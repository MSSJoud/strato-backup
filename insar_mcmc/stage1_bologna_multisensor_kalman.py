#!/usr/bin/env python3
"""Balanced grouped multisensor Stage 1 for Bologna.

This is a real-data regional prototype that fuses:
- InSAR regional-mean deformation anomaly
- GRACE regional TWS anomaly
- SMAP regional surface soil moisture

The latent state is a grouped correction-factor state:

    theta_t = [theta_shallow, theta_deep, theta_groundwater]

applied to grouped W3RA priors:

    x_t = theta_t ⊙ z_t

where:
- z_shallow = S0 + Ss
- z_deep = Sd + Sr
- z_groundwater = Sg

Balancing is handled by scaling each observation stream before Kalman updates.
"""

from __future__ import annotations

import argparse
import json
import random
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np
import pandas as pd
import xarray as xr


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

STATE_NAMES = ("ShallowLoad", "DeepLoad", "Groundwater")


@dataclass
class BolognaMultisensorKalmanConfig:
    insar_path: str = "/mnt/data/mcma/01/insar_sub.nc"
    w3ra_path: str = "/mnt/data/mcma/01/w3ra_sub_anom.nc"
    grace_csv: str = "/home/ubuntu/work/insar_mcmc/outputs_external_constraints/bologna_grace_region_timeseries.csv"
    smap_csv: str = "/home/ubuntu/work/insar_mcmc/outputs_external_constraints/smap_processed/bologna_smap_surface_soil_moisture_timeseries.csv"
    swot_river_csv: str = ""
    swot_lake_csv: str = ""
    output_dir: str = "/home/ubuntu/work/insar_mcmc/outputs_stage1_bologna_multisensor_kalman"
    seed: int = 42
    state_persistence: float = 0.98
    q_scale: float = 2e-2
    p0_scale: float = 0.25
    theta0: float = 1.0
    r_insar: float = 0.15
    r_grace: float = 0.25
    r_smap: float = 0.30
    r_swot_river: float = 0.40
    r_swot_lake: float = 0.40
    swot_max_gap_days: int = 14
    grace_unit_scale: float = 10.0  # cm LWE -> mm LWE
    ridge_eps: float = 1e-6


@dataclass(frozen=True)
class PhysicsConfig:
    E: float = 1e9
    nu: float = 0.25
    rho_w: float = 1000.0
    g: float = 9.81
    alpha: float = 0.8
    Hg: float = 150.0
    Seff: float = 0.2
    dx: float = 10000.0
    dy: float = 10000.0
    a_load: float = 3000.0
    a_poro: float = 3000.0


def set_seed(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)


def rmse(a, b) -> float:
    aa = np.asarray(a)
    bb = np.asarray(b)
    return float(np.sqrt(np.nanmean((aa - bb) ** 2)))


def corr_np(a, b) -> float:
    aa = np.asarray(a).ravel()
    bb = np.asarray(b).ravel()
    m = np.isfinite(aa) & np.isfinite(bb)
    if m.sum() < 2:
        return np.nan
    return float(np.corrcoef(aa[m], bb[m])[0, 1])


def r2_score_np(y_true, y_pred) -> float:
    yt = np.asarray(y_true).ravel()
    yp = np.asarray(y_pred).ravel()
    m = np.isfinite(yt) & np.isfinite(yp)
    if m.sum() < 2:
        return np.nan
    yt = yt[m]
    yp = yp[m]
    ss_res = np.sum((yt - yp) ** 2)
    ss_tot = np.sum((yt - np.mean(yt)) ** 2)
    return np.nan if ss_tot == 0 else float(1.0 - ss_res / ss_tot)


def build_elastic_kernel(E: float, nu: float, dx: float, dy: float, a: float, nx: int, ny: int) -> np.ndarray:
    xgrid = (np.arange(nx) - nx / 2) * dx
    ygrid = (np.arange(ny) - ny / 2) * dy
    xx, yy = np.meshgrid(xgrid, ygrid)
    r = np.sqrt(xx**2 + yy**2)
    r[r < 1e-6] = 1e-6
    return (1 + nu) / (np.pi * E * (1 - nu)) * (1 - np.exp(-r / a)) / r


