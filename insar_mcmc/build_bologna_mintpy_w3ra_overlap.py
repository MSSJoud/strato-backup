#!/usr/bin/env python3
"""Build corrected Bologna overlap products from the 2025 MintPy scene and W3RA grid.

This script:
- reads the newer MintPy HDF5 scene through 2025-06-27
- intersects it with the available W3RA regional grid/time support
- aggregates the MintPy deformation onto the native W3RA lat/lon grid
- exports compact overlap products suitable for grouped Stage 1 reruns

The output grid is the W3RA grid, not the native MintPy pixel grid.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from pathlib import Path

import h5py
import numpy as np
import pandas as pd
import xarray as xr
from pyproj import CRS, Transformer


W3RA_VARS = ("S0", "Ss", "Sd", "Sg", "Sr")


@dataclass
class BolognaMintPyW3RAOverlapConfig:
    mintpy_path: str = "/mnt/data/aoi_3_bologna/mintpy_filtered/timeseries_SET_ERA5_ramp_demErr.h5"
    w3ra_source_path: str = "/mnt/data/data_bologna_swin_test/w3ra/W3RA_2010_2024_.nc"
    output_dir: str = "/home/ubuntu/work/insar_mcmc/outputs_bologna_2025_overlap"
    end_date_limit: str = "2024-08-01"
    valid_fill_values: tuple[float, ...] = (-9999.0,)


def parse_args() -> BolognaMintPyW3RAOverlapConfig:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--mintpy-path", default=BolognaMintPyW3RAOverlapConfig.mintpy_path)
    p.add_argument("--w3ra-source-path", default=BolognaMintPyW3RAOverlapConfig.w3ra_source_path)
    p.add_argument("--output-dir", default=BolognaMintPyW3RAOverlapConfig.output_dir)
    p.add_argument("--end-date-limit", default=BolognaMintPyW3RAOverlapConfig.end_date_limit)
    ns = p.parse_args()
    return BolognaMintPyW3RAOverlapConfig(
        mintpy_path=ns.mintpy_path,
        w3ra_source_path=ns.w3ra_source_path,
        output_dir=ns.output_dir,
        end_date_limit=ns.end_date_limit,
    )


def load_w3ra_daily(source_path: str, start: pd.Timestamp, end: pd.Timestamp) -> xr.Dataset:
    ds = xr.open_dataset(source_path)
    try:
        lat = ds["lat"].values.astype(np.float32)
        lon = ds["lon"].values.astype(np.float32)
        pieces: list[xr.Dataset] = []
        for year in range(start.year, end.year + 1):
            time_name = f"time_{year}"
            if time_name not in ds.coords:
                continue
            times = pd.DatetimeIndex(pd.to_datetime(ds[time_name].values))
            keep = (times >= start) & (times <= end)
            if not keep.any():
                continue
            data_vars = {}
            for var in W3RA_VARS:
                name = f"{var}_EU_{year}"
                if name not in ds.data_vars:
                    raise KeyError(f"Missing {name} in {source_path}")
                data_vars[var] = (("time", "lat", "lon"), ds[name].values[keep].astype(np.float32))
            piece = xr.Dataset(
                data_vars=data_vars,
                coords={
                    "time": times[keep].values,
                    "lat": lat,
                    "lon": lon,
                },
            )
            pieces.append(piece)
        if not pieces:
            raise ValueError("No W3RA time slices overlap requested range.")
        out = xr.concat(pieces, dim="time").sortby("time")
        return out
    finally:
        ds.close()


def mintpy_overlap_indices(attrs: dict, lat_min: float, lat_max: float, lon_min: float, lon_max: float) -> tuple[slice, slice, np.ndarray, np.ndarray]:
    x0 = float(attrs["X_FIRST"])
    y0 = float(attrs["Y_FIRST"])
    dx = float(attrs["X_STEP"])
    dy = float(attrs["Y_STEP"])
    width = int(attrs["WIDTH"])
    height = int(attrs["LENGTH"])
    utm_zone = attrs["UTM_ZONE"]
    if isinstance(utm_zone, bytes):
        utm_zone = utm_zone.decode()

    zone_num = int(str(utm_zone)[:-1])
    hemi = str(utm_zone)[-1].upper()
    epsg = 32600 + zone_num if hemi == "N" else 32700 + zone_num
    to_utm = Transformer.from_crs(CRS.from_epsg(4326), CRS.from_epsg(epsg), always_xy=True)
    x_corners, y_corners = to_utm.transform(
        [lon_min, lon_max, lon_min, lon_max],
        [lat_min, lat_min, lat_max, lat_max],
    )
    xmin, xmax = min(x_corners), max(x_corners)
    ymin, ymax = min(y_corners), max(y_corners)

    xs = x0 + np.arange(width) * dx
    ys = y0 + np.arange(height) * dy
    xmask = (xs >= xmin) & (xs <= xmax) if dx > 0 else (xs <= xmax) & (xs >= xmin)
    ymask = (ys >= ymin) & (ys <= ymax) if dy > 0 else (ys <= ymax) & (ys >= ymin)
    xidx = np.where(xmask)[0]
    yidx = np.where(ymask)[0]
    if xidx.size == 0 or yidx.size == 0:
        raise ValueError("No MintPy pixels overlap the W3RA bbox.")
    return (
        slice(int(yidx.min()), int(yidx.max()) + 1),
        slice(int(xidx.min()), int(xidx.max()) + 1),
        xs[xidx.min() : xidx.max() + 1],
        ys[yidx.min() : yidx.max() + 1],
    )


def build_subset_lonlat(xs: np.ndarray, ys: np.ndarray, utm_zone: str) -> tuple[np.ndarray, np.ndarray]:
    zone_num = int(str(utm_zone)[:-1])
    hemi = str(utm_zone)[-1].upper()
    epsg = 32600 + zone_num if hemi == "N" else 32700 + zone_num
    to_geo = Transformer.from_crs(CRS.from_epsg(epsg), CRS.from_epsg(4326), always_xy=True)
    xx, yy = np.meshgrid(xs, ys)
    lon2d, lat2d = to_geo.transform(xx, yy)
    return lat2d.astype(np.float32), lon2d.astype(np.float32)


def compute_w3ra_cell_edges(vals: np.ndarray) -> np.ndarray:
    vals = np.asarray(vals, dtype=np.float64)
    mids = 0.5 * (vals[:-1] + vals[1:])
    edges = np.empty(vals.size + 1, dtype=np.float64)
    edges[1:-1] = mids
    edges[0] = vals[0] - (mids[0] - vals[0])
    edges[-1] = vals[-1] + (vals[-1] - mids[-1])
    return edges


def assign_w3ra_bins(lat2d: np.ndarray, lon2d: np.ndarray, lat_vals: np.ndarray, lon_vals: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    descending_lat = lat_vals[0] > lat_vals[-1]
    lat_asc = lat_vals[::-1] if descending_lat else lat_vals
    lat_edges = compute_w3ra_cell_edges(lat_asc)
    lon_edges = compute_w3ra_cell_edges(lon_vals)

    lat_flat = lat2d.ravel()
    lon_flat = lon2d.ravel()

    if descending_lat:
        lat_bin_asc = np.searchsorted(lat_edges, lat_flat, side="right") - 1
        lat_bin = (len(lat_vals) - 1) - lat_bin_asc
    else:
        lat_bin = np.searchsorted(lat_edges, lat_flat, side="right") - 1
    lon_bin = np.searchsorted(lon_edges, lon_flat, side="right") - 1

    valid = (
        (lat_bin >= 0)
        & (lat_bin < len(lat_vals))
        & (lon_bin >= 0)
        & (lon_bin < len(lon_vals))
    )
    cell_index = lat_bin * len(lon_vals) + lon_bin
    return valid, lat_bin, cell_index


def aggregate_mintpy_to_w3ra(
    mintpy_path: str,
    overlap_dates: pd.DatetimeIndex,
    lat_vals: np.ndarray,
    lon_vals: np.ndarray,
    valid_fill_values: tuple[float, ...],
) -> xr.Dataset:
    with h5py.File(mintpy_path, "r") as f:
        attrs = dict(f.attrs)
        all_dates = pd.DatetimeIndex(pd.to_datetime([d.decode() for d in f["date"][:]], format="%Y%m%d"))
        date_to_idx = {d: i for i, d in enumerate(all_dates)}
        available = [d for d in overlap_dates if d in date_to_idx]
        if not available:
            raise ValueError("No overlapping MintPy dates found in HDF5.")

        lat_min, lat_max = float(lat_vals.min()), float(lat_vals.max())
        lon_min, lon_max = float(lon_vals.min()), float(lon_vals.max())
        yslice, xslice, xs, ys = mintpy_overlap_indices(attrs, lat_min, lat_max, lon_min, lon_max)
        utm_zone = attrs["UTM_ZONE"]
        if isinstance(utm_zone, bytes):
            utm_zone = utm_zone.decode()
        lat2d, lon2d = build_subset_lonlat(xs, ys, utm_zone)
        valid_mask, _, cell_index = assign_w3ra_bins(lat2d, lon2d, lat_vals, lon_vals)
        n_cells = len(lat_vals) * len(lon_vals)

        out = np.full((len(available), len(lat_vals), len(lon_vals)), np.nan, dtype=np.float32)
        ts = f["timeseries"]
        for ti, date in enumerate(available):
            arr = ts[date_to_idx[date], yslice, xslice].astype(np.float32).ravel()
            finite = np.isfinite(arr)
            for fill in valid_fill_values:
                finite &= arr != fill
            use = valid_mask & finite
            if not np.any(use):
                continue
            sums = np.bincount(cell_index[use], weights=arr[use], minlength=n_cells).astype(np.float64)
            counts = np.bincount(cell_index[use], minlength=n_cells).astype(np.int64)
            means = np.divide(sums, counts, out=np.full(n_cells, np.nan), where=counts > 0)
            out[ti] = means.reshape(len(lat_vals), len(lon_vals)).astype(np.float32)

    lat2d_w3ra, lon2d_w3ra = np.meshgrid(lat_vals, lon_vals, indexing="ij")
    return xr.Dataset(
        data_vars={
            "insar_deformation": (("time", "y", "x"), out),
        },
        coords={
            "time": np.array(available, dtype="datetime64[ns]"),
            "y": np.arange(len(lat_vals)),
            "x": np.arange(len(lon_vals)),
            "lat": (("y", "x"), lat2d_w3ra.astype(np.float32)),
            "lon": (("y", "x"), lon2d_w3ra.astype(np.float32)),
        },
        attrs={
            "source": mintpy_path,
            "aggregation": "MintPy scene aggregated to native W3RA grid",
            "unit": "m",
        },
    )


def w3ra_to_target_grid(w3ra_ds: xr.Dataset) -> xr.Dataset:
    lat2d, lon2d = np.meshgrid(w3ra_ds["lat"].values.astype(np.float32), w3ra_ds["lon"].values.astype(np.float32), indexing="ij")
    return xr.Dataset(
        data_vars={
            var: (("time", "y", "x"), w3ra_ds[var].transpose("time", "lat", "lon").values.astype(np.float32))
            for var in W3RA_VARS
        },
        coords={
            "time": w3ra_ds["time"].values,
            "y": np.arange(w3ra_ds.sizes["lat"]),
            "x": np.arange(w3ra_ds.sizes["lon"]),
            "lat": (("y", "x"), lat2d),
            "lon": (("y", "x"), lon2d),
        },
    )


def main() -> None:
    cfg = parse_args()
    out_dir = Path(cfg.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    end_limit = pd.Timestamp(cfg.end_date_limit)
    # Build W3RA first so its support defines the overlap bbox and time.
    w3ra_daily = load_w3ra_daily(cfg.w3ra_source_path, start=pd.Timestamp("2017-01-01"), end=end_limit)
    overlap_dates = pd.DatetimeIndex(w3ra_daily.time.values)

    insar_ds = aggregate_mintpy_to_w3ra(
        mintpy_path=cfg.mintpy_path,
        overlap_dates=overlap_dates,
        lat_vals=w3ra_daily["lat"].values.astype(np.float32),
        lon_vals=w3ra_daily["lon"].values.astype(np.float32),
        valid_fill_values=cfg.valid_fill_values,
    )

    common_dates = pd.DatetimeIndex(sorted(set(pd.to_datetime(insar_ds.time.values)).intersection(set(overlap_dates))))
    insar_ds = insar_ds.sel(time=common_dates)
    w3ra_ds = w3ra_to_target_grid(w3ra_daily.sel(time=common_dates))
    w3ra_anom = xr.Dataset({var: w3ra_ds[var] - w3ra_ds[var].mean("time") for var in W3RA_VARS}, coords=w3ra_ds.coords)

    insar_path = out_dir / "insar_mintpy2025_on_w3ra_grid.nc"
    w3ra_path = out_dir / "w3ra_on_mintpy2025_overlap.nc"
    w3ra_anom_path = out_dir / "w3ra_on_mintpy2025_overlap_anom.nc"
    insar_ds.to_netcdf(insar_path)
    w3ra_ds.to_netcdf(w3ra_path)
    w3ra_anom.to_netcdf(w3ra_anom_path)

    summary = {
        "config": asdict(cfg),
        "n_times": int(len(common_dates)),
        "time_start": str(common_dates[0].date()) if len(common_dates) else None,
        "time_end": str(common_dates[-1].date()) if len(common_dates) else None,
        "grid_shape": {"y": int(insar_ds.sizes["y"]), "x": int(insar_ds.sizes["x"])},
        "bbox": {
            "lat_min": float(insar_ds["lat"].values.min()),
            "lat_max": float(insar_ds["lat"].values.max()),
            "lon_min": float(insar_ds["lon"].values.min()),
            "lon_max": float(insar_ds["lon"].values.max()),
        },
        "outputs": {
            "insar_path": str(insar_path),
            "w3ra_path": str(w3ra_path),
            "w3ra_anom_path": str(w3ra_anom_path),
        },
    }
    (out_dir / "bologna_mintpy2025_w3ra_overlap_summary.json").write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
