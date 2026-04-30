#!/usr/bin/env python3
"""Synthetic Stage 2 residual learning on top of the pure Stage 1 prior."""

from __future__ import annotations

import argparse
import json
import math
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np

try:
    import torch
    from torch.utils.data import DataLoader, Dataset
except ModuleNotFoundError as exc:
    raise SystemExit("This script requires PyTorch in the active environment.") from exc


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from insar_mcmc.stage1_pure_mcmc import (  # noqa: E402
    LAYER_NAMES,
    Stage1PureConfig,
    gibbs_per_grid,
    make_synthetic_layers,
    make_synthetic_observation,
    make_theta_truth,
)
from punjab.punjab_inversion.metrics import anisotropic_total_variation, corr_np, r2_score_np, rmse  # noqa: E402
from punjab.punjab_inversion.models import ContextConditionedResidualSwinUNet3D  # noqa: E402
from punjab.punjab_inversion.physics import (  # noqa: E402
    PhysicsConfig,
    build_fft_kernels,
    forward_five_layer_total_numpy,
    forward_physics_torch,
    set_seed,
)


DEVICE = "cuda" if torch.cuda.is_available() else "cpu"


@dataclass
class Stage2SyntheticConfig:
    output_dir: str = "/home/ubuntu/work/insar_mcmc/outputs_stage2_synthetic"
    seed: int = 42
    device: str = "auto"
    time_steps: int = 24
    height: int = 16
    width: int = 16
    tile_size: int = 8
    tile_stride: int = 8
    window_size: int = 6
    noise_scale: float = 0.05
    noise_mode: str = "punjab"
    stage1_n_iter: int = 40
    stage1_burn: int = 15
    batch_size: int = 4
    max_epochs: int = 20
    patience: int = 5
    learning_rate: float = 2e-4
    weight_decay: float = 1e-4
    base_dim: int = 16
    time_patch: int = 2
    spatial_patch: int = 4
    num_heads: int = 4
    window_attn_t: int = 3
    window_attn_xy: int = 4
    lambda_state: float = 1.0
    lambda_phys: float = 0.5
    lambda_prior: float = 1e-3
    lambda_tv: float = 1e-4
    train_fraction: float = 0.65
    val_fraction: float = 0.20


def resolve_device(name: str) -> str:
    if name == "auto":
        return "cuda" if torch.cuda.is_available() else "cpu"
    return name


def masked_mse(pred: torch.Tensor, target: torch.Tensor, mask: torch.Tensor) -> torch.Tensor:
    weight = mask.to(dtype=pred.dtype)
    denom = weight.sum().clamp_min(1.0)
    return ((pred - target).square() * weight).sum() / denom


class Stage2SyntheticDataset(Dataset):
    def __init__(
        self,
        y_obs: np.ndarray,
        x_prior: np.ndarray,
        x_true: np.ndarray,
        window_size: int,
        tile_size: int,
        tile_stride: int,
    ):
        self.samples: list[tuple[int, int, int]] = []
        self.y_obs = y_obs.astype(np.float32)
        self.x_prior = x_prior.astype(np.float32)
        self.x_true = x_true.astype(np.float32)
        self.residual_true = (x_true - x_prior).astype(np.float32)
        self.window_size = window_size
        self.tile_size = tile_size

        _, _, h, w = x_true.shape
        y_positions = list(range(0, h - tile_size + 1, tile_stride))
        x_positions = list(range(0, w - tile_size + 1, tile_stride))
        if y_positions[-1] != h - tile_size:
            y_positions.append(h - tile_size)
        if x_positions[-1] != w - tile_size:
            x_positions.append(w - tile_size)

        for end_idx in range(window_size - 1, y_obs.shape[0]):
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
        prior_window = self.x_prior[start_idx : end_idx + 1, :, y0:y1, x0:x1].transpose(1, 0, 2, 3)
        x_in = np.concatenate([disp_window, prior_window], axis=0)

        residual = self.residual_true[end_idx, :, y0:y1, x0:x1]
        x_prior_last = self.x_prior[end_idx, :, y0:y1, x0:x1]
        x_true_last = self.x_true[end_idx, :, y0:y1, x0:x1]
        u_last = self.y_obs[end_idx, y0:y1, x0:x1][None, ...]
        mask = np.ones((1, self.tile_size, self.tile_size), dtype=np.float32)

        return (
            torch.tensor(x_in, dtype=torch.float32),
            torch.tensor(residual, dtype=torch.float32),
            torch.tensor(x_prior_last, dtype=torch.float32),
            torch.tensor(x_true_last, dtype=torch.float32),
            torch.tensor(u_last, dtype=torch.float32),
            torch.tensor(mask, dtype=torch.float32),
        )


