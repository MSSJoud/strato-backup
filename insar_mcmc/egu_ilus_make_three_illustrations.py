from __future__ import annotations

import os
from pathlib import Path

import h5py
import numpy as np
import pandas as pd
import xarray as xr
from matplotlib.colors import TwoSlopeNorm
from pyproj import Transformer


ROOT = Path("/home/ubuntu/work/insar_mcmc")
OUTDIR = ROOT / "egu_ilus_outputs"
OUTDIR.mkdir(parents=True, exist_ok=True)

os.environ.setdefault("XDG_CACHE_HOME", "/mnt/data/tmp")
os.environ.setdefault("MPLCONFIGDIR", "/mnt/data/tmp/mpl_egu")
Path(os.environ["XDG_CACHE_HOME"]).mkdir(parents=True, exist_ok=True)
Path(os.environ["MPLCONFIGDIR"]).mkdir(parents=True, exist_ok=True)

import matplotlib.pyplot as plt

TRUSTED_WELLS_CSV = ROOT / "outputs_well_validation" / "well_groundwater_validation_trusted_stations.csv"
BOLOGNA_WELLS_META_CSV = ROOT / "outputs_external_bologna_wells" / "processed" / "station_metadata_combined.csv"
STATION_SERIES_DIR = ROOT / "outputs_well_validation" / "station_series"

VEL_H5 = Path("/mnt/data/aoi_3_bologna/mintpy_filtered/velocity.h5")
TS_H5 = Path("/mnt/data/aoi_3_bologna/mintpy_filtered/timeseries_SET_ERA5_ramp_demErr.h5")
GROUPED_TILED_NPZ = ROOT / "outputs_stage1_bologna_multisensor_kalman_tiled_overlap2025_smaprefresh" / "stage1_bologna_multisensor_kalman_tiled_results.npz"
W3RA_OVERLAP_ANOM = ROOT / "outputs_bologna_2025_overlap" / "w3ra_on_mintpy2025_overlap_anom.nc"


def save(fig: plt.Figure, name: str) -> Path:
    path = OUTDIR / name
    fig.savefig(path, bbox_inches="tight", dpi=220)
    plt.close(fig)
    return path


def top9_trusted_wells() -> pd.DataFrame:
    trusted = pd.read_csv(TRUSTED_WELLS_CSV)
    top9 = trusted.sort_values(["corr_anom", "n_matches"], ascending=[False, False]).head(9).copy()
    top9["panel_id"] = np.arange(1, len(top9) + 1)
    return top9


def bologna_well_metadata() -> pd.DataFrame:
    all_meta = pd.read_csv(BOLOGNA_WELLS_META_CSV).drop_duplicates("station_code")
    return all_meta.loc[all_meta["province"] == "BO"].copy()


def mintpy_grid_info(path: Path) -> dict:
    with h5py.File(path, "r") as f:
        attrs = f.attrs
        epsg_raw = attrs.get("EPSG", 32632)
        try:
            epsg = int(epsg_raw)
        except Exception:
            epsg = 32632
        # Some MintPy products carry non-CRS EPSG-like codes in this field.
        if epsg < 10000:
            epsg = 32632
        x_first = float(attrs["X_FIRST"])
        y_first = float(attrs["Y_FIRST"])
        x_step = float(attrs["X_STEP"])
        y_step = float(attrs["Y_STEP"])
        width = int(attrs["WIDTH"])
        length = int(attrs["LENGTH"])
    return {
        "epsg": epsg,
        "x_first": x_first,
        "y_first": y_first,
        "x_step": x_step,
        "y_step": y_step,
        "width": width,
        "length": length,
    }


def lonlat_to_grid_xy(df: pd.DataFrame, grid: dict) -> pd.DataFrame:
    transformer = Transformer.from_crs(4326, grid["epsg"], always_xy=True)
    x, y = transformer.transform(df["lon"].to_numpy(), df["lat"].to_numpy())
    out = df.copy()
    out["utm_x"] = x
    out["utm_y"] = y
    out["col"] = np.rint((out["utm_x"] - grid["x_first"]) / grid["x_step"]).astype(int)
    out["row"] = np.rint((out["utm_y"] - grid["y_first"]) / grid["y_step"]).astype(int)
    return out


