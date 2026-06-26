#!/usr/bin/env python3
"""Controlled backbone comparison on the revised Bologna Stage-2 tile dataset.

This script reuses the exact tile construction, train/validation/test split,
normalization, optimizer family, early stopping, and random seed from the
verified Swin3D-UNet Stage-2 experiment. The only controlled variable is the
neural backbone:

1. 3D CNN baseline
2. Swin3D-UNet

Both models are trained against the same held-out deformation target using the
same posterior-conditioned input tensor. The exported comparison table reports
full-map reconstruction metrics only.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import h5py
import numpy as np
import pandas as pd

try:
    import torch
    import torch.nn as nn
    import torch.nn.functional as F
    from torch.utils.data import DataLoader, Dataset
except ModuleNotFoundError as exc:
    raise SystemExit("This script requires PyTorch in the active environment.") from exc


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from punjab.punjab_inversion.metrics import anisotropic_total_variation, mae, r2_score_np, rmse  # noqa: E402
from punjab.punjab_inversion.models import ContextConditionedResidualSwinUNet3D  # noqa: E402
from punjab.punjab_inversion.physics import PhysicsConfig, build_fft_kernels, forward_physics_torch, set_seed  # noqa: E402


FIELD_NAMES = ("Load_total", "Sg")


@dataclass
class ComparisonConfig:
    stage1_results_path: str = "/home/ubuntu/work/insar_mcmc/outputs_stage1_bologna_real_full_grouped_quick/stage1_bologna_real_results.npz"
    full_insar_path: str = "/mnt/data/mcma/01/insar_aligned.nc"
    subregion_path: str = "/mnt/data/mcma/01/insar_sub.nc"
    temporal_coh_path: str = "/mnt/data/aoi_3_02_bologna/MintPy/temporalCoherence.h5"
    avg_coh_path: str = "/mnt/data/aoi_3_02_bologna/MintPy/avgSpatialCoh.h5"
    coh_mask_path: str = "/mnt/data/aoi_3_02_bologna/MintPy/maskTempCoh.h5"
    output_root: str = "/home/ubuntu/work/insar_mcmc"
    device: str = "auto"
    seed: int = 42
    batch_size: int = 4
    max_epochs: int = 8
    patience: int = 3
    learning_rate: float = 2e-4
    weight_decay: float = 1e-4
    window_size: int = 6
    tile_size: int = 8
    tile_stride: int = 8
    train_fraction: float = 0.65
    val_fraction: float = 0.20
    base_dim: int = 16
    time_patch: int = 2
    spatial_patch: int = 4
    num_heads: int = 4
    window_attn_t: int = 3
    window_attn_xy: int = 4
    lambda_phys: float = 1.0
    lambda_prior: float = 0.01
    lambda_anchor: float = 0.25
    lambda_tv: float = 1e-4
    residual_scale: float = 0.05
    num_workers: int = 0


def resolve_device(name: str) -> str:
    if name == "auto":
        return "cuda" if torch.cuda.is_available() else "cpu"
    return name


def bias_np(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    yt = np.asarray(y_true, dtype=np.float64)
    yp = np.asarray(y_pred, dtype=np.float64)
    mask = np.isfinite(yt) & np.isfinite(yp)
    if mask.sum() == 0:
        return float("nan")
    return float(np.mean(yp[mask] - yt[mask]))


def count_trainable_parameters(model: nn.Module) -> int:
    return int(sum(p.numel() for p in model.parameters() if p.requires_grad))


def masked_mse(pred: torch.Tensor, target: torch.Tensor, mask: torch.Tensor) -> torch.Tensor:
    weight = mask.to(dtype=pred.dtype)
    denom = weight.sum().clamp_min(1.0)
    return ((pred - target).square() * weight).sum() / denom


def infer_crop_from_subregion(full_insar_path: str, subregion_path: str) -> tuple[int, int, int, int]:
    with h5py.File(full_insar_path, "r") as full_f, h5py.File(subregion_path, "r") as sub_f:
        lat_full = full_f["lat"][:]
        lon_full = full_f["lon"][:]
        lat_sub = sub_f["lat"][:]
        lon_sub = sub_f["lon"][:]

    lat_axis = lat_full[:, 0]
    lon_axis = lon_full[0, :]
    lat_bounds = [float(np.nanmin(lat_sub)), float(np.nanmax(lat_sub))]
    lon_bounds = [float(np.nanmin(lon_sub)), float(np.nanmax(lon_sub))]
    y_candidates = [int(np.argmin(np.abs(lat_axis - v))) for v in lat_bounds]
    x_candidates = [int(np.argmin(np.abs(lon_axis - v))) for v in lon_bounds]
    y0, y1 = sorted(y_candidates)
    x0, x1 = sorted(x_candidates)
    return y0, y1 + 1, x0, x1 + 1


def map_indices(start: int, size: int, src_len: int, dst_len: int) -> np.ndarray:
    coords = np.arange(start, start + size, dtype=np.float32)
    mapped = coords / max(dst_len - 1, 1) * (src_len - 1)
    return np.clip(np.rint(mapped).astype(np.int64), 0, src_len - 1)


def load_static_context(cfg: ComparisonConfig, target_h: int, target_w: int) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    y0, _, x0, _ = infer_crop_from_subregion(cfg.full_insar_path, cfg.subregion_path)

    with h5py.File(cfg.full_insar_path, "r") as f:
        full_h = int(f["insar_deformation"].shape[1])
        full_w = int(f["insar_deformation"].shape[2])
    with h5py.File(cfg.temporal_coh_path, "r") as f:
        temporal_full = f["temporalCoherence"][:].astype(np.float32)
    with h5py.File(cfg.avg_coh_path, "r") as f:
        avg_full = f["coherence"][:].astype(np.float32)
    with h5py.File(cfg.coh_mask_path, "r") as f:
        mask_full = f["mask"][:].astype(bool)

    mintpy_h, mintpy_w = temporal_full.shape
    y_idx = map_indices(y0, target_h, mintpy_h, full_h)
    x_idx = map_indices(x0, target_w, mintpy_w, full_w)
    temporal_crop = temporal_full[np.ix_(y_idx, x_idx)]
    avg_crop = avg_full[np.ix_(y_idx, x_idx)]
    mask_crop = mask_full[np.ix_(y_idx, x_idx)]

    temporal_crop = np.where(np.isfinite(temporal_crop), temporal_crop, 0.0).astype(np.float32)
    avg_crop = np.where(np.isfinite(avg_crop), avg_crop, 0.0).astype(np.float32)
    reliability = np.sqrt(np.clip(temporal_crop, 0.0, 1.0) * np.clip(avg_crop, 0.0, 1.0)).astype(np.float32)
    reliability *= mask_crop.astype(np.float32)
    return temporal_crop, avg_crop, reliability


class Stage2TileDataset(Dataset):
    def __init__(
        self,
        y_obs: np.ndarray,
        d_prior: np.ndarray,
        x_prior: np.ndarray,
        theta_prior: np.ndarray,
        temporal_coh: np.ndarray,
        avg_coh: np.ndarray,
        prior_conf: np.ndarray,
        window_size: int,
        tile_size: int,
        tile_stride: int,
        end_indices: list[int],
    ):
        self.y_obs = y_obs.astype(np.float32)
        self.d_prior = d_prior.astype(np.float32)
        self.x_prior = x_prior.astype(np.float32)
        self.theta_prior = theta_prior.astype(np.float32)
        self.temporal_coh = temporal_coh.astype(np.float32)
        self.avg_coh = avg_coh.astype(np.float32)
        self.prior_conf = prior_conf.astype(np.float32)
        self.window_size = window_size
        self.tile_size = tile_size
        self.samples: list[tuple[int, int, int]] = []

        _, _, h, w = x_prior.shape
        y_positions = list(range(0, h - tile_size + 1, tile_stride))
        x_positions = list(range(0, w - tile_size + 1, tile_stride))
        if y_positions[-1] != h - tile_size:
            y_positions.append(h - tile_size)
        if x_positions[-1] != w - tile_size:
            x_positions.append(w - tile_size)

        for end_idx in end_indices:
            for y0 in y_positions:
                for x0 in x_positions:
                    self.samples.append((end_idx, y0, x0))

    def __len__(self) -> int:
        return len(self.samples)

    def __getitem__(self, idx: int):
        end_idx, y0, x0 = self.samples[idx]
        start_idx = end_idx - self.window_size + 1
        y1 = y0 + self.tile_size
        x1 = x0 + self.tile_size

        disp_window = self.y_obs[start_idx : end_idx + 1, y0:y1, x0:x1][None, ...]
        resid_window = (
            self.y_obs[start_idx : end_idx + 1, y0:y1, x0:x1]
            - self.d_prior[start_idx : end_idx + 1, y0:y1, x0:x1]
        )[None, ...]
        prior_window = self.x_prior[start_idx : end_idx + 1, :, y0:y1, x0:x1].transpose(1, 0, 2, 3)
        theta_window = self.theta_prior[start_idx : end_idx + 1, :, y0:y1, x0:x1].transpose(1, 0, 2, 3)
        temporal_window = np.repeat(self.temporal_coh[None, None, y0:y1, x0:x1], self.window_size, axis=1)
        avg_window = np.repeat(self.avg_coh[None, None, y0:y1, x0:x1], self.window_size, axis=1)
        conf_window = np.repeat(self.prior_conf[None, None, y0:y1, x0:x1], self.window_size, axis=1)
        x_in = np.concatenate(
            [disp_window, resid_window, prior_window, theta_window, temporal_window, avg_window, conf_window],
            axis=0,
        )

        x_prior_last = self.x_prior[end_idx, :, y0:y1, x0:x1]
        u_last = self.y_obs[end_idx, y0:y1, x0:x1][None, ...]
        obs_weight = np.maximum(self.temporal_coh[y0:y1, x0:x1][None, ...], 1e-3).astype(np.float32)
        anchor_weight = np.maximum(self.prior_conf[y0:y1, x0:x1][None, ...], 1e-3).astype(np.float32)
        meta = np.array([end_idx, y0, x0], dtype=np.int64)

        return (
            torch.tensor(x_in, dtype=torch.float32),
            torch.tensor(x_prior_last, dtype=torch.float32),
            torch.tensor(u_last, dtype=torch.float32),
            torch.tensor(obs_weight, dtype=torch.float32),
            torch.tensor(anchor_weight, dtype=torch.float32),
            torch.tensor(meta, dtype=torch.int64),
        )


@dataclass
class Stage2Stats:
    x_mean: torch.Tensor
    x_std: torch.Tensor
    state_mean: torch.Tensor
    state_std: torch.Tensor


def compute_stats(ds: Stage2TileDataset) -> Stage2Stats:
    x_sum = None
    x_sq = None
    x_count = 0.0
    s_sum = None
    s_sq = None
    s_count = 0.0

    for idx in range(len(ds)):
        x_in, x_prior_last, _, _, _, _ = ds[idx]
        x_np = x_in.numpy()
        s_np = x_prior_last.numpy()
        if x_sum is None:
            x_sum = x_np.sum(axis=(1, 2, 3))
            x_sq = np.square(x_np).sum(axis=(1, 2, 3))
            s_sum = s_np.sum(axis=(1, 2))
            s_sq = np.square(s_np).sum(axis=(1, 2))
        else:
            x_sum += x_np.sum(axis=(1, 2, 3))
            x_sq += np.square(x_np).sum(axis=(1, 2, 3))
            s_sum += s_np.sum(axis=(1, 2))
            s_sq += np.square(s_np).sum(axis=(1, 2))
        x_count += float(np.prod(x_np.shape[1:]))
        s_count += float(np.prod(s_np.shape[1:]))

    x_mean = x_sum / max(x_count, 1.0)
    x_var = x_sq / max(x_count, 1.0) - np.square(x_mean)
    s_mean = s_sum / max(s_count, 1.0)
    s_var = s_sq / max(s_count, 1.0) - np.square(s_mean)
    return Stage2Stats(
        x_mean=torch.tensor(x_mean[:, None, None, None], dtype=torch.float32),
        x_std=torch.tensor(np.sqrt(np.maximum(x_var, 1e-6))[:, None, None, None], dtype=torch.float32),
        state_mean=torch.tensor(s_mean[:, None, None], dtype=torch.float32),
        state_std=torch.tensor(np.sqrt(np.maximum(s_var, 1e-6))[:, None, None], dtype=torch.float32),
    )


class NormalizedSubset(Dataset):
    def __init__(self, base: Stage2TileDataset, stats: Stage2Stats):
        self.base = base
        self.stats = stats

    def __len__(self) -> int:
        return len(self.base)

    def __getitem__(self, idx: int):
        x_in, x_prior_last, u_last, obs_weight, anchor_weight, meta = self.base[idx]
        x_in = (x_in - self.stats.x_mean) / self.stats.x_std
        return x_in, x_prior_last, u_last, obs_weight, anchor_weight, meta


class CNN3DResidualBaseline(nn.Module):
    def __init__(self, in_channels: int, out_channels: int, base_dim: int = 32):
        super().__init__()
        self.net = nn.Sequential(
            nn.Conv3d(in_channels, base_dim, kernel_size=3, padding=1),
            nn.GELU(),
            nn.Conv3d(base_dim, base_dim * 2, kernel_size=3, padding=1),
            nn.GELU(),
            nn.Conv3d(base_dim * 2, base_dim * 2, kernel_size=3, padding=1),
            nn.GELU(),
            nn.Conv3d(base_dim * 2, base_dim, kernel_size=3, padding=1),
            nn.GELU(),
            nn.Conv3d(base_dim, out_channels, kernel_size=1),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.net(x)[:, :, -1]


class ConvBlock3D(nn.Module):
    def __init__(self, in_channels: int, out_channels: int):
        super().__init__()
        self.block = nn.Sequential(
            nn.Conv3d(in_channels, out_channels, kernel_size=3, padding=1),
            nn.GELU(),
            nn.Conv3d(out_channels, out_channels, kernel_size=3, padding=1),
            nn.GELU(),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.block(x)


class UNet3DResidualBaseline(nn.Module):
    def __init__(self, in_channels: int, out_channels: int, base_dim: int = 16):
        super().__init__()
        self.enc1 = ConvBlock3D(in_channels, base_dim)
        self.pool1 = nn.MaxPool3d(kernel_size=(1, 2, 2), stride=(1, 2, 2))
        self.enc2 = ConvBlock3D(base_dim, base_dim * 2)
        self.pool2 = nn.MaxPool3d(kernel_size=(1, 2, 2), stride=(1, 2, 2))
        self.bottleneck = ConvBlock3D(base_dim * 2, base_dim * 4)
        self.up2 = nn.ConvTranspose3d(base_dim * 4, base_dim * 2, kernel_size=(1, 2, 2), stride=(1, 2, 2))
        self.dec2 = ConvBlock3D(base_dim * 4, base_dim * 2)
        self.up1 = nn.ConvTranspose3d(base_dim * 2, base_dim, kernel_size=(1, 2, 2), stride=(1, 2, 2))
        self.dec1 = ConvBlock3D(base_dim * 2, base_dim)
        self.head = nn.Conv3d(base_dim, out_channels, kernel_size=1)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        e1 = self.enc1(x)
        e2 = self.enc2(self.pool1(e1))
        b = self.bottleneck(self.pool2(e2))
        d2 = self.up2(b)
        if d2.shape[-2:] != e2.shape[-2:]:
            d2 = F.interpolate(d2, size=e2.shape[-3:], mode="trilinear", align_corners=False)
        d2 = self.dec2(torch.cat([d2, e2], dim=1))
        d1 = self.up1(d2)
        if d1.shape[-2:] != e1.shape[-2:]:
            d1 = F.interpolate(d1, size=e1.shape[-3:], mode="trilinear", align_corners=False)
        d1 = self.dec1(torch.cat([d1, e1], dim=1))
        return self.head(d1)[:, :, -1]


def build_model(name: str, cfg: ComparisonConfig) -> nn.Module:
    in_channels = 2 + len(FIELD_NAMES) + len(FIELD_NAMES) + 3
    out_channels = len(FIELD_NAMES)
    if name == "3d_cnn":
        return CNN3DResidualBaseline(in_channels=in_channels, out_channels=out_channels, base_dim=32)
    if name == "3d_unet":
        return UNet3DResidualBaseline(in_channels=in_channels, out_channels=out_channels, base_dim=16)
    if name == "swin3d_unet":
        return ContextConditionedResidualSwinUNet3D(
            in_channels=in_channels,
            out_channels=out_channels,
            base_dim=cfg.base_dim,
            time_patch=cfg.time_patch,
            spatial_patch=cfg.spatial_patch,
            num_heads=cfg.num_heads,
            window_size=(cfg.window_attn_t, cfg.window_attn_xy, cfg.window_attn_xy),
        )
    raise ValueError(f"Unknown model name: {name}")


def maybe_reset_peak_memory(device: str) -> None:
    if device == "cuda":
        torch.cuda.reset_peak_memory_stats()


def maybe_peak_memory_gb(device: str) -> float:
    if device != "cuda":
        return float("nan")
    return float(torch.cuda.max_memory_allocated() / (1024 ** 3))


def maybe_sync(device: str) -> None:
    if device == "cuda":
        torch.cuda.synchronize()


def run_epoch(
    model: nn.Module,
    loader: DataLoader,
    optimizer: torch.optim.Optimizer | None,
    stats: Stage2Stats,
    g_load_fft: torch.Tensor,
    g_poro_fft: torch.Tensor,
    physics: PhysicsConfig,
    cfg: ComparisonConfig,
    device: str,
) -> dict[str, float]:
    train = optimizer is not None
    model.train() if train else model.eval()
    running = {"loss": 0.0, "loss_phys": 0.0, "loss_prior": 0.0, "loss_anchor": 0.0, "loss_tv": 0.0}
    n = 0

    state_mean = stats.state_mean.to(device)[None, ...]
    state_std = stats.state_std.to(device)[None, ...]

    for xb, xprior_b, ub, obs_weight, anchor_weight, _meta in loader:
        xb = xb.to(device)
        xprior_b = xprior_b.to(device)
        ub = ub.to(device)
        obs_weight = obs_weight.to(device)
        anchor_weight = anchor_weight.to(device)

        with torch.set_grad_enabled(train):
            res_norm = model(xb)
            res_raw = torch.tanh(res_norm) * (cfg.residual_scale * state_std)
            x_final = xprior_b + res_raw
            d_hat = forward_physics_torch(
                x_final,
                g_load_fft,
                g_poro_fft,
                physics,
                sg_index=1,
                load_indices=(0,),
            )
            loss_phys = masked_mse(d_hat, ub, obs_weight)
            loss_prior = res_norm.square().mean()
            loss_anchor = masked_mse(torch.tanh(res_norm), torch.zeros_like(res_norm), anchor_weight)
            x_final_scaled = (x_final - state_mean) / state_std
            loss_tv = anisotropic_total_variation(x_final_scaled)
            loss = (
                cfg.lambda_phys * loss_phys
                + cfg.lambda_prior * loss_prior
                + cfg.lambda_anchor * loss_anchor
                + cfg.lambda_tv * loss_tv
            )

            if train:
                optimizer.zero_grad()
                loss.backward()
                optimizer.step()

        bsz = xb.shape[0]
        n += bsz
        running["loss"] += float(loss.item()) * bsz
        running["loss_phys"] += float(loss_phys.item()) * bsz
        running["loss_prior"] += float(loss_prior.item()) * bsz
        running["loss_anchor"] += float(loss_anchor.item()) * bsz
        running["loss_tv"] += float(loss_tv.item()) * bsz

    return {k: v / max(n, 1) for k, v in running.items()}


def evaluate_model(
    model: nn.Module,
    loader: DataLoader,
    stats: Stage2Stats,
    g_load_fft: torch.Tensor,
    g_poro_fft: torch.Tensor,
    physics: PhysicsConfig,
    cfg: ComparisonConfig,
    device: str,
) -> dict[str, Any]:
    state_std = stats.state_std.to(device)[None, ...]
    model.eval()

    y_true_all = []
    y_prior_all = []
    y_pred_all = []
    meta_all = []

    maybe_reset_peak_memory(device)
    maybe_sync(device)
    t0 = time.perf_counter()

    with torch.no_grad():
        for xb, xprior_b, ub, _obs_weight, _anchor_weight, meta in loader:
            xb = xb.to(device)
            xprior_b = xprior_b.to(device)
            ub = ub.to(device)

            res_norm = model(xb)
            res_raw = torch.tanh(res_norm) * (cfg.residual_scale * state_std)
            x_final = xprior_b + res_raw
            d_prior = forward_physics_torch(
                xprior_b,
                g_load_fft,
                g_poro_fft,
                physics,
                sg_index=1,
                load_indices=(0,),
            )
            d_pred = forward_physics_torch(
                x_final,
                g_load_fft,
                g_poro_fft,
                physics,
                sg_index=1,
                load_indices=(0,),
            )

            y_true_all.append(ub[:, 0].cpu().numpy())
            y_prior_all.append(d_prior[:, 0].cpu().numpy())
            y_pred_all.append(d_pred[:, 0].cpu().numpy())
            meta_all.append(meta.cpu().numpy())

    maybe_sync(device)
    inference_seconds = time.perf_counter() - t0
    inference_peak_gb = maybe_peak_memory_gb(device)

    y_true = np.concatenate(y_true_all, axis=0) if y_true_all else np.empty((0, cfg.tile_size, cfg.tile_size), dtype=np.float32)
    y_prior = np.concatenate(y_prior_all, axis=0) if y_prior_all else np.empty_like(y_true)
    y_pred = np.concatenate(y_pred_all, axis=0) if y_pred_all else np.empty_like(y_true)
    meta = np.concatenate(meta_all, axis=0) if meta_all else np.empty((0, 3), dtype=np.int64)

    y_true_mm = y_true * 1000.0
    y_prior_mm = y_prior * 1000.0
    y_pred_mm = y_pred * 1000.0

    regional_true = np.nanmean(y_true_mm, axis=(1, 2))
    regional_pred = np.nanmean(y_pred_mm, axis=(1, 2))
    regional_prior = np.nanmean(y_prior_mm, axis=(1, 2))

    metrics = {
        "rmse_mm": rmse(y_true_mm, y_pred_mm),
        "mae_mm": mae(y_true_mm, y_pred_mm),
        "bias_mm": bias_np(y_true_mm, y_pred_mm),
        "regional_r2": r2_score_np(regional_true, regional_pred),
        "tile_r2": r2_score_np(y_true_mm, y_pred_mm),
        "prior_rmse_mm": rmse(y_true_mm, y_prior_mm),
        "prior_mae_mm": mae(y_true_mm, y_prior_mm),
        "prior_bias_mm": bias_np(y_true_mm, y_prior_mm),
        "prior_regional_r2": r2_score_np(regional_true, regional_prior),
        "prior_tile_r2": r2_score_np(y_true_mm, y_prior_mm),
        "inference_time_seconds": inference_seconds,
        "peak_gpu_memory_gb_inference": inference_peak_gb,
    }
    return {
        "metrics": metrics,
        "y_true_mm": y_true_mm.astype(np.float32),
        "y_prior_mm": y_prior_mm.astype(np.float32),
        "y_pred_mm": y_pred_mm.astype(np.float32),
        "regional_true_mm": regional_true.astype(np.float32),
        "regional_prior_mm": regional_prior.astype(np.float32),
        "regional_pred_mm": regional_pred.astype(np.float32),
        "meta": meta.astype(np.int64),
    }


def reconstruct_full_state(
    model: nn.Module,
    ds: Stage2TileDataset,
    stats: Stage2Stats,
    cfg: ComparisonConfig,
    device: str,
) -> np.ndarray:
    t_steps, k_dim, h, w = ds.x_prior.shape
    x_final_sum = np.zeros((t_steps, k_dim, h, w), dtype=np.float32)
    x_final_count = np.zeros((t_steps, 1, h, w), dtype=np.float32)
    x_mean = stats.x_mean.to(device)
    x_std = stats.x_std.to(device)
    state_std = stats.state_std.to(device)[None, ...]

    model.eval()
    with torch.no_grad():
        for idx in range(len(ds)):
            x_in, x_prior_last, _u_last, _obs_weight, _anchor_weight, meta = ds[idx]
            end_idx, y0, x0 = [int(v) for v in meta.tolist()]
            xb = ((x_in.to(device) - x_mean) / x_std).unsqueeze(0)
            x_prior_last = x_prior_last.to(device).unsqueeze(0)
            res_norm = model(xb)
            x_final_tile = (
                x_prior_last + torch.tanh(res_norm) * (cfg.residual_scale * state_std)
            ).squeeze(0).cpu().numpy()
            y1 = y0 + cfg.tile_size
            x1 = x0 + cfg.tile_size
            x_final_sum[end_idx, :, y0:y1, x0:x1] += x_final_tile
            x_final_count[end_idx, :, y0:y1, x0:x1] += 1.0

    denom = np.maximum(np.repeat(x_final_count, k_dim, axis=1), 1.0)
    x_avg = x_final_sum / denom
    x_final = np.where(np.repeat(x_final_count > 0, k_dim, axis=1), x_avg, ds.x_prior)
    return x_final.astype(np.float32)


def predict_full_deformation(x_state: np.ndarray, physics: PhysicsConfig) -> np.ndarray:
    tensor = torch.tensor(x_state, dtype=torch.float32, device="cpu")
    g_load_fft, g_poro_fft = build_fft_kernels(x_state.shape[2], x_state.shape[3], physics, device="cpu")
    with torch.no_grad():
        pred = forward_physics_torch(
            tensor,
            g_load_fft,
            g_poro_fft,
            physics,
            sg_index=1,
            load_indices=(0,),
        )
    return pred.squeeze(1).cpu().numpy().astype(np.float32)


def evaluate_full_map(y_obs: np.ndarray, d_pred: np.ndarray) -> dict[str, float]:
    y_true_mm = y_obs.astype(np.float32) * 1000.0
    y_pred_mm = d_pred.astype(np.float32) * 1000.0
    regional_true = np.nanmean(y_true_mm, axis=(1, 2))
    regional_pred = np.nanmean(y_pred_mm, axis=(1, 2))
    return {
        "rmse_mm": rmse(y_true_mm, y_pred_mm),
        "mae_mm": mae(y_true_mm, y_pred_mm),
        "bias_mm": bias_np(y_true_mm, y_pred_mm),
        "regional_r2": r2_score_np(regional_true, regional_pred),
        "tile_r2": r2_score_np(y_true_mm, y_pred_mm),
    }


def run_single_model(
    name: str,
    cfg: ComparisonConfig,
    train_loader: DataLoader,
    val_loader: DataLoader,
    test_loader: DataLoader,
    full_base: Stage2TileDataset,
    stats: Stage2Stats,
    physics: PhysicsConfig,
    device: str,
    checkpoint_dir: Path,
    prediction_dir: Path,
    y_obs_full: np.ndarray,
) -> dict[str, Any]:
    model = build_model(name, cfg).to(device)
    optimizer = torch.optim.AdamW(model.parameters(), lr=cfg.learning_rate, weight_decay=cfg.weight_decay)
    g_load_fft, g_poro_fft = build_fft_kernels(cfg.tile_size, cfg.tile_size, physics, device=device)

    best_val = math.inf
    best_state = None
    history: list[dict[str, Any]] = []
    patience_left = cfg.patience

    maybe_reset_peak_memory(device)
    maybe_sync(device)
    t0 = time.perf_counter()

    for epoch in range(1, cfg.max_epochs + 1):
        train_metrics = run_epoch(model, train_loader, optimizer, stats, g_load_fft, g_poro_fft, physics, cfg, device)
        val_metrics = run_epoch(model, val_loader, None, stats, g_load_fft, g_poro_fft, physics, cfg, device)
        history.append({"epoch": epoch, "train": train_metrics, "val": val_metrics})

        print(
            f"[{name}][epoch {epoch:02d}] train={train_metrics['loss']:.4f} "
            f"(phys={train_metrics['loss_phys']:.4f}, prior={train_metrics['loss_prior']:.4f}, "
            f"anchor={train_metrics['loss_anchor']:.4f}) | val={val_metrics['loss']:.4f}"
        )

        if val_metrics["loss"] < best_val:
            best_val = val_metrics["loss"]
            best_state = {k: v.detach().cpu().clone() for k, v in model.state_dict().items()}
            patience_left = cfg.patience
        else:
            patience_left -= 1
            if patience_left <= 0:
                print(f"[{name}] Early stopping at epoch {epoch}.")
                break

    maybe_sync(device)
    training_seconds = time.perf_counter() - t0
    training_peak_gb = maybe_peak_memory_gb(device)

    if best_state is not None:
        model.load_state_dict(best_state)

    checkpoint_path = checkpoint_dir / f"{name}.pt"
    torch.save(model.state_dict(), checkpoint_path)

    eval_out = evaluate_model(model, test_loader, stats, g_load_fft, g_poro_fft, physics, cfg, device)
    x_final_full = reconstruct_full_state(model, full_base, stats, cfg, device)
    d_final_full = predict_full_deformation(x_final_full, physics)
    full_map_metrics = evaluate_full_map(y_obs_full, d_final_full)
    prediction_path = prediction_dir / f"{name}_test.npz"
    np.savez_compressed(
        prediction_path,
        y_true_mm=eval_out["y_true_mm"],
        y_prior_mm=eval_out["y_prior_mm"],
        y_pred_mm=eval_out["y_pred_mm"],
        regional_true_mm=eval_out["regional_true_mm"],
        regional_prior_mm=eval_out["regional_prior_mm"],
        regional_pred_mm=eval_out["regional_pred_mm"],
        sample_meta=eval_out["meta"],
        x_final_full=x_final_full.astype(np.float32),
        d_final_full_mm=(d_final_full.astype(np.float32) * 1000.0),
        y_obs_full_mm=(y_obs_full.astype(np.float32) * 1000.0),
    )

    metrics = {
        "model": name,
        "trainable_parameters": count_trainable_parameters(model),
        "rmse_mm": full_map_metrics["rmse_mm"],
        "mae_mm": full_map_metrics["mae_mm"],
        "bias_mm": full_map_metrics["bias_mm"],
        "regional_r2": full_map_metrics["regional_r2"],
        "tile_r2": full_map_metrics["tile_r2"],
        "peak_gpu_memory_gb": max(training_peak_gb, eval_out["metrics"]["peak_gpu_memory_gb_inference"])
        if np.isfinite(training_peak_gb) or np.isfinite(eval_out["metrics"]["peak_gpu_memory_gb_inference"])
        else float("nan"),
        "training_time_seconds": training_seconds,
        "inference_time_seconds": eval_out["metrics"]["inference_time_seconds"],
        "checkpoint": str(checkpoint_path),
        "prediction_npz": str(prediction_path),
        "history": history,
        "best_val_loss": best_val,
        "heldout_tile_metrics": eval_out["metrics"],
        "full_map_metrics": full_map_metrics,
    }
    return metrics


def build_datasets(
    cfg: ComparisonConfig,
) -> tuple[Stage2Stats, DataLoader, DataLoader, DataLoader, Stage2TileDataset, dict[str, Any]]:
    src = np.load(cfg.stage1_results_path)
    field_names = tuple(str(x) for x in src["field_names"].tolist())
    if field_names != FIELD_NAMES:
        raise ValueError(f"Expected grouped Stage-1 fields {FIELD_NAMES}, got {field_names}.")

    x_prior = src["x_prior"].astype(np.float32)
    theta_prior = src["theta_hat"].astype(np.float32)
    y_obs = src["y_obs"].astype(np.float32)
    d_prior_full = src["y_pred"].astype(np.float32)
    times = src["time"]

    temporal_coh, avg_coh, reliability = load_static_context(cfg, y_obs.shape[1], y_obs.shape[2])
    resid_abs = np.mean(np.abs(y_obs - d_prior_full), axis=0)
    resid_scale = float(np.nanmean(resid_abs) + 1e-6)
    stage1_fit_conf = np.exp(-resid_abs / resid_scale).astype(np.float32)
    prior_conf = np.clip(reliability * stage1_fit_conf, 0.0, 1.0).astype(np.float32)

    t_steps = y_obs.shape[0]
    end_all = list(range(cfg.window_size - 1, t_steps))
    n_total_times = len(end_all)
    n_train_times = max(1, int(cfg.train_fraction * n_total_times))
    n_val_times = max(1, int(cfg.val_fraction * n_total_times))
    n_test_times = max(1, n_total_times - n_train_times - n_val_times)
    train_times = end_all[:n_train_times]
    val_times = end_all[n_train_times : n_train_times + n_val_times]
    test_times = end_all[n_train_times + n_val_times : n_train_times + n_val_times + n_test_times]

    train_base = Stage2TileDataset(
        y_obs,
        d_prior_full,
        x_prior,
        theta_prior,
        temporal_coh,
        avg_coh,
        prior_conf,
        cfg.window_size,
        cfg.tile_size,
        cfg.tile_stride,
        train_times,
    )
    val_base = Stage2TileDataset(
        y_obs,
        d_prior_full,
        x_prior,
        theta_prior,
        temporal_coh,
        avg_coh,
        prior_conf,
        cfg.window_size,
        cfg.tile_size,
        cfg.tile_stride,
        val_times,
    )
    test_base = Stage2TileDataset(
        y_obs,
        d_prior_full,
        x_prior,
        theta_prior,
        temporal_coh,
        avg_coh,
        prior_conf,
        cfg.window_size,
        cfg.tile_size,
        cfg.tile_stride,
        test_times,
    )
    full_base = Stage2TileDataset(
        y_obs,
        d_prior_full,
        x_prior,
        theta_prior,
        temporal_coh,
        avg_coh,
        prior_conf,
        cfg.window_size,
        cfg.tile_size,
        cfg.tile_stride,
        end_all,
    )

    stats = compute_stats(train_base)
    train_ds = NormalizedSubset(train_base, stats)
    val_ds = NormalizedSubset(val_base, stats)
    test_ds = NormalizedSubset(test_base, stats)

    generator = torch.Generator()
    generator.manual_seed(cfg.seed)
    train_loader = DataLoader(
        train_ds,
        batch_size=cfg.batch_size,
        shuffle=True,
        num_workers=cfg.num_workers,
        generator=generator,
    )
    val_loader = DataLoader(val_ds, batch_size=cfg.batch_size, shuffle=False, num_workers=cfg.num_workers)
    test_loader = DataLoader(test_ds, batch_size=cfg.batch_size, shuffle=False, num_workers=cfg.num_workers)

    aux = {
        "times": times,
        "train_time_indices": train_times,
        "val_time_indices": val_times,
        "test_time_indices": test_times,
        "train_samples": len(train_base),
        "val_samples": len(val_base),
        "test_samples": len(test_base),
        "field_names": list(FIELD_NAMES),
        "y_obs": y_obs,
        "d_prior": d_prior_full,
    }
    return stats, train_loader, val_loader, test_loader, full_base, aux


def to_display_name(model_key: str) -> str:
    mapping = {
        "3d_cnn": "3D CNN",
        "swin3d_unet": "Swin3D-UNet",
    }
    return mapping.get(model_key, model_key)


def format_value(val: Any, kind: str) -> str:
    if val is None or (isinstance(val, float) and not np.isfinite(val)):
        return r"\textemdash"
    if kind == "params":
        return f"{int(val):,}"
    if kind in {"rmse", "mae", "bias"}:
        return f"{float(val):.5f}"
    if kind in {"r2"}:
        return f"{float(val):.5f}"
    if kind == "seconds":
        return f"{float(val):.2f}"
    if kind == "gb":
        return f"{float(val):.3f}"
    return str(val)


def write_latex_table(df: pd.DataFrame, out_path: Path) -> None:
    rows = []
    for _, row in df.iterrows():
        rows.append(
            " & ".join(
                [
                    to_display_name(row["model"]),
                    format_value(row["trainable_parameters"], "params"),
                    format_value(row["rmse_mm"], "rmse"),
                    format_value(row["mae_mm"], "mae"),
                    format_value(row["bias_mm"], "bias"),
                    format_value(row["regional_r2"], "r2"),
                    format_value(row["tile_r2"], "r2"),
                    format_value(row["peak_gpu_memory_gb"], "gb"),
                    format_value(row["training_time_seconds"], "seconds"),
                    format_value(row["inference_time_seconds"], "seconds"),
                ]
            )
            + r" \\"
        )

    latex = r"""\begin{table*}[t]
