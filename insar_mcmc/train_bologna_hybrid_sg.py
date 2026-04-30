#!/usr/bin/env python3
"""Hybrid Bologna inversion: InSAR + MintPy coherence -> load proxy + groundwater.

This script is a cleaner alternative to the exploratory notebook pipeline. It:

1. reads the aligned Bologna InSAR and W3RA cubes
2. injects MintPy temporal/spatial coherence as static context channels
3. predicts a two-layer state at the final step of each time window:
   - load_proxy = S0 + Ss + Sd + Sr
   - Sg
4. penalizes the prediction with a forward physics loss back into deformation

The implementation reuses the Punjab Swin blocks and two-layer forward model,
but narrows the target so the groundwater channel stays the main focus.
"""

from __future__ import annotations

import argparse
import copy
import json
import math
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable

import h5py
import numpy as np

try:
    import torch
    import torch.nn.functional as F
    from torch.utils.data import DataLoader, Dataset
except ModuleNotFoundError as exc:
    raise SystemExit(
        "This script requires PyTorch in the active Python environment."
    ) from exc


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from punjab.punjab_inversion.metrics import (  # noqa: E402
    anisotropic_total_variation,
    corr_np,
    r2_score_np,
    rmse,
)
from punjab.punjab_inversion.models import (  # noqa: E402
    ContextConditionedTwoLayerSwinUNet3D,
)
from punjab.punjab_inversion.physics import (  # noqa: E402
    PhysicsConfig,
    build_fft_kernels,
    forward_two_layer_torch,
    set_seed,
)


DEVICE = "cuda" if torch.cuda.is_available() else "cpu"


@dataclass
class BolognaHybridConfig:
    insar_path: str = "/mnt/data/mcma/01/insar_aligned.nc"
    w3ra_path: str = "/mnt/data/mcma/01/w3ra_on_insar.nc"
    subregion_path: str = "/mnt/data/mcma/01/insar_sub.nc"
    temporal_coh_path: str = "/mnt/data/aoi_3_02_bologna/MintPy/temporalCoherence.h5"
    avg_coh_path: str = "/mnt/data/aoi_3_02_bologna/MintPy/avgSpatialCoh.h5"
    coh_mask_path: str = "/mnt/data/aoi_3_02_bologna/MintPy/maskTempCoh.h5"
    output_dir: str = "/home/ubuntu/work/insar_mcmc/outputs"
    cache_path: str = "/home/ubuntu/work/insar_mcmc/outputs/bologna_hybrid_cache.h5"
    seed: int = 42
    window_size: int = 6
    tile_size: int = 64
    tile_stride: int = 64
    batch_size: int = 4
    num_workers: int = 0
    eval_num_workers: int = 0
    device: str = "auto"
    cpu_threads: int = 0
    pin_memory: bool = False
    data_parallel: bool = False
    gpu_ids: str = ""
    max_epochs: int = 20
    patience: int = 5
    learning_rate: float = 2e-4
    weight_decay: float = 1e-4
    lambda_phys: float = 0.5
    lambda_tv: float = 1e-4
    sg_weight: float = 2.0
    min_coherence: float = 0.35
    min_frame_finite_fraction: float = 0.01
    target_mode: str = "anomaly"
    force_rebuild_cache: bool = False
    train_fraction: float = 0.70
    val_fraction: float = 0.15
    max_stats_samples: int = 256
    base_dim: int = 32
    time_patch: int = 2
    spatial_patch: int = 4
    num_heads: int = 4
    window_attn_t: int = 3
    window_attn_xy: int = 4


def build_positions(start: int, stop: int, size: int, stride: int) -> list[int]:
    if stop - start < size:
        raise ValueError(f"Requested tile size {size} exceeds span {stop - start}.")
    positions = list(range(start, stop - size + 1, stride))
    last = stop - size
    if positions[-1] != last:
        positions.append(last)
    return positions


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


def masked_mse(pred: torch.Tensor, target: torch.Tensor, mask: torch.Tensor) -> torch.Tensor:
    weight = mask.to(dtype=pred.dtype)
    denom = weight.sum().clamp_min(1.0)
    return ((pred - target).square() * weight).sum() / denom


def denormalize_field(x: torch.Tensor, mean: torch.Tensor, std: torch.Tensor) -> torch.Tensor:
    return x * std + mean


def resolve_device(device_name: str) -> str:
    if device_name == "auto":
        return "cuda" if torch.cuda.is_available() else "cpu"
    if device_name.startswith("cuda") and not torch.cuda.is_available():
        raise RuntimeError("CUDA was requested, but torch.cuda.is_available() is False.")
    return device_name