def crop_bounds_for_wells(wells_xy: pd.DataFrame, grid: dict, margin_m: float = 18000.0) -> tuple[int, int, int, int]:
    x_min = wells_xy["utm_x"].min() - margin_m
    x_max = wells_xy["utm_x"].max() + margin_m
    y_min = wells_xy["utm_y"].min() - margin_m
    y_max = wells_xy["utm_y"].max() + margin_m

    col0 = max(0, int(np.floor((x_min - grid["x_first"]) / grid["x_step"])))
    col1 = min(grid["width"] - 1, int(np.ceil((x_max - grid["x_first"]) / grid["x_step"])))

    row_a = int(np.floor((y_max - grid["y_first"]) / grid["y_step"]))
    row_b = int(np.ceil((y_min - grid["y_first"]) / grid["y_step"]))
    row0 = max(0, min(row_a, row_b))
    row1 = min(grid["length"] - 1, max(row_a, row_b))
    return row0, row1, col0, col1


def nearest_valid_insar_pixels(wells_xy: pd.DataFrame, grid: dict) -> pd.DataFrame:
    with h5py.File(VEL_H5, "r") as f:
        vel = f["velocity"][:]
    mask = np.isfinite(vel) & (vel != 0)
    rows, cols = np.where(mask)
    if len(rows) == 0:
        raise RuntimeError("No valid non-zero InSAR velocity pixels found.")

    out = wells_xy.copy()
    sample_rows = []
    sample_cols = []
    sample_x = []
    sample_y = []
    sample_lon = []
    sample_lat = []
    sample_dist_px = []
    sample_vel_mm_yr = []
    tr_back = Transformer.from_crs(grid["epsg"], 4326, always_xy=True)

    for _, row in wells_xy.iterrows():
        d2 = (rows - int(row["row"])) ** 2 + (cols - int(row["col"])) ** 2
        idx = int(np.argmin(d2))
        rr = int(rows[idx])
        cc = int(cols[idx])
        x = grid["x_first"] + cc * grid["x_step"]
        y = grid["y_first"] + rr * grid["y_step"]
        lon, lat = tr_back.transform(x, y)
        sample_rows.append(rr)
        sample_cols.append(cc)
        sample_x.append(x)
        sample_y.append(y)
        sample_lon.append(lon)
        sample_lat.append(lat)
        sample_dist_px.append(float(np.sqrt(d2[idx])))
        sample_vel_mm_yr.append(float(vel[rr, cc] * 1000.0))

    out["sample_row"] = sample_rows
    out["sample_col"] = sample_cols
    out["sample_x"] = sample_x
    out["sample_y"] = sample_y
    out["sample_lon"] = sample_lon
    out["sample_lat"] = sample_lat
    out["sample_pixel_dist"] = sample_dist_px
    out["sample_velocity_mm_yr"] = sample_vel_mm_yr
    return out


def load_velocity_crop(grid: dict, row0: int, row1: int, col0: int, col1: int) -> tuple[np.ndarray, np.ndarray]:
    with h5py.File(VEL_H5, "r") as f:
        vel = f["velocity"][row0 : row1 + 1, col0 : col1 + 1].astype(np.float32) * 1000.0

    x = grid["x_first"] + np.arange(col0, col1 + 1) * grid["x_step"]
    y = grid["y_first"] + np.arange(row0, row1 + 1) * grid["y_step"]
    return vel, np.asarray([x[0], x[-1], y[-1], y[0]], dtype=float)


