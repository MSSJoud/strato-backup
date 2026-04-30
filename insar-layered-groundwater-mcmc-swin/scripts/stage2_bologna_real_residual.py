#!/usr/bin/env python3
"""Real Bologna Stage 2 residual refinement on top of grouped Stage 1 prior."""

from __future__ import annotations

import argparse
import json
import math
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

import h5py
import numpy as np

try:
    import torch
    from torch.utils.data import DataLoader, Dataset
except ModuleNotFoundError as exc:
    raise SystemExit("This script requires PyTorch in the active environment.") from exc


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from punjab.punjab_inversion.metrics import anisotropic_total_variation, corr_np, r2_score_np, rmse  # noqa: E402
from punjab.punjab_inversion.models import ContextConditionedResidualSwinUNet3D  # noqa: E402
from punjab.punjab_inversion.physics import PhysicsConfig, build_fft_kernels, forward_physics_torch, set_seed  # noqa: E402


FIELD_NAMES = ("Load_total", "Sg")


@dataclass
class Stage2BolognaConfig:
    stage1_results_path: str = "/home/ubuntu/work/insar_mcmc/outputs_stage1_bologna_real_full_grouped_quick/stage1_bologna_real_results.npz"
    output_dir: str = "/home/ubuntu/work/insar_mcmc/outputs_stage2_bologna_real_full_grouped_strong"
    full_insar_path: str = "/mnt/data/mcma/01/insar_aligned.nc"
    subregion_path: str = "/mnt/data/mcma/01/insar_sub.nc"
    temporal_coh_path: str = "/mnt/data/aoi_3_02_bologna/MintPy/temporalCoherence.h5"
    avg_coh_path: str = "/mnt/data/aoi_3_02_bologna/MintPy/avgSpatialCoh.h5"
    coh_mask_path: str = "/mnt/data/aoi_3_02_bologna/MintPy/maskTempCoh.h5"
    seed: int = 42
    device: str = "auto"
    batch_size: int = 8
    max_epochs: int = 4
    patience: int = 2
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
    lambda_prior: float = 5e-2
    lambda_anchor: float = 0.25
    lambda_tv: float = 1e-4
    residual_scale: float = 0.05
    num_workers: int = 0


def resolve_device(name: str) -> str:
    if name == "auto":
        return "cuda" if torch.cuda.is_available() else "cpu"
    return name


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


def load_static_context(cfg: Stage2BolognaConfig, target_h: int, target_w: int) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
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


class Stage2BolognaDataset(Dataset):
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
        resid_window = (self.y_obs[start_idx : end_idx + 1, y0:y1, x0:x1] - self.d_prior[start_idx : end_idx + 1, y0:y1, x0:x1])[None, ...]
        prior_window = self.x_prior[start_idx : end_idx + 1, :, y0:y1, x0:x1].transpose(1, 0, 2, 3)
        theta_window = self.theta_prior[start_idx : end_idx + 1, :, y0:y1, x0:x1].transpose(1, 0, 2, 3)
        temporal_window = np.repeat(self.temporal_coh[None, None, y0:y1, x0:x1], self.window_size, axis=1)
        avg_window = np.repeat(self.avg_coh[None, None, y0:y1, x0:x1], self.window_size, axis=1)
        conf_window = np.repeat(self.prior_conf[None, None, y0:y1, x0:x1], self.window_size, axis=1)
        x_in = np.concatenate([disp_window, resid_window, prior_window, theta_window, temporal_window, avg_window, conf_window], axis=0)

        x_prior_last = self.x_prior[end_idx, :, y0:y1, x0:x1]
        u_last = self.y_obs[end_idx, y0:y1, x0:x1][None, ...]
        obs_weight = np.maximum(self.temporal_coh[y0:y1, x0:x1][None, ...], 1e-3).astype(np.float32)
        anchor_weight = np.maximum(self.prior_conf[y0:y1, x0:x1][None, ...], 1e-3).astype(np.float32)
        return (
            torch.tensor(x_in, dtype=torch.float32),
            torch.tensor(x_prior_last, dtype=torch.float32),
            torch.tensor(u_last, dtype=torch.float32),
            torch.tensor(obs_weight, dtype=torch.float32),
            torch.tensor(anchor_weight, dtype=torch.float32),
        )


@dataclass
class Stage2Stats:
    x_mean: torch.Tensor
    x_std: torch.Tensor
    state_mean: torch.Tensor
    state_std: torch.Tensor


