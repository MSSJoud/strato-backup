#!/usr/bin/env python3
"""Extract Bologna-overlap SWOT products from the Emilia-Romagna archive.

This keeps the SWOT side consistent with the corrected MintPy 2025 overlap
domain by:
- reading the overlap bbox/time span from the overlap summary JSON
- filtering the already-downloaded Emilia-Romagna SWOT feature tables
- writing Bologna-overlap feature tables and daily summaries
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd


DEFAULT_OVERLAP_SUMMARY = "/home/ubuntu/work/insar_mcmc/outputs_bologna_2025_overlap/bologna_mintpy2025_w3ra_overlap_summary.json"
DEFAULT_SWOT_PROC = "/home/ubuntu/work/insar_mcmc/outputs_external_constraints/swot_emilia_romagna_processed"
DEFAULT_OUT = "/home/ubuntu/work/insar_mcmc/outputs_external_constraints/swot_bologna_overlap2025"


def load_overlap(overlap_summary: str) -> tuple[dict, pd.Timestamp, pd.Timestamp]:
    obj = json.loads(Path(overlap_summary).read_text())
    bbox = obj["bbox"]
    t0 = pd.Timestamp(obj["time_start"]).normalize()
    t1 = pd.Timestamp(obj["time_end"]).normalize()
    return bbox, t0, t1


def filter_time(df: pd.DataFrame, t0: pd.Timestamp, t1: pd.Timestamp) -> pd.DataFrame:
    out = df.copy()
    out["time"] = pd.to_datetime(out["time"], utc=True, errors="coerce")
    out["date"] = out["time"].dt.tz_convert(None).dt.normalize()
    return out.loc[(out["date"] >= t0) & (out["date"] <= t1)].copy()


def filter_river_bbox(df: pd.DataFrame, bbox: dict) -> pd.DataFrame:
    return df.loc[
        df["p_lon"].between(bbox["lon_min"], bbox["lon_max"], inclusive="both")
        & df["p_lat"].between(bbox["lat_min"], bbox["lat_max"], inclusive="both")
    ].copy()


def filter_lake_bbox(df: pd.DataFrame, bbox: dict) -> pd.DataFrame:
    return df.loc[
        df["lon"].between(bbox["lon_min"], bbox["lon_max"], inclusive="both")
        & df["lat"].between(bbox["lat_min"], bbox["lat_max"], inclusive="both")
    ].copy()


def summarize_river(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame(columns=["time", "n_obs", "n_reaches", "wse_mean", "width_mean", "slope2_mean", "d_x_area_mean", "dschg_c_mean"])
    return (
        df.groupby("date", dropna=True)
        .agg(
            n_obs=("reach_id", "size"),
            n_reaches=("reach_id", pd.Series.nunique),
            wse_mean=("wse", "mean"),
            width_mean=("width", "mean"),
            slope2_mean=("slope2", "mean"),
            d_x_area_mean=("d_x_area", "mean"),
            dschg_c_mean=("dschg_c", "mean"),
        )
        .reset_index()
        .rename(columns={"date": "time"})
        .sort_values("time")
    )


def summarize_lake(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame(columns=["time", "n_obs", "n_lakes", "wse_mean", "area_total_mean"])
    return (
        df.groupby("date", dropna=True)
        .agg(
            n_obs=("lake_id", "size"),
            n_lakes=("lake_id", pd.Series.nunique),
            wse_mean=("wse", "mean"),
            area_total_mean=("area_total", "mean"),
        )
        .reset_index()
        .rename(columns={"date": "time"})
        .sort_values("time")
    )


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--overlap-summary", default=DEFAULT_OVERLAP_SUMMARY)
    p.add_argument("--swot-proc-dir", default=DEFAULT_SWOT_PROC)
    p.add_argument("--output-dir", default=DEFAULT_OUT)
    return p


def main() -> None:
    args = build_parser().parse_args()
    bbox, t0, t1 = load_overlap(args.overlap_summary)
    proc = Path(args.swot_proc_dir)
    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    river = pd.read_csv(proc / "swot_emilia_romagna_river_features.csv")
    lake = pd.read_csv(proc / "swot_emilia_romagna_lake_features.csv")

    river = filter_time(filter_river_bbox(river, bbox), t0, t1)
    lake = filter_time(filter_lake_bbox(lake, bbox), t0, t1)

    river_summary = summarize_river(river)
    lake_summary = summarize_lake(lake)

    river.to_csv(out_dir / "swot_bologna_overlap_river_features.csv", index=False)
    lake.to_csv(out_dir / "swot_bologna_overlap_lake_features.csv", index=False)
    river_summary.to_csv(out_dir / "swot_bologna_overlap_river_summary.csv", index=False)
    lake_summary.to_csv(out_dir / "swot_bologna_overlap_lake_summary.csv", index=False)

    summary = {
        "bbox": bbox,
        "time_start": str(t0.date()),
        "time_end": str(t1.date()),
        "river_rows": int(len(river)),
        "lake_rows": int(len(lake)),
        "river_times": int(river_summary["time"].nunique()) if not river_summary.empty else 0,
        "lake_times": int(lake_summary["time"].nunique()) if not lake_summary.empty else 0,
        "outputs": {
            "river_features_csv": str(out_dir / "swot_bologna_overlap_river_features.csv"),
            "lake_features_csv": str(out_dir / "swot_bologna_overlap_lake_features.csv"),
            "river_summary_csv": str(out_dir / "swot_bologna_overlap_river_summary.csv"),
            "lake_summary_csv": str(out_dir / "swot_bologna_overlap_lake_summary.csv"),
        },
    }
    (out_dir / "swot_bologna_overlap_summary.json").write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