def sample_insar_timeseries_at_wells(wells_xy: pd.DataFrame) -> tuple[pd.DatetimeIndex, dict[str, np.ndarray]]:
    out_ts: dict[str, np.ndarray] = {}
    with h5py.File(TS_H5, "r") as f_ts, h5py.File(VEL_H5, "r") as f_vel:
        raw_dates = f_ts["date"][:]
        dates = pd.to_datetime([d.decode() if isinstance(d, bytes) else str(d) for d in raw_dates], format="%Y%m%d")
        ts_ds = f_ts["timeseries"]
        for _, row in wells_xy.iterrows():
            series_mm = ts_ds[:, int(row["sample_row"]), int(row["sample_col"])].astype(np.float64) * 1000.0
            series_mm = series_mm - series_mm[0]
            out_ts[row["station_code"]] = series_mm
    return dates, out_ts


def tile_positions(length: int, tile_size: int, stride: int) -> list[int]:
    pos = list(range(0, max(length - tile_size + 1, 1), stride))
    last = max(length - tile_size, 0)
    if not pos or pos[-1] != last:
        pos.append(last)
    return pos


def reconstruct_grouped_state_fields(npz_path: Path, w3ra_path: Path) -> tuple[list[str], np.ndarray, np.ndarray, pd.DatetimeIndex, np.ndarray]:
    tiled_npz = np.load(npz_path)
    state_names = [str(s) for s in tiled_npz["state_names"].tolist()]
    theta_tiles = tiled_npz["theta_tiles"].astype(np.float64)

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

    n_time, _, h, w = z_state.shape
    ny, nx = tiled_npz["lat_tiles"].shape
    y_pos = tile_positions(h, 8, 8)
    x_pos = tile_positions(w, 8, 8)

    full_recon = np.zeros((n_time, len(state_names), h, w), dtype=np.float64)
    full_count = np.zeros((n_time, len(state_names), h, w), dtype=np.float64)

    for t_idx in range(n_time):
        for iy, y0 in enumerate(y_pos[:ny]):
            for ix, x0 in enumerate(x_pos[:nx]):
                y1 = min(y0 + 8, h)
                x1 = min(x0 + 8, w)
                theta_tile = theta_tiles[t_idx, :, iy, ix]
                full_recon[t_idx, :, y0:y1, x0:x1] += theta_tile[:, None, None] * z_state[t_idx, :, y0:y1, x0:x1]
                full_count[t_idx, :, y0:y1, x0:x1] += 1.0

    with np.errstate(invalid="ignore", divide="ignore"):
        full_recon = np.divide(full_recon, np.where(full_count == 0, np.nan, full_count))

    ts = pd.to_datetime(tiled_npz["time"])
    return state_names, lat, lon, ts, full_recon


def grouped_station_timeseries(top9: pd.DataFrame) -> tuple[pd.DatetimeIndex, dict[str, np.ndarray], list[str]]:
    state_names, lat, lon, time, full_recon = reconstruct_grouped_state_fields(GROUPED_TILED_NPZ, W3RA_OVERLAP_ANOM)
    series = {}
    for _, row in top9.iterrows():
        d2 = (lat - float(row["lat"])) ** 2 + (lon - float(row["lon"])) ** 2
        iy, ix = np.unravel_index(int(np.argmin(d2)), d2.shape)
        series[row["station_code"]] = full_recon[:, :, iy, ix]
    return time, series, state_names


def validation_station_series(top9: pd.DataFrame) -> dict[str, pd.DataFrame]:
    out = {}
    for _, row in top9.iterrows():
        path = STATION_SERIES_DIR / f"{row['station_code']}_{row['measurement_type']}.csv"
        df = pd.read_csv(path, parse_dates=["date"])
        out[row["station_code"]] = df
    return out


def add_station_labels(ax: plt.Axes, wells_df: pd.DataFrame, dx: float, dy: float, color: str = "darkred") -> None:
    for _, row in wells_df.iterrows():
        ax.text(
            row["utm_x"] + dx,
            row["utm_y"] + dy,
            str(int(row["panel_id"])),
            fontsize=9,
            fontweight="bold",
            color=color,
            ha="left",
            va="bottom",
            zorder=7,
        )