def build_poroelastic_kernel(E: float, nu: float, alpha: float, hg: float, dx: float, dy: float, a: float, nx: int, ny: int) -> np.ndarray:
    xgrid = (np.arange(nx) - nx / 2) * dx
    ygrid = (np.arange(ny) - ny / 2) * dy
    xx, yy = np.meshgrid(xgrid, ygrid)
    r = np.sqrt(xx**2 + yy**2)
    r[r < 1e-6] = 1e-6
    factor = alpha * (1 + nu) * hg * 9.81 / (np.pi * E * (1 - nu))
    return factor * (1 - np.exp(-r / a)) / r


def build_fft_kernels_numpy(ny: int, nx: int, physics: PhysicsConfig) -> tuple[np.ndarray, np.ndarray]:
    g_load = build_elastic_kernel(physics.E, physics.nu, physics.dx, physics.dy, physics.a_load, nx, ny)
    g_poro = build_poroelastic_kernel(
        physics.E,
        physics.nu,
        physics.alpha,
        physics.Hg,
        physics.dx,
        physics.dy,
        physics.a_poro,
        nx,
        ny,
    )
    return np.fft.fft2(np.fft.ifftshift(g_load)), np.fft.fft2(np.fft.ifftshift(g_poro))


def fft_convolve2d_numpy(field: np.ndarray, kernel_fft: np.ndarray) -> np.ndarray:
    return np.fft.ifft2(np.fft.fft2(field) * kernel_fft).real.astype(np.float32)


def forward_five_layer_components_numpy(
    layers: np.ndarray,
    physics: PhysicsConfig,
    sg_index: int = 3,
    load_indices: tuple[int, ...] = (0, 1, 2, 4),
) -> np.ndarray:
    if layers.ndim != 4:
        raise ValueError(f"Expected layers with shape (T,K,H,W), got {layers.shape}.")
    t_steps, n_layers, ny, nx = layers.shape
    g_load_fft, g_poro_fft = build_fft_kernels_numpy(ny, nx, physics)
    components = np.zeros_like(layers, dtype=np.float32)
    for t in range(t_steps):
        for k in range(n_layers):
            field = layers[t, k].astype(np.float32)
            if k == sg_index:
                delta = physics.rho_w * physics.g * (field / physics.Seff)
                components[t, k] = fft_convolve2d_numpy(delta, g_poro_fft)
            elif k in load_indices:
                delta = physics.rho_w * field
                components[t, k] = fft_convolve2d_numpy(delta, g_load_fft)
    return components


def align_optional_series(times: pd.DatetimeIndex, csv_path: str, value_column: str) -> np.ndarray:
    df = pd.read_csv(csv_path)
    df["time"] = pd.to_datetime(df["time"]).dt.normalize()
    merged = pd.DataFrame({"time": times.normalize()}).merge(df[["time", value_column]], on="time", how="left")
    return merged[value_column].to_numpy(dtype=np.float64)


def align_nearest_series(
    times: pd.DatetimeIndex,
    csv_path: str,
    value_column: str,
    max_gap_days: int,
) -> np.ndarray:
    if not csv_path:
        return np.full(len(times), np.nan, dtype=np.float64)
    df = pd.read_csv(csv_path)
    if df.empty:
        return np.full(len(times), np.nan, dtype=np.float64)
    df["time"] = pd.to_datetime(df["time"]).dt.normalize()
    df = df[["time", value_column]].dropna().sort_values("time")
    base = pd.DataFrame({"time": times.normalize()}).sort_values("time")
    if df.empty:
        return np.full(len(times), np.nan, dtype=np.float64)
    merged = pd.merge_asof(
        base,
        df,
        on="time",
        direction="nearest",
        tolerance=pd.Timedelta(days=max_gap_days),
    )
    return merged[value_column].to_numpy(dtype=np.float64)


def anomaly_1d(values: np.ndarray) -> np.ndarray:
    arr = values.astype(np.float64).copy()
    if np.isfinite(arr).any():
        arr = arr - np.nanmean(arr)
    return arr


def safe_std(values: np.ndarray, floor: float = 1e-6) -> float:
    val = float(np.nanstd(values))
    if not np.isfinite(val):
        return 1.0
    return max(val, floor)


def scalar_slope(x: np.ndarray, y: np.ndarray, ridge_eps: float = 1e-6) -> float:
    mask = np.isfinite(x) & np.isfinite(y)
    if mask.sum() < 2:
        return 0.0
    xv = x[mask]
    yv = y[mask]
    denom = float(np.dot(xv, xv) + ridge_eps)
    return float(np.dot(xv, yv) / denom)


