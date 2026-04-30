#!/usr/bin/env python3
from __future__ import annotations

import json
import math
import shutil
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import rasterio
from matplotlib.colors import LightSource
from matplotlib.patches import FancyBboxPatch, Rectangle
from rasterio.warp import transform_bounds


ROOT = Path("/home/ubuntu/work/insar_mcmc")
OUTDIR = ROOT / "paper_figures"
OUTDIR.mkdir(parents=True, exist_ok=True)

MPL_DIR = Path("/mnt/data/tmp/mpl_paper_figures")
MPL_DIR.mkdir(parents=True, exist_ok=True)

plt.rcParams.update(
    {
        "figure.dpi": 180,
        "savefig.dpi": 300,
        "font.size": 10,
        "axes.titlesize": 12,
        "axes.labelsize": 10,
        "legend.fontsize": 9,
        "xtick.labelsize": 9,
        "ytick.labelsize": 9,
    }
)


def load_json(path: Path) -> dict:
    with open(path) as f:
        return json.load(f)


def save(fig: plt.Figure, name: str) -> Path:
    path = OUTDIR / name
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)
    return path


def tile_positions(length: int, tile_size: int, stride: int) -> list[int]:
    pos = list(range(0, max(length - tile_size + 1, 1), stride))
    last = max(length - tile_size, 0)
    if not pos or pos[-1] != last:
        pos.append(last)
    return pos


def prepare_dem_tile(dem_path: Path):
    with rasterio.open(dem_path) as ds:
        arr = ds.read(
            1,
            out_shape=(min(800, ds.height), min(800, ds.width)),
            masked=True,
        ).astype(np.float32)
        src_bounds = ds.bounds
        lon_min, lat_min, lon_max, lat_max = transform_bounds(ds.crs, "EPSG:4326", *src_bounds)

    arr = np.ma.masked_invalid(arr)
    arr = np.ma.masked_where(arr <= -9990, arr)
    valid_mask = ~np.ma.getmaskarray(arr)
    valid_rows = np.where(valid_mask.any(axis=1))[0]
    valid_cols = np.where(valid_mask.any(axis=0))[0]

    row0, row1 = int(valid_rows[0]), int(valid_rows[-1])
    col0, col1 = int(valid_cols[0]), int(valid_cols[-1])
    arr = arr[row0 : row1 + 1, col0 : col1 + 1]

    full_h, full_w = valid_mask.shape
    full_lon_min, full_lat_min, full_lon_max, full_lat_max = lon_min, lat_min, lon_max, lat_max
    lon_span = full_lon_max - full_lon_min
    lat_span = full_lat_max - full_lat_min
    lon_min = full_lon_min + lon_span * (col0 / full_w)
    lon_max = full_lon_min + lon_span * ((col1 + 1) / full_w)
    lat_max = full_lat_max - lat_span * (row0 / full_h)
    lat_min = full_lat_max - lat_span * ((row1 + 1) / full_h)

    filled = arr.filled(np.nanmedian(arr))
    ls = LightSource(azdeg=315, altdeg=45)
    rgb = ls.shade(filled, cmap=plt.cm.gist_earth, vert_exag=0.001, blend_mode="soft")
    return rgb, (lon_min, lon_max, lat_min, lat_max)


def figure_1_area_dtm(
    overlap_summary: dict,
    dem_paths: list[Path],
    all_meta: pd.DataFrame,
    bologna_meta: pd.DataFrame,
    trusted: pd.DataFrame,
) -> Path:
    bbox = overlap_summary["bbox"]
    dem_tiles = [prepare_dem_tile(p) for p in dem_paths]
    lon_min = min(ext[0] for _, ext in dem_tiles)
    lon_max = max(ext[1] for _, ext in dem_tiles)
    lat_min = min(ext[2] for _, ext in dem_tiles)
    lat_max = max(ext[3] for _, ext in dem_tiles)

    # The shared overlap bbox is broader than the clipped DEM footprint, so we
    # display the overlap only over the valid DTM extent used in the figure.
    box_lon_min = max(bbox["lon_min"], lon_min)
    box_lon_max = min(bbox["lon_max"], lon_max)
    box_lat_min = max(bbox["lat_min"], lat_min)
    box_lat_max = min(bbox["lat_max"], lat_max)

    wells_lon_min = float(bologna_meta["lon"].min())
    wells_lon_max = float(bologna_meta["lon"].max())
    wells_lat_min = float(bologna_meta["lat"].min())
    wells_lat_max = float(bologna_meta["lat"].max())

    zoom_lon_min = max(lon_min, min(box_lon_min, wells_lon_min) - 0.18)
    zoom_lon_max = min(lon_max, max(box_lon_max, wells_lon_max) + 0.18)
    zoom_lat_min = max(lat_min, min(box_lat_min, wells_lat_min) - 0.14)
    zoom_lat_max = min(lat_max, max(box_lat_max, wells_lat_max) + 0.14)

    fig = plt.figure(figsize=(13.5, 6.5), constrained_layout=True)
    gs = fig.add_gridspec(1, 2, width_ratios=[1.15, 1.0])
    ax1 = fig.add_subplot(gs[0, 0])
    ax2 = fig.add_subplot(gs[0, 1])

    for rgb, (tlon_min, tlon_max, tlat_min, tlat_max) in dem_tiles:
        ax1.imshow(rgb, extent=[tlon_min, tlon_max, tlat_min, tlat_max], origin="upper")
    ax1.scatter(all_meta["lon"], all_meta["lat"], s=6, c="white", alpha=0.28, linewidths=0)
    ax1.add_patch(
        Rectangle(
            (box_lon_min, box_lat_min),
            box_lon_max - box_lon_min,
            box_lat_max - box_lat_min,
            fill=False,
            ec="red",
            lw=2.2,
        )
    )
    ax1.text(
        box_lon_min + 0.03,
        box_lat_max - 0.06,
        "Shared Bologna overlap",
        color="red",
        weight="bold",
        va="top",
    )
    ax1.set_title("DTM background and overlap domain")
    ax1.set_xlabel("Longitude")
    ax1.set_ylabel("Latitude")
    ax1.set_xlim(8.0, 13.0)
    ax1.set_ylim(43.0, 46.0)

    for rgb, (tlon_min, tlon_max, tlat_min, tlat_max) in dem_tiles:
        ax2.imshow(rgb, extent=[tlon_min, tlon_max, tlat_min, tlat_max], origin="upper")
    ax2.set_xlim(zoom_lon_min, zoom_lon_max)
    ax2.set_ylim(zoom_lat_min, zoom_lat_max)
    ax2.scatter(bologna_meta["lon"], bologna_meta["lat"], s=28, c="#bbbbbb", ec="white", lw=0.25, alpha=0.9, label="Bologna well stations")
    ax2.scatter(trusted["lon"], trusted["lat"], s=110, marker="*", c="gold", ec="black", lw=0.7, label="Trusted validation wells")
    ax2.add_patch(
        Rectangle(
            (box_lon_min, box_lat_min),
            box_lon_max - box_lon_min,
            box_lat_max - box_lat_min,
            fill=False,
            ec="red",
            lw=1.6,
        )
    )
    ax2.set_title("Zoom on Bologna overlap and validation wells")
    ax2.set_xlabel("Longitude")
    ax2.set_ylabel("Latitude")
    ax2.legend(loc="lower left", frameon=True)

    return save(fig, "figure_1_study_area_dtm_wells.png")