def make_figure_1_maps(top9_xy: pd.DataFrame, bologna_xy: pd.DataFrame) -> Path:
    grid = mintpy_grid_info(VEL_H5)
    row0, row1, col0, col1 = crop_bounds_for_wells(top9_xy, grid, margin_m=18000.0)
    vel_mm_yr, extent = load_velocity_crop(grid, row0, row1, col0, col1)

    valid = vel_mm_yr[np.isfinite(vel_mm_yr)]
    vlim = np.nanpercentile(np.abs(valid), 98) if valid.size else 5.0
    vlim = max(float(vlim), 1.0)
    norm = TwoSlopeNorm(vmin=-vlim, vcenter=0.0, vmax=vlim)

    fig = plt.figure(figsize=(16, 7.5), constrained_layout=True)
    gs = fig.add_gridspec(1, 2, width_ratios=[1.0, 1.25])
    ax_wells = fig.add_subplot(gs[0, 0])
    ax_insar = fig.add_subplot(gs[0, 1])

    ax_wells.scatter(bologna_xy["lon"], bologna_xy["lat"], s=12, c="#c4c4c4", alpha=0.55, linewidths=0, label="Bologna wells")
    ax_wells.scatter(top9_xy["lon"], top9_xy["lat"], s=180, marker="*", c="#d62728", edgecolors="white", linewidths=0.9, zorder=6, label="Selected wells")
    for _, row in top9_xy.iterrows():
        ax_wells.text(row["lon"] + 0.014, row["lat"] + 0.008, str(int(row["panel_id"])), fontsize=9, fontweight="bold", color="darkred")
    ax_wells.set_title("Selected wells within the Bologna monitoring network")
    ax_wells.set_xlabel("Longitude")
    ax_wells.set_ylabel("Latitude")
    ax_wells.legend(loc="lower left", frameon=True)

    im = ax_insar.imshow(vel_mm_yr, extent=extent, origin="upper", cmap="RdBu_r", norm=norm)
    ax_insar.scatter(top9_xy["utm_x"], top9_xy["utm_y"], s=185, marker="*", c="#d62728", edgecolors="white", linewidths=0.9, zorder=7, label="Well location")
    ax_insar.scatter(top9_xy["sample_x"], top9_xy["sample_y"], s=42, marker="o", facecolors="none", edgecolors="black", linewidths=1.0, zorder=8, label="Nearest valid InSAR pixel")
    for _, row in top9_xy.iterrows():
        ax_insar.plot([row["utm_x"], row["sample_x"]], [row["utm_y"], row["sample_y"]], color="#444444", lw=0.7, alpha=0.7)
    add_station_labels(ax_insar, top9_xy, dx=220.0, dy=220.0)
    cbar = fig.colorbar(im, ax=ax_insar, shrink=0.82, pad=0.02)
    cbar.set_label("LOS velocity (mm/yr)")
    ax_insar.set_title("InSAR LOS velocity in the valid subarea around the selected wells")
    ax_insar.set_xlabel("UTM32N Easting (m)")
    ax_insar.set_ylabel("UTM32N Northing (m)")
    ax_insar.legend(loc="lower left", frameon=True)

    fig.suptitle("Illustration 1: Wells map and cleaned InSAR velocity subarea", fontsize=15)
    return save(fig, "egu_ilus_1_wells_and_insar_maps.png")


def make_figure_2_insar_timeseries(top9_xy: pd.DataFrame) -> Path:
    dates, ts_by_station = sample_insar_timeseries_at_wells(top9_xy)
    fig, axes = plt.subplots(3, 3, figsize=(15, 10), constrained_layout=True)
    axes = axes.ravel()
    for ax, (_, row) in zip(axes, top9_xy.iterrows()):
        station = row["station_code"]
        ax.plot(dates, ts_by_station[station], color="#1f77b4", lw=1.7)
        ax.axhline(0.0, color="#666666", lw=0.8, ls="--")
        dist_km = row["sample_pixel_dist"] * 80.0 / 1000.0
        ax.set_title(
            f"{int(row['panel_id'])}. {station} | v={row['sample_velocity_mm_yr']:.1f} mm/yr | {dist_km:.1f} km",
            fontsize=10,
        )
        ax.tick_params(axis="x", rotation=30)
        ax.set_ylabel("LOS disp. (mm)")
    fig.suptitle("Illustration 2: InSAR time series from the nearest valid pixels to the selected wells", fontsize=15)
    return save(fig, "egu_ilus_2_insar_timeseries_panels.png")