def load_series(cfg: BolognaMultisensorKalmanConfig) -> dict[str, np.ndarray]:
    insar = xr.open_dataset(cfg.insar_path)
    w3ra = xr.open_dataset(cfg.w3ra_path)
    try:
        times = pd.DatetimeIndex(pd.to_datetime(insar.time.values))
        if not np.array_equal(times.values, pd.DatetimeIndex(pd.to_datetime(w3ra.time.values)).values):
            raise ValueError("InSAR and W3RA times do not match.")

        y_insar = insar["insar_deformation"].mean(dim=("y", "x"), skipna=True).values.astype(np.float64)
        y_insar = anomaly_1d(y_insar)

        z_shallow = (w3ra["S0"] + w3ra["Ss"]).mean(dim=("y", "x"), skipna=True).values.astype(np.float64)
        z_deep = (w3ra["Sd"] + w3ra["Sr"]).mean(dim=("y", "x"), skipna=True).values.astype(np.float64)
        z_ground = w3ra["Sg"].mean(dim=("y", "x"), skipna=True).values.astype(np.float64)
        z_state = np.stack([z_shallow, z_deep, z_ground], axis=1)

        z_layers = np.stack([w3ra[name].values.astype(np.float32) for name in ("S0", "Ss", "Sd", "Sg", "Sr")], axis=1)
        z_layers = np.nan_to_num(z_layers, nan=0.0, posinf=0.0, neginf=0.0)
        def_components = forward_five_layer_components_numpy(
            z_layers,
            physics=PhysicsConfig(),
            sg_index=3,
            load_indices=(0, 1, 2, 4),
        )
        d_shallow = def_components[:, [0, 1]].sum(axis=1).mean(axis=(1, 2)).astype(np.float64)
        d_deep = def_components[:, [2, 4]].sum(axis=1).mean(axis=(1, 2)).astype(np.float64)
        d_ground = def_components[:, 3].mean(axis=(1, 2)).astype(np.float64)
        z_def = np.stack([d_shallow, d_deep, d_ground], axis=1)
    finally:
        insar.close()
        w3ra.close()

    y_grace = align_optional_series(times, cfg.grace_csv, "lwe_thickness_mean_anom")
    y_grace = anomaly_1d(y_grace * cfg.grace_unit_scale)

    y_smap = align_optional_series(times, cfg.smap_csv, "soil_moisture_mean")
    y_smap = anomaly_1d(y_smap)

    y_swot_river = align_nearest_series(times, cfg.swot_river_csv, "wse_mean", cfg.swot_max_gap_days)
    y_swot_river = anomaly_1d(y_swot_river)

    y_swot_lake = align_nearest_series(times, cfg.swot_lake_csv, "wse_mean", cfg.swot_max_gap_days)
    y_swot_lake = anomaly_1d(y_swot_lake)

    return {
        "times": times,
        "y_insar": y_insar,
        "y_grace": y_grace,
        "y_smap": y_smap,
        "y_swot_river": y_swot_river,
        "y_swot_lake": y_swot_lake,
        "z_state": z_state,
        "z_def": z_def,
    }