def figure_2_workflow() -> Path:
    fig, ax = plt.subplots(figsize=(14, 7))
    ax.axis("off")

    boxes = [
        (0.03, 0.63, 0.18, 0.21, "Synthetic pre-stage\n5-layer W3RA-like states\n[S0, Ss, Sd, Sg, Sr]"),
        (0.28, 0.63, 0.18, 0.21, "Forward hydro-\nmechanical physics\nDeformation-space predictors"),
        (0.53, 0.63, 0.18, 0.21, "Synthetic Stage 1\nMCMC validation\nKnown-truth recovery"),
        (0.78, 0.63, 0.18, 0.21, "Optional synthetic Stage 2\nResidual / lag diagnostic\nExploratory"),
        (0.03, 0.17, 0.18, 0.21, "Real MintPy InSAR\nanomalies\nBologna overlap"),
        (0.28, 0.17, 0.18, 0.21, "W3RA grouped prior\n[S0+Ss, Sd+Sr, Sg]\nShared 22 x 24 grid"),
        (0.53, 0.17, 0.18, 0.21, "External constraints\nGRACE + SMAP\n+ exploratory SWOT"),
        (0.78, 0.17, 0.18, 0.21, "Grouped Stage 1 posterior\nIndependent well validation\nMain supported result"),
    ]
    for x, y, w, h, txt in boxes:
        patch = FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.02", fc="#f7f7f7", ec="#333333", lw=1.5)
        ax.add_patch(patch)
        ax.text(x + w / 2, y + h / 2, txt, ha="center", va="center", fontsize=11)

    arrows = [
        ((0.21, 0.735), (0.28, 0.735)),
        ((0.46, 0.735), (0.53, 0.735)),
        ((0.71, 0.735), (0.78, 0.735)),
        ((0.21, 0.275), (0.28, 0.275)),
        ((0.46, 0.275), (0.53, 0.275)),
        ((0.71, 0.275), (0.78, 0.275)),
    ]
    for (x0, y0), (x1, y1) in arrows:
        ax.annotate("", xy=(x1, y1), xytext=(x0, y0), arrowprops=dict(arrowstyle="->", lw=2))

    ax.text(
        0.5,
        0.49,
        "Synthetic pre-stage validates the inversion machinery; the applied Bologna estimator becomes grouped and is externally validated with wells.",
        ha="center",
        va="center",
        fontsize=12,
        fontweight="bold",
    )
    return save(fig, "figure_2_workflow_schematic.png")


def figure_3_synthetic(synth_summary: dict) -> Path:
    rows = pd.DataFrame(
        [
            {"metric": "Sg state $R^2$", "value": synth_summary["state_metrics"]["Sg"]["r2"]},
            {"metric": "Load total $R^2$", "value": synth_summary["derived_state_metrics"]["Load_total"]["r2"]},
            {"metric": "TWS $R^2$", "value": synth_summary["derived_state_metrics"]["TWS"]["r2"]},
            {"metric": "Deformation $R^2$", "value": synth_summary["deformation_metrics"]["r2"]},
        ]
    )
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.6), constrained_layout=True)
    axes[0].bar(rows["metric"], rows["value"], color=["#1b9e77", "#d95f02", "#7570b3", "#4c78a8"])
    axes[0].set_ylim(0, 1.05)
    axes[0].set_ylabel("$R^2$")
    axes[0].set_title("Synthetic Stage 1 skill")
    axes[0].tick_params(axis="x", rotation=20)

    txt = (
        f"Grid: {synth_summary['shape']['height']} x {synth_summary['shape']['width']}\n"
        f"Times: {synth_summary['shape']['time']}\n"
        f"Layers: {synth_summary['shape']['layers']}\n"
        f"Noise scale: {synth_summary['config']['noise_scale']}\n\n"
        "Interpretation:\n"
        "- Stage 1 recovers grouped synthetic states strongly\n"
        "- Deformation reconstruction is excellent\n"
        "- Synthetic success supports the machinery,\n  but does not by itself prove real-data identifiability"
    )
    axes[1].axis("off")
    axes[1].text(0.02, 0.98, txt, va="top", ha="left", fontsize=11)
    return save(fig, "figure_3_synthetic_validation.png")