def parse_gpu_ids(gpu_ids: str) -> list[int]:
    if not gpu_ids.strip():
        return []
    return [int(part.strip()) for part in gpu_ids.split(",") if part.strip()]


def maybe_set_cpu_threads(cfg: BolognaHybridConfig) -> None:
    if cfg.cpu_threads and cfg.cpu_threads > 0:
        torch.set_num_threads(cfg.cpu_threads)
        if hasattr(torch, "set_num_interop_threads"):
            torch.set_num_interop_threads(max(1, min(cfg.cpu_threads, 4)))


def prepare_bologna_cache(cfg: BolognaHybridConfig, force: bool = False) -> Path:
    """Cache the cropped Bologna tensors so repeated experiments are cheap.

    The cache stores:
    - insar deformation cube on the aligned crop
    - raw and anomaly versions of load_proxy / Sg
    - MintPy temporal and average coherence on the same crop
    - a static support mask derived from MintPy coherence quality
    """

    cache_path = Path(cfg.cache_path)
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    if cache_path.exists() and not force:
        return cache_path

    crop = infer_crop_from_subregion(cfg.insar_path, cfg.subregion_path)
    y0, y1, x0, x1 = crop
    crop_h = y1 - y0
    crop_w = x1 - x0

    with h5py.File(cfg.insar_path, "r") as f:
        insar = f["insar_deformation"][:, y0:y1, x0:x1].astype(np.float32)
        lat = f["lat"][y0:y1, x0:x1].astype(np.float32)
        lon = f["lon"][y0:y1, x0:x1].astype(np.float32)
        time = f["time"][:]
        full_h = f["insar_deformation"].shape[1]
        full_w = f["insar_deformation"].shape[2]

    with h5py.File(cfg.w3ra_path, "r") as f:
        s0 = f["S0"][:, y0:y1, x0:x1].astype(np.float32)
        ss = f["Ss"][:, y0:y1, x0:x1].astype(np.float32)
        sd = f["Sd"][:, y0:y1, x0:x1].astype(np.float32)
        sr = f["Sr"][:, y0:y1, x0:x1].astype(np.float32)
        sg = f["Sg"][:, y0:y1, x0:x1].astype(np.float32)

    load_proxy = s0 + ss + sd + sr
    load_proxy_anom = load_proxy - np.nanmean(load_proxy, axis=0, keepdims=True)
    sg_anom = sg - np.nanmean(sg, axis=0, keepdims=True)

    with h5py.File(cfg.temporal_coh_path, "r") as f:
        temporal_full = f["temporalCoherence"][:].astype(np.float32)
    with h5py.File(cfg.avg_coh_path, "r") as f:
        avg_full = f["coherence"][:].astype(np.float32)
    with h5py.File(cfg.coh_mask_path, "r") as f:
        mask_full = f["mask"][:].astype(bool)

    mintpy_h, mintpy_w = temporal_full.shape

    def map_indices(start: int, size: int, src_len: int, dst_len: int) -> np.ndarray:
        coords = np.arange(start, start + size, dtype=np.float32)
        mapped = coords / max(dst_len - 1, 1) * (src_len - 1)
        return np.clip(np.rint(mapped).astype(np.int64), 0, src_len - 1)

    y_idx = map_indices(y0, crop_h, mintpy_h, full_h)
    x_idx = map_indices(x0, crop_w, mintpy_w, full_w)
    temporal_crop = temporal_full[np.ix_(y_idx, x_idx)]
    avg_crop = avg_full[np.ix_(y_idx, x_idx)]
    mask_crop = mask_full[np.ix_(y_idx, x_idx)]
    static_valid = (
        np.isfinite(temporal_crop)
        & np.isfinite(avg_crop)
        & mask_crop
        & (temporal_crop >= cfg.min_coherence)
    )

    with h5py.File(cache_path, "w") as f:
        f.create_dataset("insar", data=insar, compression="gzip", shuffle=True)
        f.create_dataset("load_proxy_raw", data=load_proxy, compression="gzip", shuffle=True)
        f.create_dataset("load_proxy_anom", data=load_proxy_anom.astype(np.float32), compression="gzip", shuffle=True)
        f.create_dataset("sg_raw", data=sg, compression="gzip", shuffle=True)
        f.create_dataset("sg_anom", data=sg_anom.astype(np.float32), compression="gzip", shuffle=True)
        f.create_dataset("temporal_coh", data=temporal_crop, compression="gzip", shuffle=True)
        f.create_dataset("avg_coh", data=avg_crop, compression="gzip", shuffle=True)
        f.create_dataset("static_valid", data=static_valid.astype(np.uint8), compression="gzip", shuffle=True)
        f.create_dataset("lat", data=lat, compression="gzip", shuffle=True)
        f.create_dataset("lon", data=lon, compression="gzip", shuffle=True)
        f.create_dataset("time", data=time)
        f.attrs["crop_y0"] = y0
        f.attrs["crop_y1"] = y1
        f.attrs["crop_x0"] = x0
        f.attrs["crop_x1"] = x1
        f.attrs["target_mode_default"] = cfg.target_mode
        f.attrs["insar_path"] = cfg.insar_path
        f.attrs["w3ra_path"] = cfg.w3ra_path
        f.attrs["temporal_coh_path"] = cfg.temporal_coh_path
        f.attrs["avg_coh_path"] = cfg.avg_coh_path
        f.attrs["coh_mask_path"] = cfg.coh_mask_path

    return cache_path