def make_figure_3_grouped_solution(top9_xy: pd.DataFrame) -> Path:
    time, grouped_by_station, state_names = grouped_station_timeseries(top9_xy)
    fig, axes = plt.subplots(3, 3, figsize=(15, 10), constrained_layout=True)
    axes = axes.ravel()
    colors = {"ShallowLoad": "#ff7f0e", "DeepLoad": "#1f77b4", "Groundwater": "#2ca02c"}
    for ax, (_, row) in zip(axes, top9_xy.iterrows()):
        station = row["station_code"]
        arr = grouped_by_station[station]
        for j, state_name in enumerate(state_names):
            ax.plot(time, arr[:, j], lw=1.6, label=state_name, color=colors.get(state_name, None))
        ax.axhline(0.0, color="#666666", lw=0.8, ls="--")
        ax.set_title(f"{int(row['panel_id'])}. {station}", fontsize=10)
        ax.tick_params(axis="x", rotation=30)
        ax.set_ylabel("State (mm)")
    axes[0].legend(loc="best", fontsize=8)
    fig.suptitle("Illustration 3: Final grouped solution time series at the selected wells", fontsize=15)
    return save(fig, "egu_ilus_3_grouped_solution_panels.png")


def make_figure_4_groundwater_validation(top9_xy: pd.DataFrame) -> Path:
    station_frames = validation_station_series(top9_xy)
    fig, axes = plt.subplots(3, 3, figsize=(15, 10), constrained_layout=True)
    axes = axes.ravel()
    for ax, (_, row) in zip(axes, top9_xy.iterrows()):
        station = row["station_code"]
        df = station_frames[station]
        ax.plot(df["date"], df["model_anom_z"], color="#1f77b4", lw=1.7, label="Model Sg anomaly")
        ax.plot(df["date"], df["obs_anom_z"], color="#ff7f0e", lw=1.7, label="Well anomaly")
        ax.axhline(0.0, color="#666666", lw=0.8, ls="--")
        ax.set_title(
            f"{int(row['panel_id'])}. {station} | corr={row['corr_anom']:.3f} | lag={int(row['best_lag_days'])}d",
            fontsize=10,
        )
        ax.tick_params(axis="x", rotation=30)
        ax.set_ylabel("z-anomaly")
    axes[0].legend(loc="best", fontsize=8)
    fig.suptitle("Illustration 4: Groundwater (Sg) validation against wells", fontsize=15)
    return save(fig, "egu_ilus_4_groundwater_validation_panels.png")


def make_all() -> dict[str, Path]:
    plt.rcParams.update(
        {
            "figure.dpi": 150,
            "savefig.dpi": 220,
            "font.size": 10,
            "axes.titlesize": 12,
            "axes.labelsize": 10,
            "legend.fontsize": 9,
            "xtick.labelsize": 9,
            "ytick.labelsize": 9,
        }
    )
    top9 = top9_trusted_wells()
    bologna_meta = bologna_well_metadata()
    grid = mintpy_grid_info(VEL_H5)
    top9_xy = lonlat_to_grid_xy(top9, grid)
    bologna_xy = lonlat_to_grid_xy(bologna_meta, grid)
    top9_xy = nearest_valid_insar_pixels(top9_xy, grid)

    outputs = {
        "maps": make_figure_1_maps(top9_xy, bologna_xy),
        "insar_ts": make_figure_2_insar_timeseries(top9_xy),
        "grouped": make_figure_3_grouped_solution(top9_xy),
        "validation": make_figure_4_groundwater_validation(top9_xy),
    }
    return outputs


if __name__ == "__main__":
    paths = make_all()
    for key, value in paths.items():
        print(f"{key}: {value}")