def figure_4_grouped_results(
    tiled_npz: np.lib.npyio.NpzFile,
    regional_npz: np.lib.npyio.NpzFile,
    w3ra_path: Path,
) -> Path:
    state_names = [str(s) for s in tiled_npz["state_names"].tolist()]
    fig, axes = plt.subplots(2, 3, figsize=(14, 8), constrained_layout=True)
    t_idx = -1

    import xarray as xr

    with xr.open_dataset(w3ra_path) as ds:
        z_state = np.stack(
            [
                (ds["S0"].values + ds["Ss"].values).astype(np.float64),
                (ds["Sd"].values + ds["Sr"].values).astype(np.float64),
                ds["Sg"].values.astype(np.float64),
            ],
            axis=1,
        )
        lat = ds["lat"].values.astype(np.float64)
        lon = ds["lon"].values.astype(np.float64)

    _, _, h, w = z_state.shape
    ny, nx = tiled_npz["lat_tiles"].shape
    y_pos = tile_positions(h, 8, 8)
    x_pos = tile_positions(w, 8, 8)
    full_recon = np.zeros((len(state_names), h, w), dtype=np.float64)
    full_count = np.zeros((len(state_names), h, w), dtype=np.float64)
    for iy, y0 in enumerate(y_pos[:ny]):
        for ix, x0 in enumerate(x_pos[:nx]):
            y1 = min(y0 + 8, h)
            x1 = min(x0 + 8, w)
            theta_tile = tiled_npz["theta_tiles"][t_idx, :, iy, ix]
            full_recon[:, y0:y1, x0:x1] += theta_tile[:, None, None] * z_state[t_idx, :, y0:y1, x0:x1]
            full_count[:, y0:y1, x0:x1] += 1.0
    full_recon = np.divide(full_recon, np.where(full_count == 0, np.nan, full_count))

    for j, name in enumerate(state_names):
        im = axes[0, j].pcolormesh(
            lon,
            lat,
            full_recon[j],
            shading="auto",
            cmap="RdBu_r",
        )
        axes[0, j].set_title(f"{name} posterior reconstruction\n{pd.to_datetime(tiled_npz['time'][t_idx]).date()}")
        axes[0, j].set_xlabel("Longitude")
        axes[0, j].set_ylabel("Latitude")
        cbar = plt.colorbar(im, ax=axes[0, j], shrink=0.8)
        cbar.set_label("mm")

    ts = pd.to_datetime(regional_npz["time"])
    for ax, obs_key, prior_key, post_key, title in [
        (axes[1, 0], "y_insar", "y_insar_prior", "y_insar_post", "InSAR"),
        (axes[1, 1], "y_grace", "y_grace_prior", "y_grace_post", "GRACE"),
        (axes[1, 2], "y_smap", "y_smap_prior", "y_smap_post", "SMAP"),
    ]:
        ax.plot(ts, regional_npz[obs_key], label="Observed", lw=1.7)
        ax.plot(ts, regional_npz[prior_key], label="Prior", lw=1.0, alpha=0.8)
        ax.plot(ts, regional_npz[post_key], label="Posterior", lw=1.7)
        ax.set_title(title)
        ax.tick_params(axis="x", rotation=25)
    axes[1, 0].legend(loc="best")
    return save(fig, "figure_4_grouped_stage1_results.png")


def figure_5_well_validation_map(
    all_meta: pd.DataFrame,
    well_summary: pd.DataFrame,
    trusted: pd.DataFrame,
    by_depth: pd.DataFrame,
    lag_state: pd.DataFrame,
) -> Path:
    trusted_plot = trusted[trusted["corr_anom"] >= 0.6].copy()

    fig = plt.figure(figsize=(14, 8.8), constrained_layout=True)
    gs = fig.add_gridspec(2, 2, width_ratios=[1.85, 0.95], height_ratios=[1.0, 1.2])
    ax = fig.add_subplot(gs[:, 0])
    ax2 = fig.add_subplot(gs[0, 1])
    ax3 = fig.add_subplot(gs[1, 1])

    ax.scatter(
        all_meta["lon"],
        all_meta["lat"],
        s=10,
        c="#9a9a9a",
        alpha=0.5,
        linewidths=0,
        label="Other Emilia-Romagna wells",
    )
    sc = ax.scatter(
        trusted_plot["lon"],
        trusted_plot["lat"],
        s=90,
        c=trusted_plot["corr_anom"],
        cmap="viridis",
        vmin=0.6,
        vmax=1.0,
        edgecolors="black",
        linewidths=0.45,
        label="Trusted wells (corr >= 0.6)",
        zorder=3,
    )
    ax.scatter(
        trusted_plot["lon"],
        trusted_plot["lat"],
        s=55,
        marker="*",
        c="none",
        edgecolors="black",
        linewidths=0.75,
        label="Trusted wells starred",
        zorder=4,
    )
    ax.set_xlabel("Longitude")
    ax.set_ylabel("Latitude")
    ax.set_title("Trusted well validation map")
    ax.legend(loc="lower left", frameon=True)
    cb = fig.colorbar(sc, ax=ax, shrink=0.78)
    cb.set_label("Trusted-well correlation")

    order = ["deep", "intermediate", "shallow"]
    depth_vals = [
        well_summary.loc[well_summary["depth_class"] == depth_class, "corr_anom"].dropna().values
        for depth_class in order
    ]
    parts = ax2.violinplot(depth_vals, positions=np.arange(1, len(order) + 1), widths=0.8, showmeans=False, showmedians=True, showextrema=False)
    violin_colors = ["#4c78a8", "#f58518", "#54a24b"]
    for body, color in zip(parts["bodies"], violin_colors):
        body.set_facecolor(color)
        body.set_edgecolor("black")
        body.set_alpha(0.45)
        body.set_linewidth(0.7)
    if "cmedians" in parts:
        parts["cmedians"].set_color("black")
        parts["cmedians"].set_linewidth(1.6)
    for i, vals in enumerate(depth_vals, start=1):
        if len(vals):
            jitter = np.linspace(-0.12, 0.12, len(vals)) if len(vals) > 1 else np.array([0.0])
            ax2.scatter(np.full(len(vals), i) + jitter, vals, s=16, c="black", alpha=0.35, linewidths=0, zorder=3)
    ax2.set_xticks(np.arange(1, len(order) + 1))
    ax2.set_xticklabels(order)
    ax2.set_ylim(0, 1.0)
    ax2.set_ylabel("Best-match anomaly correlation")
    ax2.set_title("Validation by depth class")

    pivot = lag_state.pivot(index="best_lag_days", columns="best_state", values="n_series").fillna(0)
    pivot.plot(kind="bar", stacked=True, ax=ax3, colormap="tab10")
    ax3.set_title("Best lag / best state counts")
    ax3.set_xlabel("Best lag (days)")
    ax3.set_ylabel("Number of wells")
    ax3.legend(title="Best state", fontsize=8, ncol=3, loc="upper center")

    return save(fig, "figure_5_well_validation_map.png")


