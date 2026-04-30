#!/usr/bin/env python3
"""Helpers for reading MintPy timeseries HDF5 products."""

from __future__ import annotations

from pathlib import Path

import h5py
import pandas as pd
import xarray as xr


def _is_h5(path: str | Path) -> bool:
    return Path(path).suffix.lower() in {".h5", ".he5"}


def load_insar_times(path: str | Path) -> pd.DatetimeIndex:
    path = str(path)
    if _is_h5(path):
        with h5py.File(path, "r") as f:
            if "date" not in f:
                raise ValueError(f"MintPy file {path} has no 'date' dataset.")
            vals = [d.decode() if isinstance(d, bytes) else str(d) for d in f["date"][:]]
        return pd.DatetimeIndex(pd.to_datetime(vals, format="%Y%m%d"))

    ds = xr.open_dataset(path)
    try:
        return pd.DatetimeIndex(pd.to_datetime(ds.time.values))
    finally:
        ds.close()


def load_insar_domain(path: str | Path) -> dict:
    path = str(path)
    if not _is_h5(path):
        ds = xr.open_dataset(path)
        try:
            times = pd.DatetimeIndex(pd.to_datetime(ds.time.values))
            lat = ds["lat"].values
            lon = ds["lon"].values
            return {
                "times": times,
                "lat_min": float(lat.min()),
                "lat_max": float(lat.max()),
                "lon_min": float(lon.min()),
                "lon_max": float(lon.max()),
                "height": int(ds.sizes["y"]),
                "width": int(ds.sizes["x"]),
                "source_type": "netcdf",
            }
        finally:
            ds.close()

    with h5py.File(path, "r") as f:
        attrs = dict(f.attrs)
        times = load_insar_times(path)
        length = int(attrs["LENGTH"])
        width = int(attrs["WIDTH"])
        x_first = float(attrs["X_FIRST"])
        y_first = float(attrs["Y_FIRST"])
        x_step = float(attrs["X_STEP"])
        y_step = float(attrs["Y_STEP"])
        x_last = x_first + (width - 1) * x_step
        y_last = y_first + (length - 1) * y_step

        utm_zone = attrs.get("UTM_ZONE")
        if isinstance(utm_zone, bytes):
            utm_zone = utm_zone.decode()
        if not utm_zone:
            raise ValueError(f"MintPy file {path} has no UTM_ZONE attribute.")

    from pyproj import CRS, Transformer

    zone_num = int(str(utm_zone)[:-1])
    hemi = str(utm_zone)[-1].upper()
    epsg = 32600 + zone_num if hemi == "N" else 32700 + zone_num
    transformer = Transformer.from_crs(CRS.from_epsg(epsg), CRS.from_epsg(4326), always_xy=True)

    corners_x = [x_first, x_first, x_last, x_last]
    corners_y = [y_first, y_last, y_first, y_last]
    lons, lats = transformer.transform(corners_x, corners_y)

    return {
        "times": times,
        "lat_min": float(min(lats)),
        "lat_max": float(max(lats)),
        "lon_min": float(min(lons)),
        "lon_max": float(max(lons)),
        "height": int(length),
        "width": int(width),
        "source_type": "mintpy_h5",
        "utm_zone": str(utm_zone),
        "epsg_projected": int(epsg),
    }