class BolognaAlignedWindowDataset(Dataset):
    """Lazy dataset over time windows and spatial tiles backed by a cached crop."""

    def __init__(self, cfg: BolognaHybridConfig):
        self.cfg = cfg
        self.cache_path = prepare_bologna_cache(cfg)
        self._cache = None

        with h5py.File(self.cache_path, "r") as f:
            self.time_len, self.crop_h, self.crop_w = f["insar"].shape
            frame_finite_fraction = np.asarray(f["insar"][:], dtype=np.float32)
            self.frame_finite_fraction = np.isfinite(frame_finite_fraction).reshape(self.time_len, -1).mean(axis=1)
            self.crop = (
                int(f.attrs["crop_y0"]),
                int(f.attrs["crop_y1"]),
                int(f.attrs["crop_x0"]),
                int(f.attrs["crop_x1"]),
            )
        self.tile_y = build_positions(0, self.crop_h, cfg.tile_size, cfg.tile_stride)
        self.tile_x = build_positions(0, self.crop_w, cfg.tile_size, cfg.tile_stride)

        end_times = []
        for end_t in range(cfg.window_size - 1, self.time_len):
            t0 = end_t - cfg.window_size + 1
            window_finite_fraction = self.frame_finite_fraction[t0 : end_t + 1]
            if np.all(window_finite_fraction >= cfg.min_frame_finite_fraction):
                end_times.append(end_t)
        n_windows = len(end_times)
        if n_windows < 3:
            raise ValueError(
                "Too few usable time windows after filtering invalid InSAR frames. "
                f"Found {n_windows}; try lowering min_frame_finite_fraction."
            )
        n_train = max(1, int(math.floor(cfg.train_fraction * n_windows)))
        n_val = max(1, int(math.floor(cfg.val_fraction * n_windows)))
        n_val = min(n_val, max(1, n_windows - n_train - 1))
        train_times = set(end_times[:n_train])
        val_times = set(end_times[n_train : n_train + n_val])
        test_times = set(end_times[n_train + n_val :])

        self.split_map = {"train": [], "val": [], "test": []}
        self.samples: list[tuple[int, int, int]] = []
        for end_t in end_times:
            split = "train" if end_t in train_times else "val" if end_t in val_times else "test"
            for y0 in self.tile_y:
                for x0 in self.tile_x:
                    self.split_map[split].append(len(self.samples))
                    self.samples.append((end_t, y0, x0))

    def _ensure_handles(self) -> None:
        if self._cache is None:
            self._cache = h5py.File(self.cache_path, "r")

    def __len__(self) -> int:
        return len(self.samples)

    def split_indices(self, split: str) -> list[int]:
        return list(self.split_map[split])

    def __getitem__(self, idx: int) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor, torch.Tensor]:
        self._ensure_handles()
        end_t, tile_y0, tile_x0 = self.samples[idx]
        t0 = end_t - self.cfg.window_size + 1

        y1 = tile_y0 + self.cfg.tile_size
        x1 = tile_x0 + self.cfg.tile_size

        ins_window = self._cache["insar"][t0 : end_t + 1, tile_y0:y1, tile_x0:x1].astype(np.float32)
        if self.cfg.target_mode == "anomaly":
            load_proxy = self._cache["load_proxy_anom"][end_t, tile_y0:y1, tile_x0:x1].astype(np.float32)
            sg = self._cache["sg_anom"][end_t, tile_y0:y1, tile_x0:x1].astype(np.float32)
        else:
            load_proxy = self._cache["load_proxy_raw"][end_t, tile_y0:y1, tile_x0:x1].astype(np.float32)
            sg = self._cache["sg_raw"][end_t, tile_y0:y1, tile_x0:x1].astype(np.float32)
        temporal_tile = self._cache["temporal_coh"][tile_y0:y1, tile_x0:x1].astype(np.float32)
        avg_tile = self._cache["avg_coh"][tile_y0:y1, tile_x0:x1].astype(np.float32)
        static_valid = self._cache["static_valid"][tile_y0:y1, tile_x0:x1].astype(bool)

        valid = (
            np.isfinite(ins_window).all(axis=0)
            & np.isfinite(load_proxy)
            & np.isfinite(sg)
            & np.isfinite(temporal_tile)
            & np.isfinite(avg_tile)
            & static_valid
        )

        temporal_rep = np.repeat(temporal_tile[None, :, :], self.cfg.window_size, axis=0)
        avg_rep = np.repeat(avg_tile[None, :, :], self.cfg.window_size, axis=0)
        x = np.stack(
            [
                np.nan_to_num(ins_window, nan=0.0),
                np.nan_to_num(temporal_rep, nan=0.0),
                np.nan_to_num(avg_rep, nan=0.0),
            ],
            axis=0,
        )
        y = np.stack(
            [
                np.nan_to_num(load_proxy, nan=0.0),
                np.nan_to_num(sg, nan=0.0),
            ],
            axis=0,
        )
        u = np.nan_to_num(ins_window[-1:], nan=0.0)
        mask = valid.astype(np.float32)[None, :, :]

        return (
            torch.from_numpy(x),
            torch.from_numpy(y),
            torch.from_numpy(u),
            torch.from_numpy(mask),
        )