@dataclass
class Stage2Stats:
    x_mean: torch.Tensor
    x_std: torch.Tensor
    y_mean: torch.Tensor
    y_std: torch.Tensor


def compute_stats(ds: Dataset, indices: list[int]) -> Stage2Stats:
    x_sum = None
    x_sq = None
    x_count = 0.0
    y_sum = None
    y_sq = None
    y_count = 0.0

    for idx in indices:
        x_in, residual, *_ = ds[idx]
        x_np = x_in.numpy()
        y_np = residual.numpy()

        if x_sum is None:
            x_sum = x_np.sum(axis=(1, 2, 3))
            x_sq = np.square(x_np).sum(axis=(1, 2, 3))
            y_sum = y_np.sum(axis=(1, 2))
            y_sq = np.square(y_np).sum(axis=(1, 2))
        else:
            x_sum += x_np.sum(axis=(1, 2, 3))
            x_sq += np.square(x_np).sum(axis=(1, 2, 3))
            y_sum += y_np.sum(axis=(1, 2))
            y_sq += np.square(y_np).sum(axis=(1, 2))

        x_count += float(np.prod(x_np.shape[1:]))
        y_count += float(np.prod(y_np.shape[1:]))

    x_mean = x_sum / max(x_count, 1.0)
    x_var = x_sq / max(x_count, 1.0) - np.square(x_mean)
    y_mean = y_sum / max(y_count, 1.0)
    y_var = y_sq / max(y_count, 1.0) - np.square(y_mean)

    return Stage2Stats(
        x_mean=torch.tensor(x_mean[:, None, None, None], dtype=torch.float32),
        x_std=torch.tensor(np.sqrt(np.maximum(x_var, 1e-6))[:, None, None, None], dtype=torch.float32),
        y_mean=torch.tensor(y_mean[:, None, None], dtype=torch.float32),
        y_std=torch.tensor(np.sqrt(np.maximum(y_var, 1e-6))[:, None, None], dtype=torch.float32),
    )


class NormalizedSubset(Dataset):
    def __init__(self, base: Stage2SyntheticDataset, indices: list[int], stats: Stage2Stats):
        self.base = base
        self.indices = list(indices)
        self.stats = stats

    def __len__(self) -> int:
        return len(self.indices)

    def __getitem__(self, idx: int):
        x_in, residual, x_prior_last, x_true_last, u_last, mask = self.base[self.indices[idx]]
        x_in = (x_in - self.stats.x_mean) / self.stats.x_std
        residual = (residual - self.stats.y_mean) / self.stats.y_std
        return x_in, residual, x_prior_last, x_true_last, u_last, mask


def build_model(cfg: Stage2SyntheticConfig) -> ContextConditionedResidualSwinUNet3D:
    return ContextConditionedResidualSwinUNet3D(
        in_channels=1 + len(LAYER_NAMES),
        out_channels=len(LAYER_NAMES),
        base_dim=cfg.base_dim,
        time_patch=cfg.time_patch,
        spatial_patch=cfg.spatial_patch,
        num_heads=cfg.num_heads,
        window_size=(cfg.window_attn_t, cfg.window_attn_xy, cfg.window_attn_xy),
    )


def denormalize_field(x: torch.Tensor, mean: torch.Tensor, std: torch.Tensor) -> torch.Tensor:
    return x * std + mean