def compute_stats(ds: Stage2BolognaDataset) -> Stage2Stats:
    x_sum = None
    x_sq = None
    x_count = 0.0
    s_sum = None
    s_sq = None
    s_count = 0.0

    for idx in range(len(ds)):
        x_in, x_prior_last, _, _, _ = ds[idx]
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
    def __init__(self, base: Stage2BolognaDataset, stats: Stage2Stats):
        self.base = base
        self.stats = stats

    def __len__(self) -> int:
        return len(self.base)

    def __getitem__(self, idx: int):
        x_in, x_prior_last, u_last, obs_weight, anchor_weight = self.base[idx]
        x_in = (x_in - self.stats.x_mean) / self.stats.x_std
        return x_in, x_prior_last, u_last, obs_weight, anchor_weight


def build_model(cfg: Stage2BolognaConfig) -> ContextConditionedResidualSwinUNet3D:
    return ContextConditionedResidualSwinUNet3D(
        in_channels=2 + len(FIELD_NAMES) + len(FIELD_NAMES) + 3,
        out_channels=len(FIELD_NAMES),
        base_dim=cfg.base_dim,
        time_patch=cfg.time_patch,
        spatial_patch=cfg.spatial_patch,
        num_heads=cfg.num_heads,
        window_size=(cfg.window_attn_t, cfg.window_attn_xy, cfg.window_attn_xy),
    )


def run_epoch(
    model: ContextConditionedResidualSwinUNet3D,
    loader: DataLoader,
    optimizer: torch.optim.Optimizer | None,
    stats: Stage2Stats,
    g_load_fft: torch.Tensor,
    g_poro_fft: torch.Tensor,
    physics: PhysicsConfig,
    cfg: Stage2BolognaConfig,
    device: str,
) -> dict[str, float]:
    train = optimizer is not None
    model.train() if train else model.eval()
    running = {"loss": 0.0, "loss_phys": 0.0, "loss_prior": 0.0, "loss_anchor": 0.0, "loss_tv": 0.0}
    n = 0

    state_mean = stats.state_mean.to(device)[None, ...]
    state_std = stats.state_std.to(device)[None, ...]

    for xb, xprior_b, ub, obs_weight, anchor_weight in loader:
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
            # Anchor in normalized state space so large-magnitude load values do
            # not swamp the grouped groundwater correction during training.
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


def evaluate(
    model: ContextConditionedResidualSwinUNet3D,
    loader: DataLoader,
    stats: Stage2Stats,
    g_load_fft: torch.Tensor,
    g_poro_fft: torch.Tensor,
    physics: PhysicsConfig,
    cfg: Stage2BolognaConfig,
    device: str,
) -> dict[str, float]:
    state_std = stats.state_std.to(device)[None, ...]
    model.eval()

    u_true_all, u_prior_all, u_final_all = [], [], []
    load_prior_all, load_final_all, sg_prior_all, sg_final_all = [], [], [], []

    with torch.no_grad():
        for xb, xprior_b, ub, obs_weight, anchor_weight in loader:
            del obs_weight, anchor_weight
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
            d_final = forward_physics_torch(
                x_final,
                g_load_fft,
                g_poro_fft,
                physics,
                sg_index=1,
                load_indices=(0,),
            )

            xprior_np = xprior_b.cpu().numpy()
            xfinal_np = x_final.cpu().numpy()
            ub_np = ub.cpu().numpy()
            d_prior_np = d_prior.cpu().numpy()
            d_final_np = d_final.cpu().numpy()

            for i in range(xfinal_np.shape[0]):
                u_true_all.append(ub_np[i, 0].reshape(-1))
                u_prior_all.append(d_prior_np[i, 0].reshape(-1))
                u_final_all.append(d_final_np[i, 0].reshape(-1))
                load_prior_all.append(xprior_np[i, 0].reshape(-1))
                load_final_all.append(xfinal_np[i, 0].reshape(-1))
                sg_prior_all.append(xprior_np[i, 1].reshape(-1))
                sg_final_all.append(xfinal_np[i, 1].reshape(-1))

    u_true = np.concatenate(u_true_all) if u_true_all else np.array([], dtype=np.float32)
    u_prior = np.concatenate(u_prior_all) if u_prior_all else np.array([], dtype=np.float32)
    u_final = np.concatenate(u_final_all) if u_final_all else np.array([], dtype=np.float32)
    load_prior = np.concatenate(load_prior_all) if load_prior_all else np.array([], dtype=np.float32)
    load_final = np.concatenate(load_final_all) if load_final_all else np.array([], dtype=np.float32)
    sg_prior = np.concatenate(sg_prior_all) if sg_prior_all else np.array([], dtype=np.float32)
    sg_final = np.concatenate(sg_final_all) if sg_final_all else np.array([], dtype=np.float32)

    return {
        "disp_prior_rmse": rmse(u_true, u_prior),
        "disp_final_rmse": rmse(u_true, u_final),
        "disp_prior_corr": corr_np(u_true, u_prior),
        "disp_final_corr": corr_np(u_true, u_final),
        "disp_prior_r2": r2_score_np(u_true, u_prior),
        "disp_final_r2": r2_score_np(u_true, u_final),
        "load_prior_mean": float(np.nanmean(load_prior)) if load_prior.size else float("nan"),
        "load_final_mean": float(np.nanmean(load_final)) if load_final.size else float("nan"),
        "sg_prior_mean": float(np.nanmean(sg_prior)) if sg_prior.size else float("nan"),
        "sg_final_mean": float(np.nanmean(sg_final)) if sg_final.size else float("nan"),
    }