def figure_6_best_wells(trusted: pd.DataFrame, station_series_dir: Path) -> Path:
    top = trusted.sort_values(["corr_anom", "n_matches"], ascending=[False, False]).head(6).copy()
    fig, axes = plt.subplots(3, 2, figsize=(14, 10), constrained_layout=True)
    axes = axes.ravel()
    for ax, (_, row) in zip(axes, top.iterrows()):
        path = station_series_dir / f"{row['station_code']}_{row['measurement_type']}.csv"
        ser = pd.read_csv(path, parse_dates=["date"])
        ax.plot(ser["date"], ser["model_anom_z"], lw=1.6, label="Model")
        ax.plot(ser["date"], ser["obs_anom_z"], lw=1.6, label="Well")
        ax.set_title(f"{row['station_code']} | corr={row['corr_anom']:.3f} | lag={int(row['best_lag_days'])}d")
        ax.tick_params(axis="x", rotation=25)
        ax.set_ylabel("z-anomaly")
    axes[0].legend(loc="best")
    return save(fig, "figure_6_best_well_timeseries.png")


def figure_s7_selected_wells_overview(
    all_meta: pd.DataFrame,
    trusted: pd.DataFrame,
    station_series_dir: Path,
) -> Path:
    top = trusted.sort_values(["corr_anom", "n_matches"], ascending=[False, False]).head(9).copy()

    fig = plt.figure(figsize=(18, 12), constrained_layout=True)
    gs = fig.add_gridspec(3, 4, width_ratios=[1.35, 1.0, 1.0, 1.0])
    ax_map = fig.add_subplot(gs[:, 0])
    ts_axes = [fig.add_subplot(gs[i, j]) for i in range(3) for j in range(1, 4)]

    ax_map.scatter(
        all_meta["lon"],
        all_meta["lat"],
        s=9,
        c="#9a9a9a",
        alpha=0.55,
        linewidths=0,
        label="All Emilia-Romagna wells",
    )
    ax_map.scatter(
        top["lon"],
        top["lat"],
        s=145,
        marker="*",
        c="#d62728",
        edgecolors="black",
        linewidths=0.6,
        label="Selected top-9 wells",
        zorder=5,
    )
    for _, row in top.iterrows():
        ax_map.text(
            row["lon"] + 0.03,
            row["lat"] + 0.02,
            row["station_code"],
            color="#8b0000",
            fontsize=8,
            weight="bold",
            zorder=6,
        )
    ax_map.set_title("Emilia-Romagna well network with selected stations")
    ax_map.set_xlabel("Longitude")
    ax_map.set_ylabel("Latitude")
    ax_map.legend(loc="lower left", frameon=True)

    for ax, (_, row) in zip(ts_axes, top.iterrows()):
        path = station_series_dir / f"{row['station_code']}_{row['measurement_type']}.csv"
        ser = pd.read_csv(path, parse_dates=["date"])
        ax.plot(ser["date"], ser["model_anom_z"], lw=1.5, color="#1f77b4", label="Model")
        ax.plot(ser["date"], ser["obs_anom_z"], lw=1.5, color="#ff7f0e", label="Well")
        ax.set_title(f"{row['station_code']} | corr={row['corr_anom']:.3f} | lag={int(row['best_lag_days'])}d")
        ax.tick_params(axis="x", rotation=25)
        ax.set_ylabel("z-anomaly")
    ts_axes[0].legend(loc="best")

    return save(fig, "figure_s7_selected_wells_overview.png")


def figure_s1_trusted_aquifer_groups(trusted_gwb: pd.DataFrame) -> Path:
    df = trusted_gwb.sort_values("median_corr", ascending=True)
    fig, ax = plt.subplots(figsize=(10, 6), constrained_layout=True)
    ax.barh(df["gwb_name"], df["median_corr"], color="#4c78a8")
    ax.set_xlim(0, 1)
    ax.set_xlabel("Median correlation")
    ax.set_title("Trusted hydrogeologic groups")
    return save(fig, "figure_s1_trusted_aquifer_groups.png")


def figure_s2_lag_histogram(lag_state: pd.DataFrame) -> Path:
    pivot = lag_state.pivot(index="best_lag_days", columns="best_state", values="n_series").fillna(0)
    fig, ax = plt.subplots(figsize=(9, 5), constrained_layout=True)
    pivot.plot(kind="bar", stacked=True, ax=ax, colormap="tab10")
    ax.set_xlabel("Best lag (days)")
    ax.set_ylabel("Number of wells")
    ax.set_title("Lag histogram by best state")
    ax.legend(title="Best state")
    return save(fig, "figure_s2_lag_histogram.png")


def figure_s3_depth_summary(by_depth: pd.DataFrame) -> Path:
    fig, ax1 = plt.subplots(figsize=(8, 5), constrained_layout=True)
    x = np.arange(len(by_depth))
    width = 0.38
    ax1.bar(x - width / 2, by_depth["median_corr"], width, label="Median corr", color="#4c78a8")
    ax1.bar(x + width / 2, by_depth["mean_corr"], width, label="Mean corr", color="#f58518")
    ax1.set_xticks(x)
    ax1.set_xticklabels(by_depth["depth_class"])
    ax1.set_ylim(0, 1)
    ax1.set_ylabel("Correlation")
    ax1.set_title("Depth-class validation summary")
    ax1.legend(loc="upper left")
    return save(fig, "figure_s3_depth_class_summary.png")