@dataclass
class NormalizationStats:
    x_mean: torch.Tensor
    x_std: torch.Tensor
    y_mean: torch.Tensor
    y_std: torch.Tensor
    u_mean: torch.Tensor
    u_std: torch.Tensor


class NormalizedSubsetDataset(Dataset):
    def __init__(self, base: BolognaAlignedWindowDataset, indices: Iterable[int], stats: NormalizationStats):
        self.base = base
        self.indices = list(indices)
        self.stats = stats

    def __len__(self) -> int:
        return len(self.indices)

    def __getitem__(self, idx: int):
        x, y, u, mask = self.base[self.indices[idx]]
        x = (x - self.stats.x_mean) / self.stats.x_std
        y = (y - self.stats.y_mean) / self.stats.y_std
        u = (u - self.stats.u_mean) / self.stats.u_std
        return x, y, u, mask


def compute_stats(
    ds: BolognaAlignedWindowDataset,
    indices: list[int],
    max_samples: int,
) -> NormalizationStats:
    take = min(len(indices), max_samples)
    sample_ids = np.linspace(0, len(indices) - 1, num=take, dtype=int)

    x_sum = np.zeros(3, dtype=np.float64)
    x_sq_sum = np.zeros(3, dtype=np.float64)
    x_count = np.zeros(3, dtype=np.float64)
    y_sum = np.zeros(2, dtype=np.float64)
    y_sq_sum = np.zeros(2, dtype=np.float64)
    y_count = np.zeros(2, dtype=np.float64)
    u_sum = 0.0
    u_sq_sum = 0.0
    u_count = 0.0

    for sid in sample_ids:
        x, y, u, mask = ds[indices[sid]]
        x_np = x.numpy()
        y_np = y.numpy()
        u_np = u.numpy()
        mask_np = mask.numpy().astype(bool)[0]

        for c in range(x_np.shape[0]):
            valid_x = np.isfinite(x_np[c])
            vals = x_np[c][valid_x]
            x_sum[c] += float(vals.sum())
            x_sq_sum[c] += float(np.square(vals).sum())
            x_count[c] += float(vals.size)

        for c in range(y_np.shape[0]):
            vals = y_np[c][mask_np]
            y_sum[c] += float(vals.sum())
            y_sq_sum[c] += float(np.square(vals).sum())
            y_count[c] += float(vals.size)

        u_vals = u_np[0][mask_np]
        u_sum += float(u_vals.sum())
        u_sq_sum += float(np.square(u_vals).sum())
        u_count += float(u_vals.size)

    x_mean = x_sum / np.maximum(x_count, 1.0)
    x_var = x_sq_sum / np.maximum(x_count, 1.0) - np.square(x_mean)
    y_mean = y_sum / np.maximum(y_count, 1.0)
    y_var = y_sq_sum / np.maximum(y_count, 1.0) - np.square(y_mean)
    u_mean = u_sum / max(u_count, 1.0)
    u_var = u_sq_sum / max(u_count, 1.0) - u_mean * u_mean

    return NormalizationStats(
        x_mean=torch.tensor(x_mean[:, None, None, None], dtype=torch.float32),
        x_std=torch.tensor(np.sqrt(np.maximum(x_var, 1e-6))[:, None, None, None], dtype=torch.float32),
        y_mean=torch.tensor(y_mean[:, None, None], dtype=torch.float32),
        y_std=torch.tensor(np.sqrt(np.maximum(y_var, 1e-6))[:, None, None], dtype=torch.float32),
        u_mean=torch.tensor([[[u_mean]]], dtype=torch.float32),
        u_std=torch.tensor([[[math.sqrt(max(u_var, 1e-6))]]], dtype=torch.float32),
    )