def kalman_filter_grouped(
    z_state: np.ndarray,
    z_def: np.ndarray,
    y_insar: np.ndarray,
    y_grace: np.ndarray,
    y_smap: np.ndarray,
    y_swot_river: np.ndarray,
    y_swot_lake: np.ndarray,
    cfg: BolognaMultisensorKalmanConfig,
) -> dict[str, np.ndarray]:
    t_steps, n_state = z_state.shape
    assert n_state == 3

    insar_scale = safe_std(y_insar)
    grace_scale = safe_std(y_grace)
    smap_scale = safe_std(y_smap[np.isfinite(y_smap)]) if np.isfinite(y_smap).any() else 1.0
    swot_river_scale = safe_std(y_swot_river[np.isfinite(y_swot_river)]) if np.isfinite(y_swot_river).any() else 1.0
    swot_lake_scale = safe_std(y_swot_lake[np.isfinite(y_swot_lake)]) if np.isfinite(y_swot_lake).any() else 1.0

    smap_slope = scalar_slope(z_state[:, 0], y_smap, ridge_eps=cfg.ridge_eps)
    swot_river_slope = scalar_slope(z_state[:, 0], y_swot_river, ridge_eps=cfg.ridge_eps)
    swot_lake_slope = scalar_slope(z_state[:, 0], y_swot_lake, ridge_eps=cfg.ridge_eps)

    phi = cfg.state_persistence
    q = cfg.q_scale * np.eye(n_state, dtype=np.float64)
    p_prev = cfg.p0_scale * np.eye(n_state, dtype=np.float64)
    m_prev = np.full(n_state, cfg.theta0, dtype=np.float64)
    m_ref = np.full(n_state, cfg.theta0, dtype=np.float64)

    pred_mean = np.zeros((t_steps, n_state), dtype=np.float64)
    pred_cov = np.zeros((t_steps, n_state, n_state), dtype=np.float64)
    filt_mean = np.zeros((t_steps, n_state), dtype=np.float64)
    filt_cov = np.zeros((t_steps, n_state, n_state), dtype=np.float64)
    innovation_store = np.full((t_steps, 5), np.nan, dtype=np.float64)

    for t in range(t_steps):
        m_pred = phi * m_prev + (1.0 - phi) * m_ref
        p_pred = (phi ** 2) * p_prev + q

        rows = []
        ys = []
        rs = []

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

        pred_mean[t] = m_pred
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
            innovation_store[t, : len(innovation)] = innovation
        else:
            m_filt = m_pred
            p_filt = p_pred

        filt_mean[t] = m_filt
        filt_cov[t] = p_filt
        m_prev = m_filt
        p_prev = p_filt

    smooth_mean = filt_mean.copy()
    smooth_cov = filt_cov.copy()
    for t in range(t_steps - 2, -1, -1):
        p_f = filt_cov[t]
        p_pn = pred_cov[t + 1]
        c = (phi * p_f) @ np.linalg.pinv(p_pn)
        smooth_mean[t] = filt_mean[t] + c @ (smooth_mean[t + 1] - pred_mean[t + 1])
        smooth_cov[t] = p_f + c @ (smooth_cov[t + 1] - p_pn) @ c.T

    x_prior = z_state
    x_post = smooth_mean * z_state

    y_insar_prior = np.einsum("tk,tk->t", z_def, np.ones_like(smooth_mean))
    y_insar_post = np.einsum("tk,tk->t", z_def, smooth_mean)
    y_grace_prior = np.einsum("tk,tk->t", z_state, np.ones_like(smooth_mean))
    y_grace_post = np.einsum("tk,tk->t", z_state, smooth_mean)
    y_smap_prior = smap_slope * z_state[:, 0]
    y_smap_post = smap_slope * x_post[:, 0]
    y_swot_river_prior = swot_river_slope * z_state[:, 0]
    y_swot_river_post = swot_river_slope * x_post[:, 0]
    y_swot_lake_prior = swot_lake_slope * z_state[:, 0]
    y_swot_lake_post = swot_lake_slope * x_post[:, 0]

    return {
        "theta_pred": pred_mean,
        "theta_filt": filt_mean,
        "theta_smooth": smooth_mean,
        "theta_smooth_cov": smooth_cov,
        "x_prior": x_prior,
        "x_post": x_post,
        "y_insar_prior": y_insar_prior,
        "y_insar_post": y_insar_post,
        "y_grace_prior": y_grace_prior,
        "y_grace_post": y_grace_post,
        "y_smap_prior": y_smap_prior,
        "y_smap_post": y_smap_post,
        "y_swot_river_prior": y_swot_river_prior,
        "y_swot_river_post": y_swot_river_post,
        "y_swot_lake_prior": y_swot_lake_prior,
        "y_swot_lake_post": y_swot_lake_post,
        "innovation": innovation_store,
        "insar_scale": np.array(insar_scale, dtype=np.float64),
        "grace_scale": np.array(grace_scale, dtype=np.float64),
        "smap_scale": np.array(smap_scale, dtype=np.float64),
        "smap_slope": np.array(smap_slope, dtype=np.float64),
        "swot_river_scale": np.array(swot_river_scale, dtype=np.float64),
        "swot_river_slope": np.array(swot_river_slope, dtype=np.float64),
        "swot_lake_scale": np.array(swot_lake_scale, dtype=np.float64),
        "swot_lake_slope": np.array(swot_lake_slope, dtype=np.float64),
    }


