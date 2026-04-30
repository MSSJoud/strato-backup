#!/usr/bin/env python3
"""Export compact diagnostics for the tiled Bologna grouped Kalman result."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path("/home/ubuntu/work/insar_mcmc")
IN_PATH = ROOT / "outputs_stage1_bologna_multisensor_kalman_tiled_v2" / "stage1_bologna_multisensor_kalman_tiled_results.npz"
OUT_DIR = ROOT / "outputs_stage1_bologna_multisensor_kalman_tiled_v2" / "diagnostics"


def trend_map(arr_tyx: np.ndarray) -> np.ndarray:
    t = np.arange(arr_tyx.shape[0], dtype=np.float64)
    t = t - t.mean()
    denom = float(np.sum(t**2))
    flat = arr_tyx.reshape(arr_tyx.shape[0], -1)
    slopes = (t[:, None] * flat).sum(axis=0) / max(denom, 1e-12)
    return slopes.reshape(arr_tyx.shape[1:])


def robust_absmax(arr: np.ndarray, pct: float = 99.0) -> float:
    vals = np.asarray(arr)
    vals = vals[np.isfinite(vals)]
    if vals.size == 0:
        return float("nan")
    return float(np.nanpercentile(np.abs(vals), pct))


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    data = np.load(IN_PATH)

    state_names = data["state_names"].tolist()
    x_tiles = data["x_tiles"]  # (T,K,Ny,Nx)
    theta_tiles = data["theta_tiles"]
    y_obs = data["y_obs_tiles"]
    y_post = data["y_post_tiles"]
    lat = data["lat_tiles"]
    lon = data["lon_tiles"]
    time = pd.DatetimeIndex(pd.to_datetime(data["time"]))

    rows = []
    for iy in range(lat.shape[0]):
        for ix in range(lat.shape[1]):
            row = {
                "tile_row": iy,
                "tile_col": ix,
                "lat": float(lat[iy, ix]),
                "lon": float(lon[iy, ix]),
                "insar_obs_mean": float(np.nanmean(y_obs[:, iy, ix])),
                "insar_post_mean": float(np.nanmean(y_post[:, iy, ix])),
                "insar_obs_trend": float(trend_map(y_obs) [iy, ix]),
                "insar_post_trend": float(trend_map(y_post)[iy, ix]),
            }
            for k, name in enumerate(state_names):
                row[f"{name}_mean"] = float(np.nanmean(x_tiles[:, k, iy, ix]))
                row[f"{name}_trend"] = float(trend_map(x_tiles[:, k])[iy, ix])
                row[f"{name}_theta_mean"] = float(np.nanmean(theta_tiles[:, k, iy, ix]))
            rows.append(row)

    df = pd.DataFrame(rows)
    df.to_csv(OUT_DIR / "bologna_kalman_tile_diagnostics.csv", index=False)

    summary = {
        "n_tiles": int(lat.size),
        "time_start": str(time[0].date()),
        "time_end": str(time[-1].date()),
        "state_sanity": {
            name: {
                "mean_abs": float(np.nanmean(np.abs(x_tiles[:, k]))),
                "max_abs": float(np.nanmax(np.abs(x_tiles[:, k]))),
                "trend_robust_absmax": robust_absmax(trend_map(x_tiles[:, k])),
                "theta_mean": float(np.nanmean(theta_tiles[:, k])),
                "theta_min": float(np.nanmin(theta_tiles[:, k])),
                "theta_max": float(np.nanmax(theta_tiles[:, k])),
            }
            for k, name in enumerate(state_names)
        },
        "insar_fit": {
            "obs_mean_abs": float(np.nanmean(np.abs(y_obs))),
            "post_mean_abs": float(np.nanmean(np.abs(y_post))),
            "trend_robust_absmax_obs": robust_absmax(trend_map(y_obs)),
            "trend_robust_absmax_post": robust_absmax(trend_map(y_post)),
        },
    }
    (OUT_DIR / "bologna_kalman_tile_diagnostics_summary.json").write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
