#!/usr/bin/env python3
"""Bundle Bologna grouped inversion inputs with external regional constraints."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from insar_mcmc.mintpy_h5_utils import load_insar_times


def align_scalar_series(
    target_dates: pd.DatetimeIndex,
    csv_path: str,
    value_column: str,
    time_column: str = "time",
    interpolate: bool = True,
) -> pd.DataFrame:
    df = pd.read_csv(csv_path)
    df[time_column] = pd.to_datetime(df[time_column]).dt.normalize()
    base = pd.DataFrame({"time": target_dates.normalize()})
    merged = base.merge(df[[time_column, value_column]], left_on="time", right_on=time_column, how="left").drop(columns=[time_column])
    if interpolate:
        merged[value_column] = merged[value_column].interpolate(limit_direction="both")
    return merged


def align_nearest_series(
    target_dates: pd.DatetimeIndex,
    csv_path: str,
    value_column: str,
    time_column: str = "time",
    max_gap_days: int = 7,
) -> pd.DataFrame:
    df = pd.read_csv(csv_path)
    df[time_column] = pd.to_datetime(df[time_column]).dt.normalize()
    df = df[[time_column, value_column]].dropna().sort_values(time_column)
    base = pd.DataFrame({"time": target_dates.normalize()}).sort_values("time")
    if df.empty:
        base[value_column] = np.nan
        return base
    merged = pd.merge_asof(
        base,
        df,
        left_on="time",
        right_on=time_column,
        direction="nearest",
        tolerance=pd.Timedelta(days=max_gap_days),
    ).drop(columns=[time_column])
    return merged


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--grace-csv",
        default="/home/ubuntu/work/insar_mcmc/outputs_external_constraints/bologna_grace_region_timeseries.csv",
    )
    p.add_argument(
        "--smap-csv",
        default="/home/ubuntu/work/insar_mcmc/outputs_external_constraints/smap_processed/bologna_smap_surface_soil_moisture_timeseries.csv",
    )
    p.add_argument(
        "--swot-river-csv",
        default="",
        help="Optional SWOT river summary CSV with columns time,wse_mean",
    )
    p.add_argument(
        "--swot-lake-csv",
        default="",
        help="Optional SWOT lake summary CSV with columns time,wse_mean",
    )
    p.add_argument("--swot-max-gap-days", type=int, default=14)
    p.add_argument(
        "--stage1-results",
        default="/home/ubuntu/work/insar_mcmc/outputs_stage1_bologna_real_full_grouped_quick/stage1_bologna_real_results.npz",
    )
    p.add_argument("--insar-path", default="/mnt/data/aoi_3_bologna/mintpy_filtered/timeseries_SET_ERA5_ramp_demErr.h5")
    p.add_argument(
        "--output-dir",
        default="/home/ubuntu/work/insar_mcmc/outputs_external_constraints/multisensor_bundle",
    )
    return p


def main() -> None:
    args = build_parser().parse_args()
    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    stage1 = np.load(args.stage1_results)
    times = load_insar_times(args.insar_path)

    grace = align_scalar_series(times, args.grace_csv, "lwe_thickness_mean_anom")
    bundle = pd.DataFrame({"time": times, "grace_tws_anom": grace["lwe_thickness_mean_anom"].to_numpy()})

    summary = {
        "n_times": int(len(times)),
        "time_start": str(times[0].date()),
        "time_end": str(times[-1].date()),
        "sources": {"grace_csv": args.grace_csv, "stage1_results": args.stage1_results},
    }

    if args.smap_csv:
        smap = align_scalar_series(times, args.smap_csv, "soil_moisture_mean")
        bundle["smap_surface_sm"] = smap["soil_moisture_mean"].to_numpy()
        summary["sources"]["smap_csv"] = args.smap_csv
        summary["smap_non_null"] = int(np.isfinite(bundle["smap_surface_sm"]).sum())

    if args.swot_river_csv:
        swot_river = align_nearest_series(
            times,
            args.swot_river_csv,
            "wse_mean",
            max_gap_days=args.swot_max_gap_days,
        )
        bundle["swot_river_wse_mean"] = swot_river["wse_mean"].to_numpy()
        summary["sources"]["swot_river_csv"] = args.swot_river_csv
        summary["swot_river_non_null"] = int(np.isfinite(bundle["swot_river_wse_mean"]).sum())
        summary["swot_max_gap_days"] = int(args.swot_max_gap_days)

    if args.swot_lake_csv:
        swot_lake = align_nearest_series(
            times,
            args.swot_lake_csv,
            "wse_mean",
            max_gap_days=args.swot_max_gap_days,
        )
        bundle["swot_lake_wse_mean"] = swot_lake["wse_mean"].to_numpy()
        summary["sources"]["swot_lake_csv"] = args.swot_lake_csv
        summary["swot_lake_non_null"] = int(np.isfinite(bundle["swot_lake_wse_mean"]).sum())

    bundle.to_csv(out_dir / "bologna_grouped_multisensor_bundle.csv", index=False)
    (out_dir / "bologna_grouped_multisensor_bundle_summary.json").write_text(json.dumps(summary, indent=2))
    print(bundle.head())
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