def figure_s4_conditioning(cond_summary: dict) -> Path:
    labels = ["Old 5-layer", "Old grouped", "Current grouped"]
    cond_j = [
        cond_summary["old_five_layer_patch"]["raw"]["condition_number"],
        cond_summary["old_grouped_patch"]["raw"]["condition_number"],
        cond_summary["current_grouped_kalman"]["stacked_operator"]["condition_number"],
    ]
    spread = [
        cond_summary["old_five_layer_patch"]["raw"]["column_scale_spread"],
        cond_summary["old_grouped_patch"]["raw"]["column_scale_spread"],
        cond_summary["current_grouped_kalman"]["stacked_operator"]["column_scale_spread"],
    ]
    corr_max = [
        np.nanmax(np.abs(pd.DataFrame(cond_summary["old_five_layer_patch"]["raw"]["column_correlation"]).astype(float).values - np.eye(5))),
        np.nanmax(np.abs(pd.DataFrame(cond_summary["old_grouped_patch"]["raw"]["column_correlation"]).astype(float).values - np.eye(2))),
        np.nanmax(np.abs(pd.DataFrame(cond_summary["current_grouped_kalman"]["stacked_operator"]["column_correlation"]).astype(float).values - np.eye(3))),
    ]

    fig, axes = plt.subplots(1, 3, figsize=(14, 4.8), constrained_layout=True)
    axes[0].bar(labels, cond_j, color=["#b2182b", "#ef8a62", "#4d9221"])
    axes[0].set_yscale("log")
    axes[0].set_title("Operator condition number")
    axes[0].tick_params(axis="x", rotation=20)

    axes[1].bar(labels, spread, color=["#b2182b", "#ef8a62", "#4d9221"])
    axes[1].set_yscale("log")
    axes[1].set_title("Column-scale spread")
    axes[1].tick_params(axis="x", rotation=20)

    axes[2].bar(labels, corr_max, color=["#b2182b", "#ef8a62", "#4d9221"])
    axes[2].set_ylim(0, 1)
    axes[2].set_title("Max off-diagonal |corr|")
    axes[2].tick_params(axis="x", rotation=20)

    return save(fig, "figure_s4_conditioning_comparison.png")


def figure_s5_swot(swot_summary: dict, bundle_full_summary: dict) -> Path:
    raw = [swot_summary["river_times"], swot_summary["lake_times"]]
    matched = [bundle_full_summary["swot_river_non_null"], bundle_full_summary["swot_lake_non_null"]]
    x = np.arange(2)
    width = 0.38
    fig, ax = plt.subplots(figsize=(8, 5), constrained_layout=True)
    ax.bar(x - width / 2, raw, width, label="Raw SWOT dates", color="#4c78a8")
    ax.bar(x + width / 2, matched, width, label="Dates retained after nearest-date fusion", color="#f58518")
    ax.set_xticks(x)
    ax.set_xticklabels(["RiverSP", "LakeSP"])
    ax.set_ylabel("Number of dates")
    ax.set_title("SWOT overlap and matched-date retention")
    ax.legend()
    return save(fig, "figure_s5_swot_overlap_summary.png")


def figure_s6_emilia_wells(all_meta: pd.DataFrame, trusted: pd.DataFrame) -> Path:
    fig, ax = plt.subplots(figsize=(8.5, 6), constrained_layout=True)
    ax.scatter(all_meta["lon"], all_meta["lat"], s=14, c="#6e6e6e", alpha=0.65, linewidths=0)
    ax.scatter(trusted["lon"], trusted["lat"], s=145, marker="*", c="gold", edgecolors="black", linewidths=0.8)
    ax.set_xlabel("Longitude")
    ax.set_ylabel("Latitude")
    ax.set_title("Emilia-Romagna well network with trusted Bologna subset")
    return save(fig, "figure_s6_emilia_romagna_wells_overview.png")