def build_model(cfg: BolognaHybridConfig) -> ContextConditionedTwoLayerSwinUNet3D:
    return ContextConditionedTwoLayerSwinUNet3D(
        context_channels=2,
        base_dim=cfg.base_dim,
        time_patch=cfg.time_patch,
        spatial_patch=cfg.spatial_patch,
        num_heads=cfg.num_heads,
        window_size=(cfg.window_attn_t, cfg.window_attn_xy, cfg.window_attn_xy),
    )


def run_epoch(
    model: ContextConditionedTwoLayerSwinUNet3D,
    loader: DataLoader,
    optimizer: torch.optim.Optimizer | None,
    g_load_fft: torch.Tensor,
    g_poro_fft: torch.Tensor,
    stats: NormalizationStats,
    cfg: BolognaHybridConfig,
    physics_cfg: PhysicsConfig,
    device: str,
) -> dict[str, float]:
    train_mode = optimizer is not None
    model.train() if train_mode else model.eval()
    running = {"loss": 0.0, "loss_load": 0.0, "loss_sg": 0.0, "loss_phys": 0.0, "loss_tv": 0.0}
    n = 0

    y_mean = stats.y_mean.to(device)[None, ...]
    y_std = stats.y_std.to(device)[None, ...]
    u_mean = stats.u_mean.to(device)[None, ...]
    u_std = stats.u_std.to(device)[None, ...]

    for xb, yb, ub, mask in loader:
        xb = xb.to(device, non_blocking=cfg.pin_memory)
        yb = yb.to(device, non_blocking=cfg.pin_memory)
        ub = ub.to(device, non_blocking=cfg.pin_memory)
        mask = mask.to(device, non_blocking=cfg.pin_memory)

        with torch.set_grad_enabled(train_mode):
            yp_norm = model(xb)
            loss_load = masked_mse(yp_norm[:, 0:1], yb[:, 0:1], mask)
            loss_sg = masked_mse(yp_norm[:, 1:2], yb[:, 1:2], mask)

            yp_raw = denormalize_field(yp_norm, y_mean, y_std)
            d_hat_raw = forward_two_layer_torch(yp_raw, g_load_fft, g_poro_fft, physics_cfg)
            d_hat_norm = (d_hat_raw - u_mean) / u_std
            loss_phys = masked_mse(d_hat_norm, ub, mask)
            loss_tv = anisotropic_total_variation(yp_raw)
            loss = loss_load + cfg.sg_weight * loss_sg + cfg.lambda_phys * loss_phys + cfg.lambda_tv * loss_tv

            if train_mode:
                optimizer.zero_grad()
                loss.backward()
                optimizer.step()

        bsz = xb.shape[0]
        n += bsz
        running["loss"] += float(loss.item()) * bsz
        running["loss_load"] += float(loss_load.item()) * bsz
        running["loss_sg"] += float(loss_sg.item()) * bsz
        running["loss_phys"] += float(loss_phys.item()) * bsz
        running["loss_tv"] += float(loss_tv.item()) * bsz

    return {k: v / max(n, 1) for k, v in running.items()}