def evaluate_full_map(y_obs: np.ndarray, d_prior: np.ndarray, d_final: np.ndarray) -> dict[str, float]:
    mask = np.isfinite(y_obs) & np.isfinite(d_prior) & np.isfinite(d_final)
    y = y_obs[mask]
    dp = d_prior[mask]
    df = d_final[mask]
    return {
        "disp_prior_rmse": rmse(y, dp),
        "disp_final_rmse": rmse(y, df),
        "disp_prior_corr": corr_np(y, dp),
        "disp_final_corr": corr_np(y, df),
        "disp_prior_r2": r2_score_np(y, dp),
        "disp_final_r2": r2_score_np(y, df),
    }


def predict_full_deformation(x_state: np.ndarray, physics: PhysicsConfig) -> np.ndarray:
    device = "cpu"
    tensor = torch.tensor(x_state, dtype=torch.float32, device=device)
    g_load_fft, g_poro_fft = build_fft_kernels(x_state.shape[2], x_state.shape[3], physics, device=device)
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


def reconstruct_full_state(
    model: ContextConditionedResidualSwinUNet3D,
    ds: Stage2BolognaDataset,
    stats: Stage2Stats,
    cfg: Stage2BolognaConfig,
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
            end_idx, y0, x0 = ds.samples[idx]
            x_in, x_prior_last, _, _, _ = ds[idx]
            xb = ((x_in.to(device) - x_mean) / x_std).unsqueeze(0)
            x_prior_last = x_prior_last.to(device).unsqueeze(0)
            res_norm = model(xb)
            x_final_tile = (x_prior_last + torch.tanh(res_norm) * (cfg.residual_scale * state_std)).squeeze(0).cpu().numpy()
            y1 = y0 + cfg.tile_size
            x1 = x0 + cfg.tile_size
            x_final_sum[end_idx, :, y0:y1, x0:x1] += x_final_tile
            x_final_count[end_idx, :, y0:y1, x0:x1] += 1.0

    denom = np.maximum(np.repeat(x_final_count, k_dim, axis=1), 1.0)
    x_avg = x_final_sum / denom
    x_final = np.where(np.repeat(x_final_count > 0, k_dim, axis=1), x_avg, ds.x_prior)
    return x_final.astype(np.float32)


def run_stage2(cfg: Stage2BolognaConfig) -> dict:
    set_seed(cfg.seed)
    device = resolve_device(cfg.device)
    physics = PhysicsConfig()

    src = np.load(cfg.stage1_results_path)
    field_names = tuple(str(x) for x in src["field_names"].tolist())
    if field_names != FIELD_NAMES:
        raise ValueError(f"Expected grouped Stage 1 fields {FIELD_NAMES}, got {field_names}.")

    x_prior = src["x_prior"].astype(np.float32)
    theta_prior = src["theta_hat"].astype(np.float32)
    y_obs = src["y_obs"].astype(np.float32)
    lat = src["lat"].astype(np.float32)
    lon = src["lon"].astype(np.float32)
    times = src["time"]
    d_prior_full = src["y_pred"].astype(np.float32)

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

    train_base = Stage2BolognaDataset(y_obs, d_prior_full, x_prior, theta_prior, temporal_coh, avg_coh, prior_conf, cfg.window_size, cfg.tile_size, cfg.tile_stride, train_times)
    val_base = Stage2BolognaDataset(y_obs, d_prior_full, x_prior, theta_prior, temporal_coh, avg_coh, prior_conf, cfg.window_size, cfg.tile_size, cfg.tile_stride, val_times)
    test_base = Stage2BolognaDataset(y_obs, d_prior_full, x_prior, theta_prior, temporal_coh, avg_coh, prior_conf, cfg.window_size, cfg.tile_size, cfg.tile_stride, test_times)
    full_base = Stage2BolognaDataset(y_obs, d_prior_full, x_prior, theta_prior, temporal_coh, avg_coh, prior_conf, cfg.window_size, cfg.tile_size, cfg.tile_stride, end_all)

    stats = compute_stats(train_base)
    train_ds = NormalizedSubset(train_base, stats)
    val_ds = NormalizedSubset(val_base, stats)
    test_ds = NormalizedSubset(test_base, stats)

    train_loader = DataLoader(train_ds, batch_size=cfg.batch_size, shuffle=True, num_workers=cfg.num_workers)
    val_loader = DataLoader(val_ds, batch_size=cfg.batch_size, shuffle=False, num_workers=cfg.num_workers)
    test_loader = DataLoader(test_ds, batch_size=cfg.batch_size, shuffle=False, num_workers=cfg.num_workers)

    model = build_model(cfg).to(device)
    optimizer = torch.optim.AdamW(model.parameters(), lr=cfg.learning_rate, weight_decay=cfg.weight_decay)
    g_load_fft, g_poro_fft = build_fft_kernels(cfg.tile_size, cfg.tile_size, physics, device=device)

    best_val = math.inf
    best_state = None
    history = []
    patience_left = cfg.patience

    for epoch in range(1, cfg.max_epochs + 1):
        train_metrics = run_epoch(model, train_loader, optimizer, stats, g_load_fft, g_poro_fft, physics, cfg, device)
        val_metrics = run_epoch(model, val_loader, None, stats, g_load_fft, g_poro_fft, physics, cfg, device)
        history.append({"epoch": epoch, "train": train_metrics, "val": val_metrics})
        print(
            f"[epoch {epoch:02d}] train={train_metrics['loss']:.4f} "
            f"(phys={train_metrics['loss_phys']:.4f}, prior={train_metrics['loss_prior']:.4f}, anchor={train_metrics['loss_anchor']:.4f}) | "
            f"val={val_metrics['loss']:.4f}"
        )

        if val_metrics["loss"] < best_val:
            best_val = val_metrics["loss"]
            best_state = {k: v.detach().cpu().clone() for k, v in model.state_dict().items()}
            patience_left = cfg.patience
        else:
            patience_left -= 1
            if patience_left <= 0:
                print(f"Early stopping at epoch {epoch}.")
                break

    if best_state is not None:
        model.load_state_dict(best_state)

    tile_test_metrics = evaluate(model, test_loader, stats, g_load_fft, g_poro_fft, physics, cfg, device)
    x_final = reconstruct_full_state(model, full_base, stats, cfg, device)
    d_final_full = predict_full_deformation(x_final, physics)
    full_map_metrics = evaluate_full_map(y_obs, d_prior_full, d_final_full)

    out_dir = Path(cfg.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    ckpt_path = out_dir / "stage2_bologna_real_best.pt"
    torch.save(model.state_dict(), ckpt_path)

    history_path = out_dir / "stage2_bologna_real_history.json"
    with history_path.open("w") as f:
        json.dump(history, f, indent=2)

    results_path = out_dir / "stage2_bologna_real_results.npz"
    np.savez_compressed(
        results_path,
        x_prior=x_prior,
        x_final=x_final,
        theta_prior=theta_prior,
        temporal_coh=temporal_coh,
        avg_coh=avg_coh,
        prior_conf=prior_conf,
        y_obs=y_obs,
        d_prior=d_prior_full,
        d_final=d_final_full,
        lat=lat,
        lon=lon,
        time=times,
        field_names=np.array(FIELD_NAMES),
    )

    summary = {
        "config": asdict(cfg),
        "shape": {
            "time": int(y_obs.shape[0]),
            "height": int(y_obs.shape[1]),
            "width": int(y_obs.shape[2]),
            "layers": len(FIELD_NAMES),
        },
        "splits": {
            "train_time_indices": train_times,
            "val_time_indices": val_times,
            "test_time_indices": test_times,
            "train_samples": len(train_base),
            "val_samples": len(val_base),
            "test_samples": len(test_base),
        },
        "test_metrics": tile_test_metrics,
        "full_map_metrics": full_map_metrics,
        "artifacts": {
            "checkpoint": str(ckpt_path),
            "history_json": str(history_path),
            "results_npz": str(results_path),
        },
    }
    summary_path = out_dir / "stage2_bologna_real_summary.json"
    with summary_path.open("w") as f:
        json.dump(summary, f, indent=2)

    print(json.dumps(summary, indent=2))
    return summary


def parse_args() -> Stage2BolognaConfig:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage1-results-path", default=Stage2BolognaConfig.stage1_results_path)
    parser.add_argument("--output-dir", default=Stage2BolognaConfig.output_dir)
    parser.add_argument("--full-insar-path", default=Stage2BolognaConfig.full_insar_path)
    parser.add_argument("--subregion-path", default=Stage2BolognaConfig.subregion_path)
    parser.add_argument("--temporal-coh-path", default=Stage2BolognaConfig.temporal_coh_path)
    parser.add_argument("--avg-coh-path", default=Stage2BolognaConfig.avg_coh_path)
    parser.add_argument("--coh-mask-path", default=Stage2BolognaConfig.coh_mask_path)
    parser.add_argument("--seed", type=int, default=Stage2BolognaConfig.seed)
    parser.add_argument("--device", default=Stage2BolognaConfig.device)
    parser.add_argument("--batch-size", type=int, default=Stage2BolognaConfig.batch_size)
    parser.add_argument("--max-epochs", type=int, default=Stage2BolognaConfig.max_epochs)
    parser.add_argument("--patience", type=int, default=Stage2BolognaConfig.patience)
    parser.add_argument("--learning-rate", type=float, default=Stage2BolognaConfig.learning_rate)
    parser.add_argument("--weight-decay", type=float, default=Stage2BolognaConfig.weight_decay)
    parser.add_argument("--window-size", type=int, default=Stage2BolognaConfig.window_size)
    parser.add_argument("--tile-size", type=int, default=Stage2BolognaConfig.tile_size)
    parser.add_argument("--tile-stride", type=int, default=Stage2BolognaConfig.tile_stride)
    parser.add_argument("--train-fraction", type=float, default=Stage2BolognaConfig.train_fraction)
    parser.add_argument("--val-fraction", type=float, default=Stage2BolognaConfig.val_fraction)
    parser.add_argument("--base-dim", type=int, default=Stage2BolognaConfig.base_dim)
    parser.add_argument("--time-patch", type=int, default=Stage2BolognaConfig.time_patch)
    parser.add_argument("--spatial-patch", type=int, default=Stage2BolognaConfig.spatial_patch)
    parser.add_argument("--num-heads", type=int, default=Stage2BolognaConfig.num_heads)
    parser.add_argument("--window-attn-t", type=int, default=Stage2BolognaConfig.window_attn_t)
    parser.add_argument("--window-attn-xy", type=int, default=Stage2BolognaConfig.window_attn_xy)
    parser.add_argument("--lambda-phys", type=float, default=Stage2BolognaConfig.lambda_phys)
    parser.add_argument("--lambda-prior", type=float, default=Stage2BolognaConfig.lambda_prior)
    parser.add_argument("--lambda-anchor", type=float, default=Stage2BolognaConfig.lambda_anchor)
    parser.add_argument("--lambda-tv", type=float, default=Stage2BolognaConfig.lambda_tv)
    parser.add_argument("--residual-scale", type=float, default=Stage2BolognaConfig.residual_scale)
    parser.add_argument("--num-workers", type=int, default=Stage2BolognaConfig.num_workers)
    args = parser.parse_args()
    return Stage2BolognaConfig(
        stage1_results_path=args.stage1_results_path,
        output_dir=args.output_dir,
        full_insar_path=args.full_insar_path,
        subregion_path=args.subregion_path,
        temporal_coh_path=args.temporal_coh_path,
        avg_coh_path=args.avg_coh_path,
        coh_mask_path=args.coh_mask_path,
        seed=args.seed,
        device=args.device,
        batch_size=args.batch_size,
        max_epochs=args.max_epochs,
        patience=args.patience,
        learning_rate=args.learning_rate,
        weight_decay=args.weight_decay,
        window_size=args.window_size,
        tile_size=args.tile_size,
        tile_stride=args.tile_stride,
        train_fraction=args.train_fraction,
        val_fraction=args.val_fraction,
        base_dim=args.base_dim,
        time_patch=args.time_patch,
        spatial_patch=args.spatial_patch,
        num_heads=args.num_heads,
        window_attn_t=args.window_attn_t,
        window_attn_xy=args.window_attn_xy,
        lambda_phys=args.lambda_phys,
        lambda_prior=args.lambda_prior,
        lambda_anchor=args.lambda_anchor,
        lambda_tv=args.lambda_tv,
        residual_scale=args.residual_scale,
        num_workers=args.num_workers,
    )


if __name__ == "__main__":
    run_stage2(parse_args())