def make_tables_markdown(
    regional_summary: dict,
    tiled_summary: dict,
    synth_summary: dict,
    well_overview: dict,
    by_depth: pd.DataFrame,
    by_gwb: pd.DataFrame,
    trusted: pd.DataFrame,
    trusted_gwb: pd.DataFrame,
    cond_summary: dict,
    swot_summary: dict,
    bundle_full_summary: dict,
) -> str:
    def df_to_markdown(df: pd.DataFrame) -> str:
        cols = [str(c) for c in df.columns]
        header = "| " + " | ".join(cols) + " |"
        sep = "| " + " | ".join(["---"] * len(cols)) + " |"
        rows = []
        for _, row in df.iterrows():
            vals = []
            for v in row.tolist():
                if isinstance(v, float):
                    if math.isfinite(v):
                        vals.append(f"{v:.4f}")
                    else:
                        vals.append("")
                else:
                    vals.append(str(v))
            rows.append("| " + " | ".join(vals) + " |")
        return "\n".join([header, sep] + rows)

    table1 = pd.DataFrame(
        [
            ["InSAR", "MintPy time series", "2017-01-04 to 2025-06-27, 394 acquisitions, 555 interferograms", "LOS deformation", "Main observation stream", "MintPy inversion; anomalies; aggregated to W3RA grid"],
            ["W3RA", "Local W3RA overlap products", "2017-01-04 to 2024-08-01, shared 22 x 24 grid", "S0, Ss, Sd, Sg, Sr", "Model prior / grouped state basis", "Overlap construction and anomaly conversion"],
            ["GRACE", "JPL mascon RL06.3", "362 aligned overlap dates", "lwe_thickness anomaly", "Regional TWS-like constraint", "Regional mean over overlap bbox"],
            ["SMAP", "SPL3SMP_E", "358 downloads, 254 valid dates", "Surface soil moisture", "Shallow hydrologic constraint", "Regional mean over overlap bbox"],
            ["SWOT", "RiverSP + LakeSP", "33 river dates / 34 lake dates, 9 retained after nearest-date fusion", "Surface-water summaries", "Exploratory surface-water constraint", "BBox subset and nearest-date matching"],
            ["Wells", "ARPAE manual + automatic", "2009-01-01 to 2024-12-18", "Piezometric head, depth to water", "Independent validation", "Metadata merge, lon/lat conversion, lagged anomaly comparison"],
        ],
        columns=["Dataset", "Product / source", "Coverage used", "Variables used", "Role in study", "Preprocessing before assimilation"],
    )

    table2 = pd.DataFrame(
        [
            ["Synthetic Stage 1", "[S0, Ss, Sd, Sg, Sr]", "Synthetic deformation Y and model-side Z", "Validate inversion machinery", "Posterior synthetic state and deformation skill"],
            ["Synthetic Stage 2", "Residual / lag refinement", "Synthetic InSAR window + Stage 1 prior", "Check whether learned residuals add value", "Exploratory residual diagnostic"],
            ["Real grouped Stage 1", "[S0+Ss, Sd+Sr, Sg]", "InSAR + GRACE + refreshed SMAP", "Stable applied estimator", "Grouped posterior state"],
            ["Exploratory SWOT extension", "[S0+Ss, Sd+Sr, Sg]", "InSAR + GRACE + SMAP + SWOT", "Test added surface-water information", "No material improvement under sparse overlap"],
            ["Well validation", "Grouped posterior vs well anomalies", "ARPAE manual + automatic wells", "Independent support for groundwater signal", "Station-wise lagged correlations and trusted subset"],
        ],
        columns=["Stage", "State formulation", "Observations", "Goal", "Output"],
    )

    table3 = pd.DataFrame(
        [
            ["Regional InSAR posterior $R^2$", regional_summary["metrics"]["insar_post"]["r2"]],
            ["Regional GRACE posterior $R^2$", regional_summary["metrics"]["grace_post"]["r2"]],
            ["Regional SMAP posterior $R^2$", regional_summary["metrics"]["smap_post"]["r2"]],
            ["Tiled InSAR posterior $R^2$", tiled_summary["metrics"]["tile_insar_post"]["r2"]],
            ["max |ShallowLoad| (mm)", tiled_summary["magnitude"]["ShallowLoad"]["x_abs_max"]],
            ["max |DeepLoad| (mm)", tiled_summary["magnitude"]["DeepLoad"]["x_abs_max"]],
            ["max |Groundwater| (mm)", tiled_summary["magnitude"]["Groundwater"]["x_abs_max"]],
            ["Well series evaluated", well_overview["n_station_series_evaluated"]],
            ["Median well correlation", well_overview["median_corr"]],
            ["Wells with corr >= 0.3", well_overview["n_corr_ge_0_3"]],
            ["Wells with corr >= 0.5", well_overview["n_corr_ge_0_5"]],
            ["Trusted groups / stations", f"{well_overview['n_trusted_gwb_groups']} / {well_overview['n_trusted_stations']}"],
        ],
        columns=["Metric", "Value"],
    )

    table_s1 = by_gwb.sort_values("median_corr", ascending=False).head(15).copy()
    table_s2 = trusted[["station_code", "municipality", "gwb_name", "depth_class", "n_matches", "corr_anom", "best_lag_days"]].copy()
    table_s3 = pd.DataFrame(
        [
            ["Old 5-layer patch", cond_summary["old_five_layer_patch"]["raw"]["condition_number"], cond_summary["old_five_layer_patch"]["raw"]["information_condition_number"], cond_summary["old_five_layer_patch"]["raw"]["effective_rank_1e-6"], cond_summary["old_five_layer_patch"]["raw"]["column_scale_spread"]],
            ["Old grouped patch", cond_summary["old_grouped_patch"]["raw"]["condition_number"], cond_summary["old_grouped_patch"]["raw"]["information_condition_number"], cond_summary["old_grouped_patch"]["raw"]["effective_rank_1e-6"], cond_summary["old_grouped_patch"]["raw"]["column_scale_spread"]],
            ["Current grouped multisensor", cond_summary["current_grouped_kalman"]["stacked_operator"]["condition_number"], cond_summary["current_grouped_kalman"]["stacked_operator"]["information_condition_number"], cond_summary["current_grouped_kalman"]["stacked_operator"]["effective_rank_1e-6"], cond_summary["current_grouped_kalman"]["stacked_operator"]["column_scale_spread"]],
        ],
        columns=["Formulation", "kappa(J)", "kappa(I)", "Effective rank", "Scale spread"],
    )
    table_s4 = pd.DataFrame(
        [
            ["RiverSP raw dates", swot_summary["river_times"]],
            ["LakeSP raw dates", swot_summary["lake_times"]],
            ["RiverSP dates retained after nearest-date fusion", bundle_full_summary["swot_river_non_null"]],
            ["LakeSP dates retained after nearest-date fusion", bundle_full_summary["swot_lake_non_null"]],
            ["Nearest-date tolerance (days)", bundle_full_summary["swot_max_gap_days"]],
        ],
        columns=["SWOT overlap metric", "Value"],
    )
    table_s5 = pd.DataFrame(
        [
            ["Sg state $R^2$", synth_summary["state_metrics"]["Sg"]["r2"]],
            ["Load total $R^2$", synth_summary["derived_state_metrics"]["Load_total"]["r2"]],
            ["TWS $R^2$", synth_summary["derived_state_metrics"]["TWS"]["r2"]],
            ["Deformation $R^2$", synth_summary["deformation_metrics"]["r2"]],
        ],
        columns=["Synthetic metric", "Value"],
    )

    parts = []
    parts.append("# Paper Figures, Tables, and Captions\n")
    parts.append("## Main figures\n")
    fig_caps = [
        ("figure_1.png", "Study area and validation setting. Left: DTM background for the broader Bologna scene with the shared InSAR/W3RA overlap marked by a red box. Right: zoom on the overlap domain showing Bologna well stations, with the trusted validation subset highlighted by stars."),
        ("figure_2.png", "Overall study workflow. The synthetic pre-stage validates the deformation-space inversion machinery under known truth, whereas the real-data branch uses the grouped state [S0+Ss, Sd+Sr, Sg], assimilates InSAR, GRACE, and refreshed SMAP (with SWOT as an exploratory extension), and validates the grouped groundwater posterior against wells."),
        ("figure_3.png", "Compact synthetic validation summary. The deformation-space Stage 1 inversion achieves strong recovery in the model-consistent synthetic setting, especially for grouped states and deformation skill."),
        ("figure_4.png", "Main grouped Stage 1 result for the Bologna overlap. Top: full-grid posterior reconstructions for ShallowLoad, DeepLoad, and Groundwater on the final overlap date, obtained by projecting the tiled grouped posterior back onto the shared 22 x 24 grid. Bottom: observed, prior, and posterior regional time-series comparisons for InSAR, GRACE, and SMAP."),
        ("figure_5.png", "Independent well validation of the grouped posterior. Gray dots show the broader Emilia-Romagna well network, while the trusted Bologna wells with correlation greater than or equal to 0.6 are highlighted as small colored dots and starred markers. The lower panel summarizes the best-lag / best-state distribution, and the upper-right panel summarizes depth-class validation."),
        ("figure_6.png", "Representative well time-series comparisons for the strongest trusted stations. Blue curves denote the grouped model anomaly and orange curves denote standardized well-head anomalies."),
    ]
    for name, cap in fig_caps:
        parts.append(f"- `{name}`: {cap}\n")

    parts.append("\n## Supplementary figures\n")
    supp_caps = [
        ("figure_s1.png", "Trusted hydrogeologic groups ranked by median well correlation."),
        ("figure_s2.png", "Histogram of best lag by best-matching grouped state across validated wells."),
        ("figure_s3.png", "Depth-class validation summary showing mean and median anomaly correlation."),
        ("figure_s4.png", "Conditioning comparison across the old layered patch, old grouped patch, and current grouped multisensor formulation, using operator condition number, column-scale spread, and maximum off-diagonal column correlation."),
        ("figure_s5.png", "SWOT overlap diagnostic showing the reduction from raw river/lake dates to matched dates retained in the nearest-date multisensor bundle."),
        ("figure_s6.png", "Static overview of the Emilia-Romagna well network with the trusted Bologna subset highlighted."),
        ("figure_s7.png", "Overview of nine selected trusted wells. Left: regional well network with the selected stations marked by red stars. Right: model-versus-well anomaly time-series comparisons for the same nine stations."),
    ]
    for name, cap in supp_caps:
        parts.append(f"- `{name}`: {cap}\n")

    def add_table(title: str, caption: str, df: pd.DataFrame):
        parts.append(f"\n## {title}\n\n")
        parts.append(f"{caption}\n\n")
        parts.append(df_to_markdown(df))
        parts.append("\n")

    add_table("Table 1", "Data summary used in the main paper.", table1)
    add_table("Table 2", "Synthetic and real experiment-block summary.", table2)
    add_table("Table 3", "Main quantitative results table for the main paper.", table3)
    add_table("Table S1", "Hydrogeologic group validation summary (top groups by median correlation).", table_s1)
    add_table("Table S2", "Trusted wells subset used for the core interpretation.", table_s2)
    add_table("Table S3", "Conditioning diagnostics before and after grouping / balancing.", table_s3)
    add_table("Table S4", "SWOT overlap and matched-date summary.", table_s4)
    add_table("Table S5", "Synthetic validation metrics supporting the pre-stage feasibility check.", table_s5)

    return "".join(parts)