def evaluate_test_split(
    model: ContextConditionedTwoLayerSwinUNet3D,
    ds: NormalizedSubsetDataset,
    stats: NormalizationStats,
    g_load_fft: torch.Tensor,
    g_poro_fft: torch.Tensor,
    physics_cfg: PhysicsConfig,
    cfg: BolognaHybridConfig,
    device: str,
) -> dict[str, float]:
    loader = DataLoader(
        ds,
        batch_size=ds.base.cfg.batch_size,
        shuffle=False,
        num_workers=cfg.eval_num_workers,
        pin_memory=cfg.pin_memory,
    )
    y_mean = stats.y_mean.to(device)[None, ...]
    y_std = stats.y_std.to(device)[None, ...]

    load_true, load_pred = [], []
    sg_true, sg_pred = [], []
    u_true, u_pred = [], []

    model.eval()
    with torch.no_grad():
        for xb, yb, ub, mask in loader:
            xb = xb.to(device, non_blocking=cfg.pin_memory)
            yb = yb.to(device, non_blocking=cfg.pin_memory)
            ub = ub.to(device, non_blocking=cfg.pin_memory)
            mask = mask.to(device, non_blocking=cfg.pin_memory)

            yp_norm = model(xb)
            yp_raw = denormalize_field(yp_norm, y_mean, y_std)
            yb_raw = denormalize_field(yb, y_mean, y_std)
            d_hat = forward_two_layer_torch(yp_raw, g_load_fft, g_poro_fft, physics_cfg)

            yp_np = yp_raw.cpu().numpy()
            yb_np = yb_raw.cpu().numpy()
            ub_np = ub.cpu().numpy()
            d_hat_np = d_hat.cpu().numpy()
            mask_np = mask.cpu().numpy().astype(bool)

            for i in range(yp_np.shape[0]):
                valid = mask_np[i, 0]
                if not np.any(valid):
                    continue
                load_true.append(yb_np[i, 0][valid])
                load_pred.append(yp_np[i, 0][valid])
                sg_true.append(yb_np[i, 1][valid])
                sg_pred.append(yp_np[i, 1][valid])
                u_true.append(ub_np[i, 0][valid])
                u_pred.append(d_hat_np[i, 0][valid])

    flatten = lambda parts: np.concatenate(parts) if parts else np.array([], dtype=np.float32)
    load_true_f = flatten(load_true)
    load_pred_f = flatten(load_pred)
    sg_true_f = flatten(sg_true)
    sg_pred_f = flatten(sg_pred)
    u_true_f = flatten(u_true)
    u_pred_f = flatten(u_pred)

    return {
        "n_test_samples": len(ds),
        "n_nonempty_samples": len(load_true),
        "n_valid_pixels": int(load_true_f.size),
        "load_rmse": rmse(load_true_f, load_pred_f),
        "load_r2": r2_score_np(load_true_f, load_pred_f),
        "load_corr": corr_np(load_true_f, load_pred_f),
        "sg_rmse": rmse(sg_true_f, sg_pred_f),
        "sg_r2": r2_score_np(sg_true_f, sg_pred_f),
        "sg_corr": corr_np(sg_true_f, sg_pred_f),
        "disp_forward_rmse": rmse(u_true_f, u_pred_f),
        "disp_forward_corr": corr_np(u_true_f, u_pred_f),
    }


def collect_valid_pixel_counts(
    ds: BolognaAlignedWindowDataset,
    indices: list[int],
) -> np.ndarray:
    counts = np.zeros(len(indices), dtype=np.int64)
    for i, idx in enumerate(indices):
        _, _, _, mask = ds[idx]
        counts[i] = int(mask.sum().item())
    return counts


def summarize_valid_pixel_coverage(
    ds: BolognaAlignedWindowDataset,
    indices: list[int],
) -> dict[str, float | int]:
    counts = collect_valid_pixel_counts(ds, indices)
    nonempty = counts[counts > 0]
    return {
        "n_samples": int(counts.size),
        "n_nonempty_samples": int(nonempty.size),
        "n_empty_samples": int((counts == 0).sum()),
        "valid_pixels_total": int(counts.sum()),
        "valid_pixels_mean": float(counts.mean()) if counts.size else 0.0,
        "valid_pixels_max": int(counts.max()) if counts.size else 0,
    }


def to_jsonable_stats(stats: NormalizationStats) -> dict[str, list[float] | float]:
    return {
        "x_mean": stats.x_mean[:, 0, 0, 0].tolist(),
        "x_std": stats.x_std[:, 0, 0, 0].tolist(),
        "y_mean": stats.y_mean[:, 0, 0].tolist(),
        "y_std": stats.y_std[:, 0, 0].tolist(),
        "u_mean": float(stats.u_mean[0, 0, 0].item()),
        "u_std": float(stats.u_std[0, 0, 0].item()),
    }