def run_epoch(
    model: ContextConditionedResidualSwinUNet3D,
    loader: DataLoader,
    optimizer: torch.optim.Optimizer | None,
    stats: Stage2Stats,
    g_load_fft: torch.Tensor,
    g_poro_fft: torch.Tensor,
    physics: PhysicsConfig,
    cfg: Stage2SyntheticConfig,
    device: str,
) -> dict[str, float]:
    train = optimizer is not None
    model.train() if train else model.eval()
    running = {"loss": 0.0, "loss_res": 0.0, "loss_state": 0.0, "loss_phys": 0.0, "loss_prior": 0.0}
    n = 0

    y_mean = stats.y_mean.to(device)[None, ...]
    y_std = stats.y_std.to(device)[None, ...]

    for xb, yb, xprior_b, xtrue_b, ub, mask in loader:
        xb = xb.to(device)
        yb = yb.to(device)
        xprior_b = xprior_b.to(device)
        xtrue_b = xtrue_b.to(device)
        ub = ub.to(device)
        mask = mask.to(device)

        with torch.set_grad_enabled(train):
            res_norm = model(xb)
            loss_res = masked_mse(res_norm, yb, mask)
            res_raw = denormalize_field(res_norm, y_mean, y_std)
            x_final = xprior_b + res_raw
            loss_state = masked_mse(x_final, xtrue_b, mask)
            d_hat = forward_physics_torch(
                x_final,
                g_load_fft,
                g_poro_fft,
                physics,
                sg_index=3,
                load_indices=(0, 1, 2, 4),
            )
            loss_phys = masked_mse(d_hat, ub, mask)
            loss_prior = res_raw.square().mean() + cfg.lambda_tv * anisotropic_total_variation(x_final)
            loss = loss_res + cfg.lambda_state * loss_state + cfg.lambda_phys * loss_phys + cfg.lambda_prior * loss_prior

            if train:
                optimizer.zero_grad()
                loss.backward()
                optimizer.step()

        bsz = xb.shape[0]
        n += bsz
        running["loss"] += float(loss.item()) * bsz
        running["loss_res"] += float(loss_res.item()) * bsz
        running["loss_state"] += float(loss_state.item()) * bsz
        running["loss_phys"] += float(loss_phys.item()) * bsz
        running["loss_prior"] += float(loss_prior.item()) * bsz

    return {k: v / max(n, 1) for k, v in running.items()}


