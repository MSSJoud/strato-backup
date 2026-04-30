#!/usr/bin/env python3
"""Prepare compact SWOT river/lake tables for Emilia-Romagna plotting."""

from __future__ import annotations

import json
import os
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd


RAW_DIR = Path("/home/ubuntu/work/insar_mcmc/outputs_external_constraints/swot_emilia_romagna_raw")
OUT_DIR = Path("/home/ubuntu/work/insar_mcmc/outputs_external_constraints/swot_emilia_romagna_processed")
BBOX = {"west": 9.15, "south": 43.70, "east": 12.85, "north": 45.15}
FILL_THRESHOLD = -1e11

RIVER_KEEP = [
    "reach_id",
    "time_str",
    "river_name",
    "p_lat",
    "p_lon",
    "wse",
    "width",
    "slope2",
    "d_x_area",
    "dschg_c",
]
LAKE_KEEP = [
    "obs_id",
    "lake_id",
    "time_str",
    "lake_name",
    "wse",
    "area_total",
    "quality_f",
]


def sanitize_numeric(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    for col in out.columns:
        if pd.api.types.is_numeric_dtype(out[col]):
            out.loc[out[col] <= FILL_THRESHOLD, col] = np.nan
    return out


def filter_river(path: Path) -> pd.DataFrame:
    gdf = gpd.read_file(f"zip://{path}")
    mask = (
        gdf["p_lon"].between(BBOX["west"], BBOX["east"], inclusive="both")
        & gdf["p_lat"].between(BBOX["south"], BBOX["north"], inclusive="both")
    )
    gdf = gdf.loc[mask, RIVER_KEEP].copy()
    if gdf.empty:
        return pd.DataFrame(columns=RIVER_KEEP + ["source_file", "product", "time"])
    gdf["source_file"] = path.name
    gdf["product"] = "river"
    gdf["time"] = pd.to_datetime(gdf["time_str"], format="%Y-%m-%dT%H:%M:%SZ", errors="coerce", utc=True)
    return sanitize_numeric(pd.DataFrame(gdf))


def filter_lake(path: Path) -> pd.DataFrame:
    gdf = gpd.read_file(f"zip://{path}")
    reps = gdf.geometry.representative_point()
    mask = (
        reps.x.astype(float).between(BBOX["west"], BBOX["east"], inclusive="both")
        & reps.y.astype(float).between(BBOX["south"], BBOX["north"], inclusive="both")
    )
    gdf = gdf.loc[mask, LAKE_KEEP].copy()
    if gdf.empty:
        return pd.DataFrame(columns=LAKE_KEEP + ["lon", "lat", "source_file", "product", "time"])
    reps = reps.loc[gdf.index]
    gdf["lon"] = reps.x.astype(float)
    gdf["lat"] = reps.y.astype(float)
    gdf["source_file"] = path.name
    gdf["product"] = "lake"
    gdf["time"] = pd.to_datetime(gdf["time_str"], format="%Y-%m-%dT%H:%M:%SZ", errors="coerce", utc=True)
    return sanitize_numeric(pd.DataFrame(gdf))


def summarize_river(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame(columns=["time", "n_obs", "n_reaches", "wse_mean", "width_mean", "slope2_mean", "d_x_area_mean", "dschg_c_mean"])
    grp = df.groupby("time", dropna=True)
    out = grp.agg(
        n_obs=("reach_id", "size"),
        n_reaches=("reach_id", pd.Series.nunique),
        wse_mean=("wse", "mean"),
        width_mean=("width", "mean"),
        slope2_mean=("slope2", "mean"),
        d_x_area_mean=("d_x_area", "mean"),
        dschg_c_mean=("dschg_c", "mean"),
    ).reset_index()
    return out.sort_values("time")


def summarize_lake(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame(columns=["time", "n_obs", "n_lakes", "wse_mean", "area_total_mean"])
    grp = df.groupby("time", dropna=True)
    out = grp.agg(
        n_obs=("lake_id", "size"),
        n_lakes=("lake_id", pd.Series.nunique),
        wse_mean=("wse", "mean"),
        area_total_mean=("area_total", "mean"),
    ).reset_index()
    return out.sort_values("time")


def top_features(df: pd.DataFrame, id_col: str, name_col: str, n: int = 15) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame(columns=[id_col, name_col, "n_obs"])
    counts = (
        df.groupby([id_col, name_col], dropna=False)
        .size()
        .reset_index(name="n_obs")
        .sort_values(["n_obs", id_col], ascending=[False, True])
        .head(n)
    )
    return counts


def main() -> None:
    os.environ.setdefault("PROJ_LIB", "/home/ubuntu/anaconda3/envs/insar/share/proj")
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    river_rows: list[pd.DataFrame] = []
    lake_rows: list[pd.DataFrame] = []
    raw_files = sorted(RAW_DIR.glob("*.zip"))
    for path in raw_files:
        if "RiverSP_Reach" in path.name:
            river_rows.append(filter_river(path))
        elif "LakeSP_Obs" in path.name:
            lake_rows.append(filter_lake(path))

    river_df = pd.concat(river_rows, ignore_index=True) if river_rows else pd.DataFrame()
    lake_df = pd.concat(lake_rows, ignore_index=True) if lake_rows else pd.DataFrame()

    river_summary = summarize_river(river_df)
    lake_summary = summarize_lake(lake_df)
    river_top = top_features(river_df, "reach_id", "river_name")
    lake_top = top_features(lake_df, "lake_id", "lake_name")

    river_df.to_csv(OUT_DIR / "swot_emilia_romagna_river_features.csv", index=False)
    lake_df.to_csv(OUT_DIR / "swot_emilia_romagna_lake_features.csv", index=False)
    river_summary.to_csv(OUT_DIR / "swot_emilia_romagna_river_summary.csv", index=False)
    lake_summary.to_csv(OUT_DIR / "swot_emilia_romagna_lake_summary.csv", index=False)
    river_top.to_csv(OUT_DIR / "swot_emilia_romagna_river_top_features.csv", index=False)
    lake_top.to_csv(OUT_DIR / "swot_emilia_romagna_lake_top_features.csv", index=False)

    latest_river = river_df.dropna(subset=["time"]).sort_values("time").groupby("reach_id", as_index=False).tail(1)
    latest_lake = lake_df.dropna(subset=["time"]).sort_values("time").groupby("lake_id", as_index=False).tail(1)
    latest_river.to_csv(OUT_DIR / "swot_emilia_romagna_river_latest.csv", index=False)
    latest_lake.to_csv(OUT_DIR / "swot_emilia_romagna_lake_latest.csv", index=False)

    summary = {
        "bbox": BBOX,
        "n_raw_zip_files": len(raw_files),
        "river_rows": int(len(river_df)),
        "lake_rows": int(len(lake_df)),
        "river_times": int(river_summary["time"].nunique()) if not river_summary.empty else 0,
        "lake_times": int(lake_summary["time"].nunique()) if not lake_summary.empty else 0,
        "time_start": str(min(
            [x for x in [
                river_summary["time"].min() if not river_summary.empty else None,
                lake_summary["time"].min() if not lake_summary.empty else None,
            ] if x is not None]
        ).date()) if (not river_summary.empty or not lake_summary.empty) else None,
        "time_end": str(max(
            [x for x in [
                river_summary["time"].max() if not river_summary.empty else None,
                lake_summary["time"].max() if not lake_summary.empty else None,
            ] if x is not None]
        ).date()) if (not river_summary.empty or not lake_summary.empty) else None,
        "outputs": {
            "river_features_csv": str(OUT_DIR / "swot_emilia_romagna_river_features.csv"),
            "lake_features_csv": str(OUT_DIR / "swot_emilia_romagna_lake_features.csv"),
            "river_summary_csv": str(OUT_DIR / "swot_emilia_romagna_river_summary.csv"),
            "lake_summary_csv": str(OUT_DIR / "swot_emilia_romagna_lake_summary.csv"),
        },
    }
    (OUT_DIR / "swot_emilia_romagna_summary.json").write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