def make_notebook() -> None:
    nb = {
        "cells": [
            {
                "cell_type": "markdown",
                "metadata": {},
                "source": [
                    "# Paper Figures Notebook\n",
                    "\n",
                    "This notebook collects the exported main and supplementary figures and points to the table/caption markdown file in `paper_figures`.\n",
                ],
            },
            {
                "cell_type": "code",
                "execution_count": None,
                "metadata": {},
                "outputs": [],
                "source": [
                    "from pathlib import Path\n",
                    "from IPython.display import Image as IPyImage, display, Markdown\n",
                    "ROOT = Path('/home/ubuntu/work/insar_mcmc/paper_figures')\n",
                    "CAPTION_FILE = ROOT / 'FIGURE_TABLE_CAPTIONS.md'\n",
                    "print('Caption/tables file:', CAPTION_FILE)\n",
                ],
            },
            {
                "cell_type": "markdown",
                "metadata": {},
                "source": ["## Main figures\n"],
            },
            {
                "cell_type": "code",
                "execution_count": None,
                "metadata": {},
                "outputs": [],
                "source": [
                    "for name in [\n",
                    "    'figure_1.png',\n",
                    "    'figure_2.png',\n",
                    "    'figure_3.png',\n",
                    "    'figure_4.png',\n",
                    "    'figure_5.png',\n",
                    "    'figure_6.png',\n",
                    "]:\n",
                    "    path = ROOT / name\n",
                    "    print(path)\n",
                    "    display(IPyImage(filename=str(path)))\n",
                ],
            },
            {
                "cell_type": "markdown",
                "metadata": {},
                "source": ["## Supplementary figures\n"],
            },
            {
                "cell_type": "code",
                "execution_count": None,
                "metadata": {},
                "outputs": [],
                "source": [
                    "for name in [\n",
                    "    'figure_s1.png',\n",
                    "    'figure_s2.png',\n",
                    "    'figure_s3.png',\n",
                    "    'figure_s4.png',\n",
                    "    'figure_s5.png',\n",
                    "    'figure_s6.png',\n",
                    "    'figure_s7.png',\n",
                    "]:\n",
                    "    path = ROOT / name\n",
                    "    print(path)\n",
                    "    display(IPyImage(filename=str(path)))\n",
                ],
            },
            {
                "cell_type": "markdown",
                "metadata": {},
                "source": ["## Tables and captions\n"],
            },
            {
                "cell_type": "code",
                "execution_count": None,
                "metadata": {},
                "outputs": [],
                "source": [
                    "display(Markdown(CAPTION_FILE.read_text()))\n",
                ],
            },
        ],
        "metadata": {
            "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
            "language_info": {"name": "python", "version": "3.x"},
        },
        "nbformat": 4,
        "nbformat_minor": 5,
    }
    with open(OUTDIR / "paper_figures_notebook.ipynb", "w") as f:
        json.dump(nb, f, indent=1)