def summarize_metric(y_true: np.ndarray, y_pred: np.ndarray) -> dict[str, float | int | None]:
    mask = np.isfinite(y_true) & np.isfinite(y_pred)
    if mask.sum() < 2:
        return {"n": int(mask.sum()), "rmse": None, "corr": None, "r2": None}
    yt = y_true[mask]
    yp = y_pred[mask]
    return {
        "n": int(mask.sum()),
        "rmse": rmse(yt, yp),
        "corr": corr_np(yt, yp),
        "r2": r2_score_np(yt, yp),
    }


def run(cfg: BolognaMultisensorKalmanConfig) -> dict:
    set_seed(cfg.seed)
    data = load_series(cfg)
    out = kalman_filter_grouped(
        z_state=data["z_state"],
        z_def=data["z_def"],
        y_insar=data["y_insar"],
        y_grace=data["y_grace"],
        y_smap=data["y_smap"],
        y_swot_river=data["y_swot_river"],
        y_swot_lake=data["y_swot_lake"],
        cfg=cfg,
    )

    summary = {
        "config": asdict(cfg),
        "time_start": str(data["times"][0].date()),
        "time_end": str(data["times"][-1].date()),
        "n_times": int(len(data["times"])),
        "state_names": list(STATE_NAMES),
        "scales": {
            "insar_scale": float(out["insar_scale"]),
            "grace_scale": float(out["grace_scale"]),
            "smap_scale": float(out["smap_scale"]),
            "smap_slope": float(out["smap_slope"]),
            "swot_river_scale": float(out["swot_river_scale"]),
            "swot_river_slope": float(out["swot_river_slope"]),
            "swot_lake_scale": float(out["swot_lake_scale"]),
            "swot_lake_slope": float(out["swot_lake_slope"]),
        },
        "metrics": {
            "insar_prior": summarize_metric(data["y_insar"], out["y_insar_prior"]),
            "insar_post": summarize_metric(data["y_insar"], out["y_insar_post"]),
            "grace_prior": summarize_metric(data["y_grace"], out["y_grace_prior"]),
            "grace_post": summarize_metric(data["y_grace"], out["y_grace_post"]),
            "smap_prior": summarize_metric(data["y_smap"], out["y_smap_prior"]),
            "smap_post": summarize_metric(data["y_smap"], out["y_smap_post"]),
            "swot_river_prior": summarize_metric(data["y_swot_river"], out["y_swot_river_prior"]),
            "swot_river_post": summarize_metric(data["y_swot_river"], out["y_swot_river_post"]),
            "swot_lake_prior": summarize_metric(data["y_swot_lake"], out["y_swot_lake_prior"]),
            "swot_lake_post": summarize_metric(data["y_swot_lake"], out["y_swot_lake_post"]),
        },
        "theta_summary": {
            name: {
                "mean": float(np.nanmean(out["theta_smooth"][:, i])),
                "std": float(np.nanstd(out["theta_smooth"][:, i])),
                "min": float(np.nanmin(out["theta_smooth"][:, i])),
                "max": float(np.nanmax(out["theta_smooth"][:, i])),
            }
            for i, name in enumerate(STATE_NAMES)
        },
    }

    out_dir = Path(cfg.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(
        out_dir / "stage1_bologna_multisensor_kalman_results.npz",
        time=data["times"].values.astype("datetime64[ns]"),
        z_state=data["z_state"],
        z_def=data["z_def"],
        y_insar=data["y_insar"],
        y_grace=data["y_grace"],
        y_smap=data["y_smap"],
        y_swot_river=data["y_swot_river"],
        y_swot_lake=data["y_swot_lake"],
        theta_pred=out["theta_pred"],
        theta_filt=out["theta_filt"],
        theta_smooth=out["theta_smooth"],
        x_prior=out["x_prior"],
        x_post=out["x_post"],
        y_insar_prior=out["y_insar_prior"],
        y_insar_post=out["y_insar_post"],
        y_grace_prior=out["y_grace_prior"],
        y_grace_post=out["y_grace_post"],
        y_smap_prior=out["y_smap_prior"],
        y_smap_post=out["y_smap_post"],
        y_swot_river_prior=out["y_swot_river_prior"],
        y_swot_river_post=out["y_swot_river_post"],
        y_swot_lake_prior=out["y_swot_lake_prior"],
        y_swot_lake_post=out["y_swot_lake_post"],
        innovation=out["innovation"],
        state_names=np.array(STATE_NAMES),
    )
    (out_dir / "stage1_bologna_multisensor_kalman_summary.json").write_text(json.dumps(summary, indent=2))
    pd.DataFrame(
        {
            "time": data["times"],
            "y_insar": data["y_insar"],
            "y_insar_prior": out["y_insar_prior"],
            "y_insar_post": out["y_insar_post"],
            "y_grace": data["y_grace"],
            "y_grace_prior": out["y_grace_prior"],
            "y_grace_post": out["y_grace_post"],
            "y_smap": data["y_smap"],
            "y_smap_prior": out["y_smap_prior"],
            "y_smap_post": out["y_smap_post"],
            "y_swot_river": data["y_swot_river"],
            "y_swot_river_prior": out["y_swot_river_prior"],
            "y_swot_river_post": out["y_swot_river_post"],
            "y_swot_lake": data["y_swot_lake"],
            "y_swot_lake_prior": out["y_swot_lake_prior"],
            "y_swot_lake_post": out["y_swot_lake_post"],
            "theta_shallow": out["theta_smooth"][:, 0],
            "theta_deep": out["theta_smooth"][:, 1],
            "theta_groundwater": out["theta_smooth"][:, 2],
            "x_shallow": out["x_post"][:, 0],
            "x_deep": out["x_post"][:, 1],
            "x_groundwater": out["x_post"][:, 2],
        }
    ).to_csv(out_dir / "stage1_bologna_multisensor_kalman_timeseries.csv", index=False)
    print(json.dumps(summary, indent=2))
    return summary


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--insar-path", default=BolognaMultisensorKalmanConfig.insar_path)
    p.add_argument("--w3ra-path", default=BolognaMultisensorKalmanConfig.w3ra_path)
    p.add_argument("--grace-csv", default=BolognaMultisensorKalmanConfig.grace_csv)
    p.add_argument("--smap-csv", default=BolognaMultisensorKalmanConfig.smap_csv)
    p.add_argument("--swot-river-csv", default=BolognaMultisensorKalmanConfig.swot_river_csv)
    p.add_argument("--swot-lake-csv", default=BolognaMultisensorKalmanConfig.swot_lake_csv)
    p.add_argument("--output-dir", default=BolognaMultisensorKalmanConfig.output_dir)
    p.add_argument("--seed", type=int, default=BolognaMultisensorKalmanConfig.seed)
    p.add_argument("--state-persistence", type=float, default=BolognaMultisensorKalmanConfig.state_persistence)
    p.add_argument("--q-scale", type=float, default=BolognaMultisensorKalmanConfig.q_scale)
    p.add_argument("--p0-scale", type=float, default=BolognaMultisensorKalmanConfig.p0_scale)
    p.add_argument("--theta0", type=float, default=BolognaMultisensorKalmanConfig.theta0)
    p.add_argument("--r-insar", type=float, default=BolognaMultisensorKalmanConfig.r_insar)
    p.add_argument("--r-grace", type=float, default=BolognaMultisensorKalmanConfig.r_grace)
    p.add_argument("--r-smap", type=float, default=BolognaMultisensorKalmanConfig.r_smap)
    p.add_argument("--r-swot-river", type=float, default=BolognaMultisensorKalmanConfig.r_swot_river)
    p.add_argument("--r-swot-lake", type=float, default=BolognaMultisensorKalmanConfig.r_swot_lake)
    p.add_argument("--swot-max-gap-days", type=int, default=BolognaMultisensorKalmanConfig.swot_max_gap_days)
    return p


def main() -> None:
    args = build_parser().parse_args()
    cfg = BolognaMultisensorKalmanConfig(
        insar_path=args.insar_path,
        w3ra_path=args.w3ra_path,
        grace_csv=args.grace_csv,
        smap_csv=args.smap_csv,
        swot_river_csv=args.swot_river_csv,
        swot_lake_csv=args.swot_lake_csv,
        output_dir=args.output_dir,
        seed=args.seed,
        state_persistence=args.state_persistence,
        q_scale=args.q_scale,
        p0_scale=args.p0_scale,
        theta0=args.theta0,
        r_insar=args.r_insar,
        r_grace=args.r_grace,
        r_smap=args.r_smap,
        r_swot_river=args.r_swot_river,
        r_swot_lake=args.r_swot_lake,
        swot_max_gap_days=args.swot_max_gap_days,
    )
    run(cfg)


if __name__ == "__main__":
    main()
