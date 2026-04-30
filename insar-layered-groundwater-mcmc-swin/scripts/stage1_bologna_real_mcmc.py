#!/usr/bin/env python3
"""Real Bologna Stage 1 deformation-space MCMC.

This script runs the pure Stage 1 model on the matched Bologna subset:

- Y: real InSAR deformation from ``insar_sub.nc``
- Z: W3RA anomaly layers from ``w3ra_sub_anom.nc`` forward-converted to
  component-wise deformation predictors

No SWOT or SMAP constraints are used here.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

import h5py
import numpy as np


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from insar_mcmc.stage1_pure_mcmc import gibbs_per_grid  # noqa: E402
from punjab.punjab_inversion.metrics import corr_np, r2_score_np, rmse  # noqa: E402
from punjab.punjab_inversion.physics import PhysicsConfig, forward_five_layer_components_numpy, set_seed  # noqa: E402


LAYER_NAMES = ("S0", "Ss", "Sd", "Sg", "Sr")
GROUPED_NAMES = ("Load_total", "Sg")


@dataclass
class Stage1BolognaConfig:
    insar_path: str = "/mnt/data/mcma/01/insar_sub.nc"
    w3ra_path: str = "/mnt/data/mcma/01/w3ra_sub_anom.nc"
    output_dir: str = "/home/ubuntu/work/insar_mcmc/outputs_stage1_bologna_real"
    seed: int = 42
    n_iter: int = 60
    burn: int = 20
    q0_scale: float = 0.01
    p0_scale: float = 0.25
    r0: float = 1e-4
    iw_dof_extra: int = 2
    m0_value: float = 0.0
    drop_empty_times: bool = True
    y0: int = 0
    y1: int = -1
    x0: int = 0
    x1: int = -1
    use_insar_anomaly: bool = True
    standardize_global: bool = True
    mode: str = "grouped"


def load_bologna_subset(cfg: Stage1BolognaConfig) -> dict[str, np.ndarray]:
    with h5py.File(cfg.insar_path, "r") as fi, h5py.File(cfg.w3ra_path, "r") as fw:
        y = fi["insar_deformation"][:].astype(np.float32)
        time = fi["time"][:]
        lat = fi["lat"][:].astype(np.float32)
        lon = fi["lon"][:].astype(np.float32)
        z_layers = np.stack([fw[name][:].astype(np.float32) for name in LAYER_NAMES], axis=1)
        w_time = fw["time"][:]

    if not np.array_equal(time, w_time):
        raise ValueError("InSAR and W3RA subset times do not match.")

    y1 = y.shape[1] if cfg.y1 < 0 else min(cfg.y1, y.shape[1])
    x1 = y.shape[2] if cfg.x1 < 0 else min(cfg.x1, y.shape[2])
    y = y[:, cfg.y0:y1, cfg.x0:x1]
    z_layers = z_layers[:, :, cfg.y0:y1, cfg.x0:x1]
    lat = lat[cfg.y0:y1, cfg.x0:x1]
    lon = lon[cfg.y0:y1, cfg.x0:x1]

    time_valid = np.isfinite(y).reshape(y.shape[0], -1).mean(axis=1) > 0.0
    if cfg.drop_empty_times:
        y = y[time_valid]
        z_layers = z_layers[time_valid]
        time = time[time_valid]

    pixel_valid = np.isfinite(y).all(axis=0)
    if not np.all(pixel_valid):
        y = y[:, pixel_valid]
        z_layers = z_layers[:, :, pixel_valid]
        lat = lat[pixel_valid]
        lon = lon[pixel_valid]

    return {
        "y": y,
        "z_layers": z_layers,
        "time": time,
        "lat": lat,
        "lon": lon,
        "pixel_valid_mask": pixel_valid,
        "time_valid_mask": time_valid,
    }


def summarize_theta(theta_hat: np.ndarray) -> dict[str, dict[str, float]]:
    out: dict[str, dict[str, float]] = {}
    names = LAYER_NAMES if theta_hat.shape[2] == len(LAYER_NAMES) else GROUPED_NAMES
    for k, name in enumerate(names):
        vals = theta_hat[:, :, k]
        out[name] = {
            "mean": float(np.nanmean(vals)),
            "std": float(np.nanstd(vals)),
            "min": float(np.nanmin(vals)),
            "max": float(np.nanmax(vals)),
            "l2_norm": float(np.linalg.norm(vals)),
        }
    return out


def safe_global_std(arr: np.ndarray, floor: float = 1e-6) -> float:
    val = float(np.nanstd(arr))
    return max(val, floor)


def run_bologna_stage1(cfg: Stage1BolognaConfig) -> dict:
    set_seed(cfg.seed)
    physics = PhysicsConfig()
    data = load_bologna_subset(cfg)

    y = data["y"]  # (T, P) after flattening valid pixels below
    z_layers = data["z_layers"]  # (T, K, P) because pixel_valid mask may flatten

    if y.ndim == 3:
        t_steps, h, w = y.shape
        n_pixels = h * w
        if cfg.use_insar_anomaly:
            y = y - np.nanmean(y, axis=0, keepdims=True)
        y_flat_raw = y.reshape(t_steps, n_pixels)
        z_forw_full = forward_five_layer_components_numpy(
            z_layers,
            physics=physics,
            sg_index=3,
            load_indices=(0, 1, 2, 4),
        )
        raw_state_full = z_layers.reshape(t_steps, len(LAYER_NAMES), n_pixels).transpose(0, 2, 1)
        if cfg.mode == "grouped":
            z_grouped = np.stack(
                [
                    z_forw_full[:, [0, 1, 2, 4]].sum(axis=1),
                    z_forw_full[:, 3],
                ],
                axis=1,
            )
            state_grouped = np.stack(
                [
                    z_layers[:, [0, 1, 2, 4]].sum(axis=1),
                    z_layers[:, 3],
                ],
                axis=1,
            )
            z_flat_raw = z_grouped.reshape(t_steps, len(GROUPED_NAMES), n_pixels).transpose(0, 2, 1)
            raw_state = state_grouped.reshape(t_steps, len(GROUPED_NAMES), n_pixels).transpose(0, 2, 1)
            field_names = GROUPED_NAMES
        elif cfg.mode == "five_layer":
            z_flat_raw = z_forw_full.reshape(t_steps, len(LAYER_NAMES), n_pixels).transpose(0, 2, 1)
            raw_state = raw_state_full
            field_names = LAYER_NAMES
        else:
            raise ValueError(f"Unsupported mode={cfg.mode!r}. Use 'grouped' or 'five_layer'.")
        mapped_shape = (h, w)
        lat_map = data["lat"]
        lon_map = data["lon"]
    else:
        # If data were reduced through a boolean mask, retain the 2D bookkeeping externally.
        raise ValueError("Expected the Bologna subset to stay on a 2D grid.")

    k_dim = z_flat_raw.shape[2]
    y_scale = safe_global_std(y_flat_raw) if cfg.standardize_global else 1.0
    z_scale = np.array(
        [safe_global_std(z_flat_raw[:, :, k]) if cfg.standardize_global else 1.0 for k in range(k_dim)],
        dtype=np.float32,
    )
    y_flat = (y_flat_raw / y_scale).astype(np.float32)
    z_flat = (z_flat_raw / z_scale[None, None, :]).astype(np.float32)

    m0 = np.full(k_dim, cfg.m0_value, dtype=np.float32)
    p0 = cfg.p0_scale * np.eye(k_dim, dtype=np.float32)
    q0 = cfg.q0_scale * np.eye(k_dim, dtype=np.float32)

    theta_hat, q_hat, r_hat = gibbs_per_grid(
        y=y_flat,
        z=z_flat,
        n_iter=cfg.n_iter,
        burn=cfg.burn,
        m0=m0,
        p0=p0,
        q0=q0,
        nu0=k_dim + cfg.iw_dof_extra,
        r0=cfg.r0,
    )

    theta_raw = theta_hat * (y_scale / z_scale[None, None, :])
    x_prior_flat = theta_raw * raw_state
    y_pred_flat_std = np.einsum("tpk,tpk->tp", z_flat, theta_hat)
    y_pred_flat = y_pred_flat_std * y_scale
    resid_flat = y_flat_raw - y_pred_flat

    theta_map = theta_raw.transpose(0, 2, 1).reshape(t_steps, k_dim, *mapped_shape)
    x_prior_map = x_prior_flat.transpose(0, 2, 1).reshape(t_steps, k_dim, *mapped_shape)
    y_map = y_flat_raw.reshape(t_steps, *mapped_shape)
    y_pred_map = y_pred_flat.reshape(t_steps, *mapped_shape)
    resid_map = resid_flat.reshape(t_steps, *mapped_shape)

    summary = {
        "config": asdict(cfg),
        "shape": {
            "time": int(t_steps),
            "height": int(mapped_shape[0]),
            "width": int(mapped_shape[1]),
            "pixels": int(n_pixels),
            "layers": int(k_dim),
        },
        "observation_fit": {
            "rmse": rmse(y_flat_raw, y_pred_flat),
            "corr": corr_np(y_flat_raw, y_pred_flat),
            "r2": r2_score_np(y_flat_raw, y_pred_flat),
        },
        "posterior": {
            "Q_hat_diag": np.diag(q_hat).astype(float).tolist(),
            "R_hat": float(r_hat),
            "y_scale": float(y_scale),
            "z_scale": z_scale.astype(float).tolist(),
            "theta_summary": summarize_theta(theta_raw),
        },
    }

    out_dir = Path(cfg.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(
        out_dir / "stage1_bologna_real_results.npz",
        theta_hat=theta_map,
        x_prior=x_prior_map,
        y_obs=y_map,
        y_pred=y_pred_map,
        residual=resid_map,
        z_layers=z_layers,
        field_names=np.array(field_names),
        time=data["time"],
        lat=lat_map,
        lon=lon_map,
        q_hat=q_hat,
        r_hat=np.array(r_hat, dtype=np.float32),
    )
    (out_dir / "stage1_bologna_real_summary.json").write_text(json.dumps(summary, indent=2))
    return summary


def parse_args() -> Stage1BolognaConfig:
    parser = argparse.ArgumentParser(description="Run pure Stage 1 MCMC on real Bologna InSAR and W3RA subset data.")
    parser.add_argument("--insar-path", default=Stage1BolognaConfig.insar_path)
    parser.add_argument("--w3ra-path", default=Stage1BolognaConfig.w3ra_path)
    parser.add_argument("--output-dir", default=Stage1BolognaConfig.output_dir)
    parser.add_argument("--seed", type=int, default=Stage1BolognaConfig.seed)
    parser.add_argument("--n-iter", type=int, default=Stage1BolognaConfig.n_iter)
    parser.add_argument("--burn", type=int, default=Stage1BolognaConfig.burn)
    parser.add_argument("--q0-scale", type=float, default=Stage1BolognaConfig.q0_scale)
    parser.add_argument("--p0-scale", type=float, default=Stage1BolognaConfig.p0_scale)
    parser.add_argument("--r0", type=float, default=Stage1BolognaConfig.r0)
    parser.add_argument("--y0", type=int, default=Stage1BolognaConfig.y0)
    parser.add_argument("--y1", type=int, default=Stage1BolognaConfig.y1)
    parser.add_argument("--x0", type=int, default=Stage1BolognaConfig.x0)
    parser.add_argument("--x1", type=int, default=Stage1BolognaConfig.x1)
    parser.add_argument("--mode", default=Stage1BolognaConfig.mode)
    args = parser.parse_args()
    return Stage1BolognaConfig(
        insar_path=args.insar_path,
        w3ra_path=args.w3ra_path,
        output_dir=args.output_dir,
        seed=args.seed,
        n_iter=args.n_iter,
        burn=args.burn,
        q0_scale=args.q0_scale,
        p0_scale=args.p0_scale,
        r0=args.r0,
        y0=args.y0,
        y1=args.y1,
        x0=args.x0,
        x1=args.x1,
        mode=args.mode,
    )


def main() -> None:
    cfg = parse_args()
    summary = run_bologna_stage1(cfg)
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