\centering
\caption{Controlled backbone comparison on the shared MT-InSAR/W3RA Bologna tile dataset using full-map reconstruction metrics only. Both backbones use the same posterior-conditioned input tensor, the same tile windows, the same train/validation/test split, the same normalization, and the same optimization/early-stopping configuration. RMSE, MAE, and bias are reported in mm on the reconstructed full-map deformation target. Regional $R^2$ is computed after spatial averaging each reconstructed map in time, while tile $R^2$ uses all valid full-map pixels and times.}
\label{tab:controlled_backbone_comparison}
\begin{tabular}{lrrrrrrrrr}
\hline
Model & Params & RMSE & MAE & Bias & Regional $R^2$ & Tile $R^2$ & Peak GPU (GB) & Train time (s) & Inference (s) \\
\hline
"""
    latex += "\n".join(rows)
    latex += r"""
\\
\hline
\end{tabular}
\end{table*}
"""
    out_path.write_text(latex)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage1-results-path", default=ComparisonConfig.stage1_results_path)
    parser.add_argument("--output-root", default=ComparisonConfig.output_root)
    parser.add_argument("--device", default=ComparisonConfig.device)
    parser.add_argument("--seed", type=int, default=ComparisonConfig.seed)
    args = parser.parse_args()

    cfg = ComparisonConfig(
        stage1_results_path=args.stage1_results_path,
        output_root=args.output_root,
        device=args.device,
        seed=args.seed,
    )

    set_seed(cfg.seed)
    device = resolve_device(cfg.device)
    physics = PhysicsConfig()

    out_root = Path(cfg.output_root)
    checkpoint_dir = out_root / "checkpoints"
    prediction_dir = out_root / "predictions"
    metrics_dir = out_root / "metrics"
    tables_dir = out_root / "tables"
    checkpoint_dir.mkdir(parents=True, exist_ok=True)
    prediction_dir.mkdir(parents=True, exist_ok=True)
    metrics_dir.mkdir(parents=True, exist_ok=True)
    tables_dir.mkdir(parents=True, exist_ok=True)

    stats, train_loader, val_loader, test_loader, full_base, aux = build_datasets(cfg)
    print(
        "Controlled split:",
        f"train_samples={aux['train_samples']}",
        f"val_samples={aux['val_samples']}",
        f"test_samples={aux['test_samples']}",
    )

    results: list[dict[str, Any]] = []
    for model_name in ("3d_cnn", "swin3d_unet"):
        metrics = run_single_model(
            model_name,
            cfg,
            train_loader,
            val_loader,
            test_loader,
            full_base,
            stats,
            physics,
            device,
            checkpoint_dir,
            prediction_dir,
            aux["y_obs"],
        )
        results.append(metrics)

    for row in results:
        row["display_name"] = to_display_name(row["model"])

    metrics_json_path = metrics_dir / "backbone_comparison_metrics.json"
    metrics_csv_path = metrics_dir / "backbone_comparison_metrics.csv"
    table_tex_path = tables_dir / "controlled_backbone_comparison.tex"

    json_payload = {
        "config": asdict(cfg),
        "device_resolved": device,
        "field_names": aux["field_names"],
        "splits": {
            "train_time_indices": aux["train_time_indices"],
            "val_time_indices": aux["val_time_indices"],
            "test_time_indices": aux["test_time_indices"],
            "train_samples": aux["train_samples"],
            "val_samples": aux["val_samples"],
            "test_samples": aux["test_samples"],
        },
        "rows": results,
    }
    metrics_json_path.write_text(json.dumps(json_payload, indent=2, default=lambda x: float(x) if isinstance(x, np.floating) else x))

    df = pd.DataFrame(results)
    ordered_cols = [
        "model",
        "display_name",
        "trainable_parameters",
        "rmse_mm",
        "mae_mm",
        "bias_mm",
        "regional_r2",
        "tile_r2",
        "peak_gpu_memory_gb",
        "training_time_seconds",
        "inference_time_seconds",
        "checkpoint",
        "prediction_npz",
        "best_val_loss",
    ]
    existing_cols = [c for c in ordered_cols if c in df.columns]
    df[existing_cols].to_csv(metrics_csv_path, index=False)
    write_latex_table(df, table_tex_path)

    print("Wrote:")
    print(" -", metrics_csv_path)
    print(" -", metrics_json_path)
    print(" -", table_tex_path)


if __name__ == "__main__":
    main()