def parse_args() -> BolognaHybridConfig:
    parser = argparse.ArgumentParser(description="Train the Bologna hybrid Sg-focused Swin model.")
    parser.add_argument("--output-dir", default=BolognaHybridConfig.output_dir)
    parser.add_argument("--cache-path", default=BolognaHybridConfig.cache_path)
    parser.add_argument("--window-size", type=int, default=BolognaHybridConfig.window_size)
    parser.add_argument("--tile-size", type=int, default=BolognaHybridConfig.tile_size)
    parser.add_argument("--tile-stride", type=int, default=BolognaHybridConfig.tile_stride)
    parser.add_argument("--batch-size", type=int, default=BolognaHybridConfig.batch_size)
    parser.add_argument("--num-workers", type=int, default=BolognaHybridConfig.num_workers)
    parser.add_argument("--eval-num-workers", type=int, default=BolognaHybridConfig.eval_num_workers)
    parser.add_argument("--device", default=BolognaHybridConfig.device, help="auto, cpu, cuda, or cuda:N")
    parser.add_argument("--cpu-threads", type=int, default=BolognaHybridConfig.cpu_threads)
    parser.add_argument("--pin-memory", action="store_true")
    parser.add_argument("--data-parallel", action="store_true")
    parser.add_argument("--gpu-ids", default=BolognaHybridConfig.gpu_ids, help="Comma-separated CUDA ids, e.g. 0,1")
    parser.add_argument("--max-epochs", type=int, default=BolognaHybridConfig.max_epochs)
    parser.add_argument("--learning-rate", type=float, default=BolognaHybridConfig.learning_rate)
    parser.add_argument("--lambda-phys", type=float, default=BolognaHybridConfig.lambda_phys)
    parser.add_argument("--sg-weight", type=float, default=BolognaHybridConfig.sg_weight)
    parser.add_argument("--target-mode", choices=["raw", "anomaly"], default=BolognaHybridConfig.target_mode)
    parser.add_argument("--force-rebuild-cache", action="store_true")
    args = parser.parse_args()

    cfg = BolognaHybridConfig()
    cfg.output_dir = args.output_dir
    cfg.cache_path = args.cache_path
    cfg.window_size = args.window_size
    cfg.tile_size = args.tile_size
    cfg.tile_stride = args.tile_stride
    cfg.batch_size = args.batch_size
    cfg.num_workers = args.num_workers
    cfg.eval_num_workers = args.eval_num_workers
    cfg.device = args.device
    cfg.cpu_threads = args.cpu_threads
    cfg.pin_memory = args.pin_memory
    cfg.data_parallel = args.data_parallel
    cfg.gpu_ids = args.gpu_ids
    cfg.max_epochs = args.max_epochs
    cfg.learning_rate = args.learning_rate
    cfg.lambda_phys = args.lambda_phys
    cfg.sg_weight = args.sg_weight
    cfg.target_mode = args.target_mode
    cfg.force_rebuild_cache = args.force_rebuild_cache
    return cfg