def evaluate(
    model: ContextConditionedResidualSwinUNet3D,
    loader: DataLoader,
    stats: Stage2Stats,
    g_load_fft: torch.Tensor,
    g_poro_fft: torch.Tensor,
    physics: PhysicsConfig,
    device: str,
) -> dict[str, float]:
    y_mean = stats.y_mean.to(device)[None, ...]
    y_std = stats.y_std.to(device)[None, ...]
    model.eval()

    xprior_all, xtrue_all, xfinal_all = [], [], []
    u_true_all, u_prior_all, u_pred_all = [], [], []

    with torch.no_grad():
        for xb, _, xprior_b, xtrue_b, ub, mask in loader:
            xb = xb.to(device)
            xprior_b = xprior_b.to(device)
            xtrue_b = xtrue_b.to(device)
            ub = ub.to(device)
            mask = mask.to(device)

            res_norm = model(xb)
            res_raw = denormalize_field(res_norm, y_mean, y_std)
            x_final = xprior_b + res_raw
            d_prior = forward_physics_torch(
                xprior_b,
                g_load_fft,
                g_poro_fft,
                physics,
                sg_index=3,
                load_indices=(0, 1, 2, 4),
            )
            d_hat = forward_physics_torch(
                x_final,
                g_load_fft,
                g_poro_fft,
                physics,
                sg_index=3,
                load_indices=(0, 1, 2, 4),
            )

            mask_np = mask.cpu().numpy().astype(bool)
            xprior_np = xprior_b.cpu().numpy()
            xtrue_np = xtrue_b.cpu().numpy()
            xfinal_np = x_final.cpu().numpy()
            ub_np = ub.cpu().numpy()
            d_prior_np = d_prior.cpu().numpy()
            d_hat_np = d_hat.cpu().numpy()

            for i in range(xfinal_np.shape[0]):
                valid = mask_np[i, 0]
                for arr, store in [
                    (xprior_np[i], xprior_all),
                    (xtrue_np[i], xtrue_all),
                    (xfinal_np[i], xfinal_all),
                ]:
                    store.append(arr[:, valid])
                u_true_all.append(ub_np[i, 0][valid])
                u_prior_all.append(d_prior_np[i, 0][valid])
                u_pred_all.append(d_hat_np[i, 0][valid])

    stack = lambda parts: np.concatenate(parts, axis=-1) if parts else np.zeros((len(LAYER_NAMES), 0), dtype=np.float32)
    xprior_f = stack(xprior_all)
    xtrue_f = stack(xtrue_all)
    xfinal_f = stack(xfinal_all)
    u_true_f = np.concatenate(u_true_all) if u_true_all else np.array([], dtype=np.float32)
    u_prior_f = np.concatenate(u_prior_all) if u_prior_all else np.array([], dtype=np.float32)
    u_pred_f = np.concatenate(u_pred_all) if u_pred_all else np.array([], dtype=np.float32)

    metrics: dict[str, float] = {}
    for k, name in enumerate(LAYER_NAMES):
        metrics[f"{name}_prior_r2"] = r2_score_np(xtrue_f[k], xprior_f[k])
        metrics[f"{name}_final_r2"] = r2_score_np(xtrue_f[k], xfinal_f[k])
        metrics[f"{name}_prior_corr"] = corr_np(xtrue_f[k], xprior_f[k])
        metrics[f"{name}_final_corr"] = corr_np(xtrue_f[k], xfinal_f[k])

    metrics["Load_total_prior_r2"] = r2_score_np(xtrue_f[[0, 1, 2, 4]].sum(axis=0), xprior_f[[0, 1, 2, 4]].sum(axis=0))
    metrics["Load_total_final_r2"] = r2_score_np(xtrue_f[[0, 1, 2, 4]].sum(axis=0), xfinal_f[[0, 1, 2, 4]].sum(axis=0))
    metrics["TWS_prior_r2"] = r2_score_np(xtrue_f.sum(axis=0), xprior_f.sum(axis=0))
    metrics["TWS_final_r2"] = r2_score_np(xtrue_f.sum(axis=0), xfinal_f.sum(axis=0))
    metrics["disp_prior_r2"] = r2_score_np(u_true_f, u_prior_f)
    metrics["disp_final_r2"] = r2_score_np(u_true_f, u_pred_f)
    metrics["disp_prior_corr"] = corr_np(u_true_f, u_prior_f)
    metrics["disp_final_corr"] = corr_np(u_true_f, u_pred_f)
    metrics["disp_prior_rmse"] = rmse(u_true_f, u_prior_f)
    metrics["disp_final_rmse"] = rmse(u_true_f, u_pred_f)
    return metrics


def reconstruct_full_state(
    model: ContextConditionedResidualSwinUNet3D,
    ds: Stage2SyntheticDataset,
    stats: Stage2Stats,
    cfg: Stage2SyntheticConfig,
    device: str,
) -> np.ndarray:
    t_steps, k_dim, h, w = ds.x_true.shape
    x_final_sum = np.zeros((t_steps, k_dim, h, w), dtype=np.float32)
    x_final_count = np.zeros((t_steps, 1, h, w), dtype=np.float32)

    x_mean = stats.x_mean.to(device)
    x_std = stats.x_std.to(device)
    y_mean = stats.y_mean.to(device)[None, ...]
    y_std = stats.y_std.to(device)[None, ...]

    model.eval()
    with torch.no_grad():
        for idx, (end_idx, y0, x0) in enumerate(ds.samples):
            x_in, _, x_prior_last, _, _, _ = ds[idx]
            xb = ((x_in.to(device) - x_mean) / x_std).unsqueeze(0)
            x_prior_last = x_prior_last.to(device).unsqueeze(0)
            res_norm = model(xb)
            res_raw = denormalize_field(res_norm, y_mean, y_std)
            x_final_tile = (x_prior_last + res_raw).squeeze(0).cpu().numpy()

            y1 = y0 + cfg.tile_size
            x1 = x0 + cfg.tile_size
            x_final_sum[end_idx, :, y0:y1, x0:x1] += x_final_tile
            x_final_count[end_idx, :, y0:y1, x0:x1] += 1.0

    denom = np.maximum(np.repeat(x_final_count, k_dim, axis=1), 1.0)
    x_avg = x_final_sum / denom
    x_final = np.where(np.repeat(x_final_count > 0, k_dim, axis=1), x_avg, ds.x_prior)
    return x_final.astype(np.float32)


