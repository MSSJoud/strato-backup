#!/usr/bin/env python3
"""Tiled balanced grouped multisensor Stage 1 for Bologna.

This extends the regional grouped Kalman prototype to coarse tiles while
keeping the latent grouped correction factors bounded to avoid pathological
load magnitudes.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np
import pandas as pd
import xarray as xr

from insar_mcmc.stage1_bologna_multisensor_kalman import (
    BolognaMultisensorKalmanConfig,
    PhysicsConfig,
    STATE_NAMES,
    align_nearest_series,
    align_optional_series,
    anomaly_1d,
    corr_np,
    forward_five_layer_components_numpy,
    r2_score_np,
    rmse,
    safe_std,
    scalar_slope,
    set_seed,
)


@dataclass
class BolognaMultisensorKalmanTiledConfig(BolognaMultisensorKalmanConfig):
    output_dir: str = "/home/ubuntu/work/insar_mcmc/outputs_stage1_bologna_multisensor_kalman_tiled"
    tile_size: int = 8
    tile_stride: int = 8
    theta_min: float = -1.5
    theta_max: float = 2.5


def tile_positions(length: int, tile_size: int, stride: int) -> list[int]:
    pos = list(range(0, max(length - tile_size + 1, 1), stride))
    last = max(length - tile_size, 0)
    if not pos or pos[-1] != last:
        pos.append(last)
    return pos


def load_tiled_series(cfg: BolognaMultisensorKalmanTiledConfig) -> dict[str, np.ndarray]:
    insar = xr.open_dataset(cfg.insar_path)
    w3ra = xr.open_dataset(cfg.w3ra_path)
    try:
        times = pd.DatetimeIndex(pd.to_datetime(insar.time.values))
        y_cube = insar["insar_deformation"].values.astype(np.float64)  # (T,H,W)
        lat = insar["lat"].values.astype(np.float32)
        lon = insar["lon"].values.astype(np.float32)

        s0 = w3ra["S0"].values.astype(np.float64)
        ss = w3ra["Ss"].values.astype(np.float64)
        sd = w3ra["Sd"].values.astype(np.float64)
        sg = w3ra["Sg"].values.astype(np.float64)
        sr = w3ra["Sr"].values.astype(np.float64)
        z_state_cube = np.stack([s0 + ss, sd + sr, sg], axis=1)  # (T,3,H,W)

        z_layers = np.stack([s0, ss, sd, sg, sr], axis=1).astype(np.float32)
        z_layers = np.nan_to_num(z_layers, nan=0.0, posinf=0.0, neginf=0.0)
        def_components = forward_five_layer_components_numpy(
            z_layers,
            physics=PhysicsConfig(),
            sg_index=3,
            load_indices=(0, 1, 2, 4),
        )
        z_def_cube = np.stack(
            [
                def_components[:, [0, 1]].sum(axis=1),
                def_components[:, [2, 4]].sum(axis=1),
                def_components[:, 3],
            ],
            axis=1,
        ).astype(np.float64)  # (T,3,H,W)
    finally:
        insar.close()
        w3ra.close()

    y_grace = anomaly_1d(align_optional_series(times, cfg.grace_csv, "lwe_thickness_mean_anom") * cfg.grace_unit_scale)
    y_smap = anomaly_1d(align_optional_series(times, cfg.smap_csv, "soil_moisture_mean"))
    y_swot_river = anomaly_1d(align_nearest_series(times, cfg.swot_river_csv, "wse_mean", cfg.swot_max_gap_days))
    y_swot_lake = anomaly_1d(align_nearest_series(times, cfg.swot_lake_csv, "wse_mean", cfg.swot_max_gap_days))

    return {
        "times": times,
        "y_cube": y_cube,
        "z_state_cube": z_state_cube,
        "z_def_cube": z_def_cube,
        "lat": lat,
        "lon": lon,
        "y_grace": y_grace,
        "y_smap": y_smap,
        "y_swot_river": y_swot_river,
        "y_swot_lake": y_swot_lake,
    }


def bounded_kalman_one_tile(
    z_state: np.ndarray,
    z_def: np.ndarray,
    y_insar: np.ndarray,
    y_grace: np.ndarray,
    y_smap: np.ndarray,
    y_swot_river: np.ndarray,
    y_swot_lake: np.ndarray,
    cfg: BolognaMultisensorKalmanTiledConfig,
) -> dict[str, np.ndarray]:
    t_steps, n_state = z_state.shape
    phi = cfg.state_persistence
    q = cfg.q_scale * np.eye(n_state, dtype=np.float64)
    p_prev = cfg.p0_scale * np.eye(n_state, dtype=np.float64)
    m_prev = np.full(n_state, cfg.theta0, dtype=np.float64)
    m_ref = np.full(n_state, cfg.theta0, dtype=np.float64)

    insar_scale = safe_std(y_insar)
    grace_scale = safe_std(y_grace)
    smap_scale = safe_std(y_smap[np.isfinite(y_smap)]) if np.isfinite(y_smap).any() else 1.0
    swot_river_scale = safe_std(y_swot_river[np.isfinite(y_swot_river)]) if np.isfinite(y_swot_river).any() else 1.0
    swot_lake_scale = safe_std(y_swot_lake[np.isfinite(y_swot_lake)]) if np.isfinite(y_swot_lake).any() else 1.0
    smap_slope = scalar_slope(z_state[:, 0], y_smap, ridge_eps=cfg.ridge_eps)
    swot_river_slope = scalar_slope(z_state[:, 0], y_swot_river, ridge_eps=cfg.ridge_eps)
    swot_lake_slope = scalar_slope(z_state[:, 0], y_swot_lake, ridge_eps=cfg.ridge_eps)

    pred = np.zeros((t_steps, n_state), dtype=np.float64)
    filt = np.zeros((t_steps, n_state), dtype=np.float64)
    pred_cov = np.zeros((t_steps, n_state, n_state), dtype=np.float64)
    filt_cov = np.zeros((t_steps, n_state, n_state), dtype=np.float64)

    for t in range(t_steps):
        m_pred = phi * m_prev + (1.0 - phi) * m_ref
        p_pred = (phi ** 2) * p_prev + q

        rows, ys, rs = [], [], []
        if np.isfinite(y_insar[t]) and np.all(np.isfinite(z_def[t])):
            rows.append(z_def[t] / insar_scale)
            ys.append(y_insar[t] / insar_scale)
            rs.append(cfg.r_insar ** 2)
        if np.isfinite(y_grace[t]) and np.all(np.isfinite(z_state[t])):
            rows.append(z_state[t] / grace_scale)
            ys.append(y_grace[t] / grace_scale)
            rs.append(cfg.r_grace ** 2)
        if np.isfinite(y_smap[t]) and np.isfinite(smap_slope) and abs(smap_slope) > 0 and np.isfinite(z_state[t, 0]):
            rows.append(np.array([smap_slope * z_state[t, 0], 0.0, 0.0], dtype=np.float64) / smap_scale)
            ys.append(y_smap[t] / smap_scale)
            rs.append(cfg.r_smap ** 2)
        if np.isfinite(y_swot_river[t]) and np.isfinite(swot_river_slope) and abs(swot_river_slope) > 0 and np.isfinite(z_state[t, 0]):
            rows.append(np.array([swot_river_slope * z_state[t, 0], 0.0, 0.0], dtype=np.float64) / swot_river_scale)
            ys.append(y_swot_river[t] / swot_river_scale)
            rs.append(cfg.r_swot_river ** 2)
        if np.isfinite(y_swot_lake[t]) and np.isfinite(swot_lake_slope) and abs(swot_lake_slope) > 0 and np.isfinite(z_state[t, 0]):
            rows.append(np.array([swot_lake_slope * z_state[t, 0], 0.0, 0.0], dtype=np.float64) / swot_lake_scale)
            ys.append(y_swot_lake[t] / swot_lake_scale)
            rs.append(cfg.r_swot_lake ** 2)

        pred[t] = m_pred
        pred_cov[t] = p_pred

        if rows:
            h = np.stack(rows, axis=0)
            yv = np.asarray(ys, dtype=np.float64)
            r = np.diag(np.asarray(rs, dtype=np.float64))
            valid_rows = np.all(np.isfinite(h), axis=1) & np.isfinite(yv) & np.isfinite(np.diag(r))
            h = h[valid_rows]
            yv = yv[valid_rows]
            r = r[np.ix_(valid_rows, valid_rows)]
        if rows and h.size > 0:
            s = h @ p_pred @ h.T + r + cfg.ridge_eps * np.eye(h.shape[0], dtype=np.float64)
            k = p_pred @ h.T @ np.linalg.pinv(s, rcond=1e-10)
            innovation = yv - h @ m_pred
            m_filt = m_pred + k @ innovation
            p_filt = (np.eye(n_state) - k @ h) @ p_pred
        else:
            m_filt = m_pred
            p_filt = p_pred

        m_filt = np.clip(m_filt, cfg.theta_min, cfg.theta_max)
        filt[t] = m_filt
        filt_cov[t] = p_filt
        m_prev = m_filt
        p_prev = p_filt

    smooth = filt.copy()
    for t in range(t_steps - 2, -1, -1):
        c = (phi * filt_cov[t]) @ np.linalg.pinv(pred_cov[t + 1])
        smooth[t] = filt[t] + c @ (smooth[t + 1] - pred[t + 1])
        smooth[t] = np.clip(smooth[t], cfg.theta_min, cfg.theta_max)

    x_post = smooth * z_state
    y_post = np.einsum("tk,tk->t", z_def, smooth)

    return {
        "theta_smooth": smooth,
        "x_post": x_post,
        "y_post": y_post,
    }


def run(cfg: BolognaMultisensorKalmanTiledConfig) -> dict:
    set_seed(cfg.seed)
    data = load_tiled_series(cfg)
    times = data["times"]
    y_cube = data["y_cube"]
    z_state_cube = data["z_state_cube"]
    z_def_cube = data["z_def_cube"]
    lat = data["lat"]
    lon = data["lon"]

    t_steps, h, w = y_cube.shape
    y_positions = tile_positions(h, cfg.tile_size, cfg.tile_stride)
    x_positions = tile_positions(w, cfg.tile_size, cfg.tile_stride)

    n_tiles = len(y_positions) * len(x_positions)
    theta_tiles = np.zeros((t_steps, len(STATE_NAMES), len(y_positions), len(x_positions)), dtype=np.float32)
    x_tiles = np.zeros_like(theta_tiles)
    y_post_tiles = np.zeros((t_steps, len(y_positions), len(x_positions)), dtype=np.float32)
    y_obs_tiles = np.zeros_like(y_post_tiles)
    z_tile_means = np.zeros_like(theta_tiles)
    lat_tiles = np.zeros((len(y_positions), len(x_positions)), dtype=np.float32)
    lon_tiles = np.zeros((len(y_positions), len(x_positions)), dtype=np.float32)

    for iy, y0 in enumerate(y_positions):
        for ix, x0 in enumerate(x_positions):
            y1 = y0 + cfg.tile_size
            x1 = x0 + cfg.tile_size

            y_insar = anomaly_1d(np.nanmean(y_cube[:, y0:y1, x0:x1], axis=(1, 2)))
            z_state = np.nanmean(z_state_cube[:, :, y0:y1, x0:x1], axis=(2, 3))
            z_def = np.nanmean(z_def_cube[:, :, y0:y1, x0:x1], axis=(2, 3))
            result = bounded_kalman_one_tile(
                z_state=z_state,
                z_def=z_def,
                y_insar=y_insar,
                y_grace=data["y_grace"],
                y_smap=data["y_smap"],
                y_swot_river=data["y_swot_river"],
                y_swot_lake=data["y_swot_lake"],
                cfg=cfg,
            )

            theta_tiles[:, :, iy, ix] = result["theta_smooth"]
            x_tiles[:, :, iy, ix] = result["x_post"]
            y_post_tiles[:, iy, ix] = result["y_post"]
            y_obs_tiles[:, iy, ix] = y_insar
            z_tile_means[:, :, iy, ix] = z_state
            lat_tiles[iy, ix] = float(np.nanmean(lat[y0:y1, x0:x1]))
            lon_tiles[iy, ix] = float(np.nanmean(lon[y0:y1, x0:x1]))

    metrics = {
        "tile_insar_post": {
            "rmse": rmse(y_obs_tiles, y_post_tiles),
            "corr": corr_np(y_obs_tiles, y_post_tiles),
            "r2": r2_score_np(y_obs_tiles, y_post_tiles),
        }
    }

    magnitude = {
        name: {
            "theta_min": float(np.nanmin(theta_tiles[:, i])),
            "theta_max": float(np.nanmax(theta_tiles[:, i])),
            "x_min": float(np.nanmin(x_tiles[:, i])),
            "x_max": float(np.nanmax(x_tiles[:, i])),
            "x_abs_max": float(np.nanmax(np.abs(x_tiles[:, i]))),
        }
        for i, name in enumerate(STATE_NAMES)
    }

    summary = {
        "config": asdict(cfg),
        "n_times": int(t_steps),
        "tile_grid": {"ny": len(y_positions), "nx": len(x_positions), "n_tiles": int(n_tiles)},
        "metrics": metrics,
        "magnitude": magnitude,
    }

    out_dir = Path(cfg.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(
        out_dir / "stage1_bologna_multisensor_kalman_tiled_results.npz",
        time=times.values.astype("datetime64[ns]"),
        theta_tiles=theta_tiles,
        x_tiles=x_tiles,
        y_post_tiles=y_post_tiles,
        y_obs_tiles=y_obs_tiles,
        z_tile_means=z_tile_means,
        lat_tiles=lat_tiles,
        lon_tiles=lon_tiles,
        state_names=np.array(STATE_NAMES),
    )
    (out_dir / "stage1_bologna_multisensor_kalman_tiled_summary.json").write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary, indent=2))
    return summary


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--insar-path", default=BolognaMultisensorKalmanTiledConfig.insar_path)
    p.add_argument("--w3ra-path", default=BolognaMultisensorKalmanTiledConfig.w3ra_path)
    p.add_argument("--grace-csv", default=BolognaMultisensorKalmanTiledConfig.grace_csv)
    p.add_argument("--smap-csv", default=BolognaMultisensorKalmanTiledConfig.smap_csv)
    p.add_argument("--swot-river-csv", default=BolognaMultisensorKalmanTiledConfig.swot_river_csv)
    p.add_argument("--swot-lake-csv", default=BolognaMultisensorKalmanTiledConfig.swot_lake_csv)
    p.add_argument("--output-dir", default=BolognaMultisensorKalmanTiledConfig.output_dir)
    p.add_argument("--tile-size", type=int, default=BolognaMultisensorKalmanTiledConfig.tile_size)
    p.add_argument("--tile-stride", type=int, default=BolognaMultisensorKalmanTiledConfig.tile_stride)
    p.add_argument("--theta-min", type=float, default=BolognaMultisensorKalmanTiledConfig.theta_min)
    p.add_argument("--theta-max", type=float, default=BolognaMultisensorKalmanTiledConfig.theta_max)
    p.add_argument("--r-swot-river", type=float, default=BolognaMultisensorKalmanTiledConfig.r_swot_river)
    p.add_argument("--r-swot-lake", type=float, default=BolognaMultisensorKalmanTiledConfig.r_swot_lake)
    p.add_argument("--swot-max-gap-days", type=int, default=BolognaMultisensorKalmanTiledConfig.swot_max_gap_days)
    return p


def main() -> None:
    args = build_parser().parse_args()
    cfg = BolognaMultisensorKalmanTiledConfig(
        insar_path=args.insar_path,
        w3ra_path=args.w3ra_path,
        grace_csv=args.grace_csv,
        smap_csv=args.smap_csv,
        swot_river_csv=args.swot_river_csv,
        swot_lake_csv=args.swot_lake_csv,
        output_dir=args.output_dir,
        tile_size=args.tile_size,
        tile_stride=args.tile_stride,
        theta_min=args.theta_min,
        theta_max=args.theta_max,
        r_swot_river=args.r_swot_river,
        r_swot_lake=args.r_swot_lake,
        swot_max_gap_days=args.swot_max_gap_days,
    )
    run(cfg)


if __name__ == "__main__":
    main()