def train_hybrid(cfg: BolognaHybridConfig) -> dict:
    out_dir = Path(cfg.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    set_seed(cfg.seed)
    maybe_set_cpu_threads(cfg)
    runtime_device = resolve_device(cfg.device)
    gpu_ids = parse_gpu_ids(cfg.gpu_ids)
    physics_cfg = PhysicsConfig()

    cache_path = prepare_bologna_cache(cfg, force=cfg.force_rebuild_cache)
    print("Using cache:", cache_path)
    base_ds = BolognaAlignedWindowDataset(cfg)
    train_idx = base_ds.split_indices("train")
    val_idx = base_ds.split_indices("val")
    test_idx = base_ds.split_indices("test")
    stats = compute_stats(base_ds, train_idx, cfg.max_stats_samples)
    split_coverage = {
        "train": summarize_valid_pixel_coverage(base_ds, train_idx),
        "val": summarize_valid_pixel_coverage(base_ds, val_idx),
        "test": summarize_valid_pixel_coverage(base_ds, test_idx),
    }

    train_ds = NormalizedSubsetDataset(base_ds, train_idx, stats)
    val_ds = NormalizedSubsetDataset(base_ds, val_idx, stats)
    test_ds = NormalizedSubsetDataset(base_ds, test_idx, stats)

    train_loader = DataLoader(
        train_ds,
        batch_size=cfg.batch_size,
        shuffle=True,
        num_workers=cfg.num_workers,
        pin_memory=cfg.pin_memory,
    )
    val_loader = DataLoader(
        val_ds,
        batch_size=cfg.batch_size,
        shuffle=False,
        num_workers=cfg.num_workers,
        pin_memory=cfg.pin_memory,
    )

    model = build_model(cfg).to(runtime_device)
    used_data_parallel = False
    if cfg.data_parallel:
        if not runtime_device.startswith("cuda"):
            raise RuntimeError("data_parallel=True requires a CUDA device.")
        if not gpu_ids:
            gpu_ids = list(range(torch.cuda.device_count()))
        if len(gpu_ids) < 2:
            raise RuntimeError("data_parallel=True requires at least 2 CUDA device ids.")
        model = torch.nn.DataParallel(model, device_ids=gpu_ids)
        used_data_parallel = True
    optimizer = torch.optim.AdamW(
        model.parameters(),
        lr=cfg.learning_rate,
        weight_decay=cfg.weight_decay,
    )
    g_load_fft, g_poro_fft = build_fft_kernels(cfg.tile_size, cfg.tile_size, physics_cfg, runtime_device)

    best_val = float("inf")
    best_state = None
    wait = 0
    history: list[dict[str, float]] = []

    for epoch in range(cfg.max_epochs):
        train_metrics = run_epoch(
            model,
            train_loader,
            optimizer,
            g_load_fft,
            g_poro_fft,
            stats,
            cfg,
            physics_cfg,
            runtime_device,
        )
        val_metrics = run_epoch(
            model,
            val_loader,
            None,
            g_load_fft,
            g_poro_fft,
            stats,
            cfg,
            physics_cfg,
            runtime_device,
        )
        row = {"epoch": epoch + 1}
        row.update({f"train_{k}": v for k, v in train_metrics.items()})
        row.update({f"val_{k}": v for k, v in val_metrics.items()})
        history.append(row)
        print(
            f"Epoch {epoch + 1:02d} | "
            f"train={train_metrics['loss']:.4f} "
            f"(load={train_metrics['loss_load']:.4f}, sg={train_metrics['loss_sg']:.4f}, phys={train_metrics['loss_phys']:.4f}) | "
            f"val={val_metrics['loss']:.4f}"
        )

        if val_metrics["loss"] < best_val:
            best_val = val_metrics["loss"]
            best_state = copy.deepcopy(model.state_dict())
            wait = 0
        else:
            wait += 1
            if wait >= cfg.patience:
                print(f"Early stopping at epoch {epoch + 1}; best val={best_val:.4f}")
                break

    if best_state is not None:
        model.load_state_dict(best_state)

    test_metrics = evaluate_test_split(
        model,
        test_ds,
        stats,
        g_load_fft,
        g_poro_fft,
        physics_cfg,
        cfg,
        runtime_device,
    )

    history_path = out_dir / "bologna_hybrid_sg_history.json"
    summary_path = out_dir / "bologna_hybrid_sg_summary.json"
    ckpt_path = out_dir / "bologna_hybrid_sg_best.pt"
    history_path.write_text(json.dumps(history, indent=2))
    model_state = model.module.state_dict() if isinstance(model, torch.nn.DataParallel) else model.state_dict()
    torch.save(model_state, ckpt_path)

    summary = {
        "device": runtime_device,
        "best_val_loss": best_val,
        "train_samples": len(train_ds),
        "val_samples": len(val_ds),
        "test_samples": len(test_ds),
        "crop": {
            "y0": base_ds.crop[0],
            "y1": base_ds.crop[1],
            "x0": base_ds.crop[2],
            "x1": base_ds.crop[3],
            "height": base_ds.crop_h,
            "width": base_ds.crop_w,
        },
        "tile_grid": {
            "tile_size": cfg.tile_size,
            "tile_stride": cfg.tile_stride,
            "n_tile_y": len(base_ds.tile_y),
            "n_tile_x": len(base_ds.tile_x),
        },
        "normalization": to_jsonable_stats(stats),
        "model": {
            "type": "ContextConditionedTwoLayerSwinUNet3D",
            "context_channels": 2,
            "inputs": ["deformation_window", "temporal_coherence", "avg_spatial_coherence"],
            "targets": ["load_proxy", "Sg"],
            "data_parallel": used_data_parallel,
            "gpu_ids": gpu_ids,
        },
        "runtime": {
            "device": runtime_device,
            "torch_num_threads": torch.get_num_threads(),
            "torch_num_interop_threads": torch.get_num_interop_threads() if hasattr(torch, "get_num_interop_threads") else None,
            "pin_memory": cfg.pin_memory,
            "train_num_workers": cfg.num_workers,
            "eval_num_workers": cfg.eval_num_workers,
        },
        "physics": {
            "load_proxy_definition": "S0 + Ss + Sd + Sr",
            "forward_model": "forward_two_layer_torch",
            "lambda_phys": cfg.lambda_phys,
        },
        "metrics": test_metrics,
        "split_coverage": split_coverage,
        "config": asdict(cfg),
        "artifacts": {
            "history_json": str(history_path),
            "summary_json": str(summary_path),
            "checkpoint": str(ckpt_path),
        },
    }
    summary_path.write_text(json.dumps(summary, indent=2))

    print("\nTest metrics")
    for key, value in test_metrics.items():
        print(f"{key}: {value}")
    print("\nArtifacts")
    print(summary_path)
    print(history_path)
    print(ckpt_path)
    return summary


def main() -> None:
    cfg = parse_args()
    train_hybrid(cfg)


if __name__ == "__main__":
    main()