def run_stage2(cfg: Stage2SyntheticConfig) -> dict:
    set_seed(cfg.seed)
    device = resolve_device(cfg.device)
    physics = PhysicsConfig()

    stage1_cfg = Stage1PureConfig(
        seed=cfg.seed,
        time_steps=cfg.time_steps,
        height=cfg.height,
        width=cfg.width,
        noise_scale=cfg.noise_scale,
        noise_mode=cfg.noise_mode,
        n_iter=cfg.stage1_n_iter,
        burn=cfg.stage1_burn,
    )

    z_layers = make_synthetic_layers(stage1_cfg)
    theta_true = make_theta_truth(stage1_cfg)
    x_true = theta_true * z_layers
    z_components, _, y_obs = make_synthetic_observation(
        z_layers=z_layers,
        theta_true=theta_true,
        physics=physics,
        noise_scale=cfg.noise_scale,
        noise_mode=cfg.noise_mode,
        seed=cfg.seed,
    )

    t_steps, k_dim, h, w = z_layers.shape
    n_pixels = h * w
    y_flat = y_obs.reshape(t_steps, n_pixels)
    z_flat = z_components.reshape(t_steps, k_dim, n_pixels).transpose(0, 2, 1)
    m0 = np.ones(k_dim, dtype=np.float32)
    p0 = 0.25 * np.eye(k_dim, dtype=np.float32)
    q0 = 0.01 * np.eye(k_dim, dtype=np.float32)
    theta_hat, q_hat, r_hat = gibbs_per_grid(
        y=y_flat,
        z=z_flat,
        n_iter=cfg.stage1_n_iter,
        burn=cfg.stage1_burn,
        m0=m0,
        p0=p0,
        q0=q0,
        nu0=k_dim + 2,
        r0=1e-4,
    )
    x_prior = (theta_hat * z_layers.reshape(t_steps, k_dim, n_pixels).transpose(0, 2, 1)).transpose(0, 2, 1).reshape(t_steps, k_dim, h, w)

    ds = Stage2SyntheticDataset(
        y_obs=y_obs,
        x_prior=x_prior,
        x_true=x_true,
        window_size=cfg.window_size,
        tile_size=cfg.tile_size,
        tile_stride=cfg.tile_stride,
    )
    n_total = len(ds)
    n_train = max(1, int(cfg.train_fraction * n_total))
    n_val = max(1, int(cfg.val_fraction * n_total))
    n_test = max(1, n_total - n_train - n_val)
    indices = list(range(n_total))
    train_idx = indices[:n_train]
    val_idx = indices[n_train : n_train + n_val]
    test_idx = indices[n_train + n_val : n_train + n_val + n_test]

    stats = compute_stats(ds, train_idx)
    train_ds = NormalizedSubset(ds, train_idx, stats)
    val_ds = NormalizedSubset(ds, val_idx, stats)
    test_ds = NormalizedSubset(ds, test_idx, stats)

    train_loader = DataLoader(train_ds, batch_size=cfg.batch_size, shuffle=True)
    val_loader = DataLoader(val_ds, batch_size=cfg.batch_size, shuffle=False)
    test_loader = DataLoader(test_ds, batch_size=cfg.batch_size, shuffle=False)

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
            f"[epoch {epoch:02d}] "
            f"train={train_metrics['loss']:.4f} "
            f"(res={train_metrics['loss_res']:.4f}, state={train_metrics['loss_state']:.4f}, phys={train_metrics['loss_phys']:.4f}) | "
            f"val={val_metrics['loss']:.4f}"
        )

        if val_metrics["loss"] < best_val:
            best_val = val_metrics["loss"]
            best_state = {k: v.cpu().clone() for k, v in model.state_dict().items()}
            patience_left = cfg.patience
        else:
            patience_left -= 1
            if patience_left <= 0:
                print(f"Early stopping at epoch {epoch}.")
                break

    if best_state is not None:
        model.load_state_dict(best_state)

    test_metrics = evaluate(model, test_loader, stats, g_load_fft, g_poro_fft, physics, device)
    x_final = reconstruct_full_state(model, ds, stats, cfg, device)
    d_prior = forward_five_layer_total_numpy(x_prior, physics=physics, sg_index=3, load_indices=(0, 1, 2, 4))
    d_final = forward_five_layer_total_numpy(x_final, physics=physics, sg_index=3, load_indices=(0, 1, 2, 4))
    out_dir = Path(cfg.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    torch.save(model.state_dict(), out_dir / "stage2_residual_best.pt")
    (out_dir / "stage2_residual_history.json").write_text(json.dumps(history, indent=2))
    np.savez_compressed(
        out_dir / "stage2_residual_results.npz",
        z_layers=z_layers,
        theta_true=theta_true,
        x_true=x_true,
        x_prior=x_prior,
        x_final=x_final,
        y_obs=y_obs,
        d_prior=d_prior,
        d_final=d_final,
        q_hat=q_hat,
        r_hat=np.array(r_hat, dtype=np.float32),
    )

    summary = {
        "config": asdict(cfg),
        "runtime_device": device,
        "n_samples": {"train": len(train_ds), "val": len(val_ds), "test": len(test_ds)},
        "stage1_posterior": {
            "Q_hat_diag": np.diag(q_hat).astype(float).tolist(),
            "R_hat": float(r_hat),
        },
        "best_val_loss": best_val,
        "test_metrics": test_metrics,
    }
    (out_dir / "stage2_residual_summary.json").write_text(json.dumps(summary, indent=2))
    return summary


def parse_args() -> Stage2SyntheticConfig:
    parser = argparse.ArgumentParser(description="Train Stage 2 residual Swin on synthetic Stage 1 priors.")
    parser.add_argument("--output-dir", default=Stage2SyntheticConfig.output_dir)
    parser.add_argument("--device", default=Stage2SyntheticConfig.device)
    parser.add_argument("--time-steps", type=int, default=Stage2SyntheticConfig.time_steps)
    parser.add_argument("--height", type=int, default=Stage2SyntheticConfig.height)
    parser.add_argument("--width", type=int, default=Stage2SyntheticConfig.width)
    parser.add_argument("--tile-size", type=int, default=Stage2SyntheticConfig.tile_size)
    parser.add_argument("--tile-stride", type=int, default=Stage2SyntheticConfig.tile_stride)
    parser.add_argument("--window-size", type=int, default=Stage2SyntheticConfig.window_size)
    parser.add_argument("--noise-scale", type=float, default=Stage2SyntheticConfig.noise_scale)
    parser.add_argument("--noise-mode", default=Stage2SyntheticConfig.noise_mode)
    parser.add_argument("--stage1-n-iter", type=int, default=Stage2SyntheticConfig.stage1_n_iter)
    parser.add_argument("--stage1-burn", type=int, default=Stage2SyntheticConfig.stage1_burn)
    parser.add_argument("--batch-size", type=int, default=Stage2SyntheticConfig.batch_size)
    parser.add_argument("--max-epochs", type=int, default=Stage2SyntheticConfig.max_epochs)
    parser.add_argument("--patience", type=int, default=Stage2SyntheticConfig.patience)
    parser.add_argument("--learning-rate", type=float, default=Stage2SyntheticConfig.learning_rate)
    parser.add_argument("--base-dim", type=int, default=Stage2SyntheticConfig.base_dim)
    args = parser.parse_args()
    return Stage2SyntheticConfig(
        output_dir=args.output_dir,
        device=args.device,
        time_steps=args.time_steps,
        height=args.height,
        width=args.width,
        tile_size=args.tile_size,
        tile_stride=args.tile_stride,
        window_size=args.window_size,
        noise_scale=args.noise_scale,
        noise_mode=args.noise_mode,
        stage1_n_iter=args.stage1_n_iter,
        stage1_burn=args.stage1_burn,
        batch_size=args.batch_size,
        max_epochs=args.max_epochs,
        patience=args.patience,
        learning_rate=args.learning_rate,
        base_dim=args.base_dim,
    )


def main() -> None:
    cfg = parse_args()
    summary = run_stage2(cfg)
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