def main() -> None:
    overlap_summary = load_json(ROOT / "outputs_bologna_2025_overlap" / "bologna_mintpy2025_w3ra_overlap_summary.json")
    synth_summary = load_json(ROOT / "outputs_stage1_pure" / "stage1_pure_synthetic_summary.json")
    regional_summary = load_json(ROOT / "outputs_stage1_bologna_multisensor_kalman_overlap2025_smaprefresh" / "stage1_bologna_multisensor_kalman_summary.json")
    tiled_summary = load_json(ROOT / "outputs_stage1_bologna_multisensor_kalman_tiled_overlap2025_smaprefresh" / "stage1_bologna_multisensor_kalman_tiled_summary.json")
    well_overview = load_json(ROOT / "outputs_well_validation" / "well_groundwater_validation_overview.json")
    cond_summary = load_json(ROOT / "outputs_conditioning_diagnostics" / "conditioning_diagnostics_summary.json")
    swot_summary = load_json(ROOT / "outputs_external_constraints" / "swot_bologna_overlap2025" / "swot_bologna_overlap_summary.json")
    bundle_full_summary = load_json(ROOT / "outputs_external_constraints_overlap2025" / "multisensor_bundle_full" / "bologna_grouped_multisensor_bundle_summary.json")

    all_meta = pd.read_csv(ROOT / "outputs_external_bologna_wells" / "processed" / "station_metadata_combined.csv").drop_duplicates("station_code")
    bologna_meta = all_meta.loc[all_meta["province"] == "BO"].copy()
    well_summary = pd.read_csv(ROOT / "outputs_well_validation" / "well_groundwater_validation_summary.csv")
    trusted = pd.read_csv(ROOT / "outputs_well_validation" / "well_groundwater_validation_trusted_stations.csv")
    by_depth = pd.read_csv(ROOT / "outputs_well_validation" / "well_groundwater_validation_by_depth.csv")
    by_gwb = pd.read_csv(ROOT / "outputs_well_validation" / "well_groundwater_validation_by_gwb.csv")
    trusted_gwb = pd.read_csv(ROOT / "outputs_well_validation" / "well_groundwater_validation_trusted_gwb.csv")
    lag_state = pd.read_csv(ROOT / "outputs_well_validation" / "well_groundwater_validation_lag_state_counts.csv")

    tiled_npz = np.load(ROOT / "outputs_stage1_bologna_multisensor_kalman_tiled_overlap2025_smaprefresh" / "stage1_bologna_multisensor_kalman_tiled_results.npz")
    regional_npz = np.load(ROOT / "outputs_stage1_bologna_multisensor_kalman_overlap2025_smaprefresh" / "stage1_bologna_multisensor_kalman_results.npz")

    dem_paths = [
        Path("/mnt/data/aoi_3_bologna/S1AA_20230912T052800_20230924T052800_VVP012_INT80_G_ueF_3BD3/S1AA_20230912T052800_20230924T052800_VVP012_INT80_G_ueF_3BD3_dem_clipped.tif"),
        Path("/mnt/data/aoi_3_02_bologna/S1AA_20170129T051855_20170210T051854_VVP012_INT80_G_weF_8A34_1/S1AA_20170129T051855_20170210T051854_VVP012_INT80_G_weF_8A34_dem.tif"),
        Path("/mnt/data/aoi_3_02_bologna/S1AB_20200618T051929_20200624T051847_VVP006_INT80_G_weF_B2AB_1/S1AB_20200618T051929_20200624T051847_VVP006_INT80_G_weF_B2AB_dem.tif"),
        Path("/mnt/data/aoi_3_bologna/S1AB_20170603T052718_20170609T052645_VVP006_INT80_G_ueF_4421/S1AB_20170603T052718_20170609T052645_VVP006_INT80_G_ueF_4421_dem.tif"),
    ]

    figure_1_area_dtm(overlap_summary, dem_paths, all_meta, bologna_meta, trusted)
    figure_2_workflow()
    figure_3_synthetic(synth_summary)
    figure_4_grouped_results(
        tiled_npz,
        regional_npz,
        ROOT / "outputs_bologna_2025_overlap" / "w3ra_on_mintpy2025_overlap_anom.nc",
    )
    figure_5_well_validation_map(all_meta, well_summary, trusted, by_depth, lag_state)
    figure_6_best_wells(trusted, ROOT / "outputs_well_validation" / "station_series")

    figure_s1_trusted_aquifer_groups(trusted_gwb)
    figure_s2_lag_histogram(lag_state)
    figure_s3_depth_summary(by_depth)
    figure_s4_conditioning(cond_summary)
    figure_s5_swot(swot_summary, bundle_full_summary)
    figure_s6_emilia_wells(all_meta, trusted)
    figure_s7_selected_wells_overview(trusted=trusted, all_meta=all_meta, station_series_dir=ROOT / "outputs_well_validation" / "station_series")

    captions = make_tables_markdown(
        regional_summary,
        tiled_summary,
        synth_summary,
        well_overview,
        by_depth,
        by_gwb,
        trusted,
        trusted_gwb,
        cond_summary,
        swot_summary,
        bundle_full_summary,
    )
    (OUTDIR / "FIGURE_TABLE_CAPTIONS.md").write_text(captions)

    alias_map = {
        "figure_1_study_area_dtm_wells.png": "figure_1.png",
        "figure_2_workflow_schematic.png": "figure_2.png",
        "figure_3_synthetic_validation.png": "figure_3.png",
        "figure_4_grouped_stage1_results.png": "figure_4.png",
        "figure_5_well_validation_map.png": "figure_5.png",
        "figure_6_best_well_timeseries.png": "figure_6.png",
        "figure_s1_trusted_aquifer_groups.png": "figure_s1.png",
        "figure_s2_lag_histogram.png": "figure_s2.png",
        "figure_s3_depth_class_summary.png": "figure_s3.png",
        "figure_s4_conditioning_comparison.png": "figure_s4.png",
        "figure_s5_swot_overlap_summary.png": "figure_s5.png",
        "figure_s6_emilia_romagna_wells_overview.png": "figure_s6.png",
        "figure_s7_selected_wells_overview.png": "figure_s7.png",
    }
    for src_name, dst_name in alias_map.items():
        shutil.copyfile(OUTDIR / src_name, OUTDIR / dst_name)

    make_notebook()

    print("Saved paper figures to", OUTDIR)


if __name__ == "__main__":
    main()
