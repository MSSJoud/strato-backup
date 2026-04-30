#!/usr/bin/env python3
"""Pure Stage 1 deformation-space MCMC on synthetic 5-layer data.

This script implements the unconstrained Stage 1 model only:

    Y_t,p = Z_t,p theta_t,p + eps_t,p
    theta_t,p = theta_{t-1,p} + eta_t,p

where:
- Y is synthetic deformation
- Z is the 5-layer forward-converted deformation design matrix
- theta is free in both space and time

No external SWOT / SMAP constraints are used here.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np
from scipy.ndimage import gaussian_filter


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from punjab.punjab_inversion.metrics import corr_np, r2_score_np, rmse  # noqa: E402
from punjab.punjab_inversion.physics import (  # noqa: E402
    PhysicsConfig,
    forward_five_layer_components_numpy,
    set_seed,
)


LAYER_NAMES = ("S0", "Ss", "Sd", "Sg", "Sr")


@dataclass
class Stage1PureConfig:
    output_dir: str = "/home/ubuntu/work/insar_mcmc/outputs_stage1_pure"
    seed: int = 42
    time_steps: int = 36
    height: int = 16
    width: int = 16
    noise_scale: float = 0.0
    noise_mode: str = "punjab"
    theta_base: float = 1.0
    theta_variation_scale: float = 0.18
    n_iter: int = 80
    burn: int = 30
    q0_scale: float = 0.01
    p0_scale: float = 0.25
    r0: float = 1e-4
    iw_dof_extra: int = 2
    theta_min: float = 0.2
    theta_max: float = 1.8
    temporal_smooth_sigma: float = 1.2
    spatial_large_sigma: float = 3.0
    spatial_small_sigma: float = 1.2


def make_spatial_pattern(rng: np.random.Generator, h: int, w: int, sigma_large: float, sigma_small: float) -> np.ndarray:
    field = 0.7 * gaussian_filter(rng.normal(size=(h, w)), sigma=sigma_large)
    field += 0.3 * gaussian_filter(rng.normal(size=(h, w)), sigma=sigma_small)
    field -= field.mean()
    field /= field.std() + 1e-6
    return field.astype(np.float32)


def make_synthetic_layers(cfg: Stage1PureConfig) -> np.ndarray:
    rng = np.random.default_rng(cfg.seed)
    t = np.arange(cfg.time_steps, dtype=np.float32)

    patterns = {
        name: make_spatial_pattern(
            rng,
            cfg.height,
            cfg.width,
            sigma_large=cfg.spatial_large_sigma + offset,
            sigma_small=cfg.spatial_small_sigma + 0.5 * offset,
        )
        for name, offset in zip(LAYER_NAMES, [0.0, 0.6, 1.2, 1.8, 0.9], strict=True)
    }

    annual = np.sin(2 * np.pi * t / 12.0)
    semi = np.sin(4 * np.pi * t / 12.0)
    interannual = np.sin(2 * np.pi * t / 24.0)
    slow = np.sin(2 * np.pi * t / 36.0)
    trend = (t - t.mean()) / max(t.max(), 1.0)

    s0 = 6.0 * annual[:, None, None] * patterns["S0"] + 1.0 * semi[:, None, None] * patterns["S0"]
    ss = 4.5 * np.sin(2 * np.pi * (t - 1.0) / 12.0)[:, None, None] * patterns["Ss"]
    ss += 1.0 * interannual[:, None, None] * patterns["Ss"]
    sd = 3.0 * np.sin(2 * np.pi * (t - 2.0) / 12.0)[:, None, None] * patterns["Sd"]
    sd += 1.2 * trend[:, None, None] * patterns["Sd"]
    sg = 5.0 * np.sin(2 * np.pi * (t - 4.0) / 18.0)[:, None, None] * patterns["Sg"]
    sg += 4.0 * trend[:, None, None] * patterns["Sg"]
    sr = 2.5 * np.sin(2 * np.pi * (t - 1.5) / 9.0)[:, None, None] * patterns["Sr"]
    sr += 0.8 * slow[:, None, None] * patterns["Sr"]

    layers = np.stack([s0, ss, sd, sg, sr], axis=1).astype(np.float32)
    layers += 0.15 * gaussian_filter(rng.normal(size=layers.shape), sigma=(0, 0, 1, 1)).astype(np.float32)
    return layers


def make_theta_truth(cfg: Stage1PureConfig) -> np.ndarray:
    rng = np.random.default_rng(cfg.seed + 17)
    t = np.arange(cfg.time_steps, dtype=np.float32)
    theta = np.empty((cfg.time_steps, len(LAYER_NAMES), cfg.height, cfg.width), dtype=np.float32)

    for k, name in enumerate(LAYER_NAMES):
        spatial = make_spatial_pattern(
            rng,
            cfg.height,
            cfg.width,
            sigma_large=cfg.spatial_large_sigma + 0.4 * k,
            sigma_small=cfg.spatial_small_sigma + 0.2 * k,
        )
        temporal = np.sin(2 * np.pi * (t - 0.8 * k) / (10.0 + 2.0 * k))
        temporal += 0.35 * np.cos(2 * np.pi * t / (18.0 + k))
        raw = cfg.theta_base + cfg.theta_variation_scale * temporal[:, None, None] * spatial[None, :, :]
        raw = gaussian_filter(raw, sigma=(cfg.temporal_smooth_sigma, 0.8, 0.8))
        theta[:, k] = np.clip(raw, cfg.theta_min, cfg.theta_max)

    return theta.astype(np.float32)


def make_synthetic_observation(
    z_layers: np.ndarray,
    theta_true: np.ndarray,
    physics: PhysicsConfig,
    noise_scale: float,
    noise_mode: str,
    seed: int,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    z_components = forward_five_layer_components_numpy(z_layers, physics=physics)
    y_clean = np.einsum("tkhw,tkhw->thw", z_components, theta_true).astype(np.float32)

    if noise_scale <= 0.0:
        return z_components, y_clean, y_clean.copy()

    if noise_mode != "punjab":
        raise ValueError(f"Unsupported noise_mode={noise_mode!r}. Use 'punjab'.")

    rng = np.random.default_rng(seed + 101)
    signal_std = max(float(np.std(y_clean)), 1e-6)

    # Punjab-style additive observation corruption:
    # white noise + spatially correlated noise + seasonal bias-like term.
    white = rng.normal(size=y_clean.shape).astype(np.float32)
    white *= (0.40 * noise_scale) * signal_std

    corr = np.zeros_like(y_clean)
    for tt in range(y_clean.shape[0]):
        corr[tt] = 0.05 * make_spatial_pattern(
            rng,
            y_clean.shape[1],
            y_clean.shape[2],
            sigma_large=10.0,
            sigma_small=4.0,
        )
    corr *= (noise_scale / 0.05)

    seasonal = 0.03 * np.sin(2 * np.pi * np.arange(y_clean.shape[0], dtype=np.float32) / 12.0)[:, None, None]
    seasonal = seasonal.astype(np.float32) * (noise_scale / 0.05)

    y_noisy = (y_clean + white + corr + seasonal).astype(np.float32)
    return z_components, y_clean, y_noisy


def invgamma_sample(shape: float, scale: float) -> float:
    return float(scale / np.random.gamma(shape, 1.0))


def iw_sample(scale_matrix: np.ndarray, dof: int) -> np.ndarray:
    k_dim = scale_matrix.shape[0]
    s = 0.5 * (scale_matrix + scale_matrix.T) + 1e-10 * np.eye(k_dim)
    eigvals, eigvecs = np.linalg.eigh(s)
    eigvals = np.maximum(eigvals, 1e-10)
    s_inv_half = (eigvecs * (eigvals ** -0.5)) @ eigvecs.T

    a = np.zeros((k_dim, k_dim), dtype=np.float64)
    for i in range(k_dim):
        a[i, i] = np.sqrt(np.random.chisquare(dof - i))
        for j in range(i):
            a[i, j] = np.random.normal()

    w = s_inv_half @ (a @ a.T) @ s_inv_half.T
    q = np.linalg.pinv(w)
    q = 0.5 * (q + q.T)
    eigvals, eigvecs = np.linalg.eigh(q)
    eigvals = np.maximum(eigvals, 1e-10)
    return (eigvecs * eigvals) @ eigvecs.T


def ffbs_one_pixel(
    y: np.ndarray,
    z: np.ndarray,
    q: np.ndarray,
    r: float,
    m0: np.ndarray,
    p0: np.ndarray,
) -> np.ndarray:
    t_steps, k_dim = z.shape
    pred_mean = np.zeros((t_steps, k_dim), dtype=np.float64)
    pred_cov = np.zeros((t_steps, k_dim, k_dim), dtype=np.float64)
    filt_mean = np.zeros((t_steps, k_dim), dtype=np.float64)
    filt_cov = np.zeros((t_steps, k_dim, k_dim), dtype=np.float64)

    for t in range(t_steps):
        if t == 0:
            pred_mean[t] = m0
            pred_cov[t] = p0
        else:
            pred_mean[t] = filt_mean[t - 1]
            pred_cov[t] = filt_cov[t - 1] + q

        h = z[t][None, :]
        s = float((h @ pred_cov[t] @ h.T).item()) + float(r)
        s = max(s, 1e-8)
        k_gain = (pred_cov[t] @ h.T) / s
        innov = y[t] - float((h @ pred_mean[t]).item())
        filt_mean[t] = pred_mean[t] + k_gain[:, 0] * innov
        filt_cov[t] = pred_cov[t] - np.outer(k_gain[:, 0], h @ pred_cov[t])
        filt_cov[t] = 0.5 * (filt_cov[t] + filt_cov[t].T)
        eigvals, eigvecs = np.linalg.eigh(filt_cov[t])
        eigvals = np.maximum(eigvals, 1e-8)
        filt_cov[t] = (eigvecs * eigvals) @ eigvecs.T

    theta = np.zeros((t_steps, k_dim), dtype=np.float64)
    chol = np.linalg.cholesky(filt_cov[-1] + 1e-8 * np.eye(k_dim))
    theta[-1] = filt_mean[-1] + chol @ np.random.randn(k_dim)

    for t in range(t_steps - 2, -1, -1):
        smoother = filt_cov[t] @ np.linalg.pinv(filt_cov[t] + q)
        mean = filt_mean[t] + smoother @ (theta[t + 1] - filt_mean[t])
        cov = filt_cov[t] - smoother @ filt_cov[t]
        cov = 0.5 * (cov + cov.T)
        eigvals, eigvecs = np.linalg.eigh(cov)
        eigvals = np.maximum(eigvals, 1e-8)
        chol = (eigvecs * np.sqrt(eigvals)) @ eigvecs.T
        theta[t] = mean + chol @ np.random.randn(k_dim)

    return theta.astype(np.float32)


def update_q_from_paths(theta_paths: np.ndarray, q0: np.ndarray, nu0: int) -> np.ndarray:
    _, _, k_dim = theta_paths.shape
    innovations = theta_paths[1:] - theta_paths[:-1]
    innovations = np.nan_to_num(innovations, nan=0.0, posinf=0.0, neginf=0.0)
    s = innovations.reshape(-1, k_dim).T @ innovations.reshape(-1, k_dim)
    s = 0.5 * (s + s.T) + 1e-8 * np.eye(k_dim)
    dof = nu0 + innovations.shape[0] * innovations.shape[1]
    return iw_sample(s + q0, dof).astype(np.float32)


def update_r_from_residuals(theta_paths: np.ndarray, y: np.ndarray, z: np.ndarray, a0: float = 1.0, b0: float = 1.0) -> float:
    y_hat = np.einsum("tpk,tpk->tp", theta_paths, z)
    ss = float(np.sum((y - y_hat) ** 2))
    n_obs = y.size
    return invgamma_sample(a0 + 0.5 * n_obs, b0 + 0.5 * ss)


def gibbs_per_grid(
    y: np.ndarray,
    z: np.ndarray,
    n_iter: int,
    burn: int,
    m0: np.ndarray,
    p0: np.ndarray,
    q0: np.ndarray,
    nu0: int,
    r0: float,
) -> tuple[np.ndarray, np.ndarray, float]:
    t_steps, n_pixels = y.shape
    k_dim = z.shape[2]
    q = q0.astype(np.float32).copy()
    r = float(r0)

    theta_sum = np.zeros((t_steps, n_pixels, k_dim), dtype=np.float64)
    q_sum = np.zeros((k_dim, k_dim), dtype=np.float64)
    r_sum = 0.0
    kept = 0

    for it in range(n_iter):
        theta_paths = np.zeros((t_steps, n_pixels, k_dim), dtype=np.float32)
        for p in range(n_pixels):
            theta_paths[:, p, :] = ffbs_one_pixel(y[:, p], z[:, p, :], q, r, m0, p0)

        q = update_q_from_paths(theta_paths, q0=q0, nu0=nu0)
        r = update_r_from_residuals(theta_paths, y=y, z=z)

        if it >= burn:
            theta_sum += theta_paths
            q_sum += q
            r_sum += r
            kept += 1

        if (it + 1) % 10 == 0 or it == 0:
            print(f"[iter {it + 1:03d}/{n_iter}] kept={kept} r={r:.3e}")

    theta_hat = (theta_sum / max(kept, 1)).astype(np.float32)
    q_hat = (q_sum / max(kept, 1)).astype(np.float32)
    r_hat = float(r_sum / max(kept, 1))
    return theta_hat, q_hat, r_hat


def summarize_layer_metrics(true_field: np.ndarray, pred_field: np.ndarray) -> dict[str, float]:
    return {
        "rmse": rmse(true_field, pred_field),
        "corr": corr_np(true_field, pred_field),
        "r2": r2_score_np(true_field, pred_field),
    }


def run_synthetic_stage1(cfg: Stage1PureConfig) -> dict:
    set_seed(cfg.seed)
    physics = PhysicsConfig()

    z_layers = make_synthetic_layers(cfg)
    theta_true = make_theta_truth(cfg)
    x_true = theta_true * z_layers

    z_components, y_clean, y_obs = make_synthetic_observation(
        z_layers=z_layers,
        theta_true=theta_true,
        physics=physics,
        noise_scale=cfg.noise_scale,
        noise_mode=cfg.noise_mode,
        seed=cfg.seed,
    )

    t_steps, k_dim, height, width = z_layers.shape
    n_pixels = height * width

    y_flat = y_obs.reshape(t_steps, n_pixels)
    z_flat = z_components.reshape(t_steps, k_dim, n_pixels).transpose(0, 2, 1)
    theta_true_flat = theta_true.reshape(t_steps, k_dim, n_pixels).transpose(0, 2, 1)

    m0 = np.ones(k_dim, dtype=np.float32)
    p0 = cfg.p0_scale * np.eye(k_dim, dtype=np.float32)
    q0 = cfg.q0_scale * np.eye(k_dim, dtype=np.float32)
    nu0 = k_dim + cfg.iw_dof_extra

    theta_hat, q_hat, r_hat = gibbs_per_grid(
        y=y_flat,
        z=z_flat,
        n_iter=cfg.n_iter,
        burn=cfg.burn,
        m0=m0,
        p0=p0,
        q0=q0,
        nu0=nu0,
        r0=cfg.r0,
    )

    x_prior_flat = theta_hat * z_layers.reshape(t_steps, k_dim, n_pixels).transpose(0, 2, 1)
    y_hat = np.einsum("tpk,tpk->tp", z_flat, theta_hat).reshape(t_steps, height, width)

    theta_hat_map = theta_hat.transpose(0, 2, 1).reshape(t_steps, k_dim, height, width)
    x_prior = x_prior_flat.transpose(0, 2, 1).reshape(t_steps, k_dim, height, width)

    layer_metrics = {}
    theta_metrics = {}
    for k, name in enumerate(LAYER_NAMES):
        theta_metrics[name] = summarize_layer_metrics(theta_true[:, k], theta_hat_map[:, k])
        layer_metrics[name] = summarize_layer_metrics(x_true[:, k], x_prior[:, k])

    derived_state_metrics = {
        "Load_total": summarize_layer_metrics(
            x_true[:, [0, 1, 2, 4]].sum(axis=1),
            x_prior[:, [0, 1, 2, 4]].sum(axis=1),
        ),
        "TWS": summarize_layer_metrics(
            x_true.sum(axis=1),
            x_prior.sum(axis=1),
        ),
    }

    deformation_metrics = summarize_layer_metrics(y_clean, y_hat)
    deformation_metrics["obs_rmse"] = rmse(y_obs, y_hat)

    summary = {
        "config": asdict(cfg),
        "shape": {
            "time": t_steps,
            "height": height,
            "width": width,
            "pixels": n_pixels,
            "layers": k_dim,
        },
        "theta_metrics": theta_metrics,
        "state_metrics": layer_metrics,
        "derived_state_metrics": derived_state_metrics,
        "deformation_metrics": deformation_metrics,
        "posterior": {
            "Q_hat_diag": np.diag(q_hat).astype(float).tolist(),
            "R_hat": r_hat,
            "theta_mean": float(np.nanmean(theta_hat)),
            "theta_std": float(np.nanstd(theta_hat)),
        },
    }

    out_dir = Path(cfg.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(
        out_dir / "stage1_pure_synthetic_results.npz",
        z_layers=z_layers,
        theta_true=theta_true,
        theta_hat=theta_hat_map,
        x_true=x_true,
        x_prior=x_prior,
        y_clean=y_clean,
        y_obs=y_obs,
        y_hat=y_hat,
        q_hat=q_hat,
        r_hat=np.array(r_hat, dtype=np.float32),
    )
    (out_dir / "stage1_pure_synthetic_summary.json").write_text(json.dumps(summary, indent=2))
    return summary


def parse_args() -> Stage1PureConfig:
    parser = argparse.ArgumentParser(description="Run pure Stage 1 deformation-space MCMC on synthetic data.")
    parser.add_argument("--output-dir", default=Stage1PureConfig.output_dir)
    parser.add_argument("--seed", type=int, default=Stage1PureConfig.seed)
    parser.add_argument("--time-steps", type=int, default=Stage1PureConfig.time_steps)
    parser.add_argument("--height", type=int, default=Stage1PureConfig.height)
    parser.add_argument("--width", type=int, default=Stage1PureConfig.width)
    parser.add_argument("--noise-scale", type=float, default=Stage1PureConfig.noise_scale)
    parser.add_argument("--noise-mode", default=Stage1PureConfig.noise_mode)
    parser.add_argument("--theta-variation-scale", type=float, default=Stage1PureConfig.theta_variation_scale)
    parser.add_argument("--n-iter", type=int, default=Stage1PureConfig.n_iter)
    parser.add_argument("--burn", type=int, default=Stage1PureConfig.burn)
    parser.add_argument("--q0-scale", type=float, default=Stage1PureConfig.q0_scale)
    parser.add_argument("--p0-scale", type=float, default=Stage1PureConfig.p0_scale)
    parser.add_argument("--r0", type=float, default=Stage1PureConfig.r0)
    parser.add_argument("--theta-min", type=float, default=Stage1PureConfig.theta_min)
    parser.add_argument("--theta-max", type=float, default=Stage1PureConfig.theta_max)
    args = parser.parse_args()
    return Stage1PureConfig(
        output_dir=args.output_dir,
        seed=args.seed,
        time_steps=args.time_steps,
        height=args.height,
        width=args.width,
        noise_scale=args.noise_scale,
        noise_mode=args.noise_mode,
        theta_variation_scale=args.theta_variation_scale,
        n_iter=args.n_iter,
        burn=args.burn,
        q0_scale=args.q0_scale,
        p0_scale=args.p0_scale,
        r0=args.r0,
        theta_min=args.theta_min,
        theta_max=args.theta_max,
    )


def main() -> None:
    cfg = parse_args()
    summary = run_synthetic_stage1(cfg)
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
