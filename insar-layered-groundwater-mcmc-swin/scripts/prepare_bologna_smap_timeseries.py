#!/usr/bin/env python3
"""Extract a Bologna-area SMAP surface-soil-moisture time series from downloaded HDF5 files."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

import h5py
import numpy as np
import pandas as pd


DATE_RE = re.compile(r"(\d{8})")


def parse_date_from_name(path: Path) -> pd.Timestamp:
    m = DATE_RE.search(path.name)
    if not m:
        raise ValueError(f"Could not parse date from {path.name}")
    return pd.to_datetime(m.group(1), format="%Y%m%d")


def extract_one(path: Path, bbox: dict, group: str = "Soil_Moisture_Retrieval_Data_AM") -> dict:
    with h5py.File(path, "r") as f:
        lat = f[f"{group}/latitude"][:]
        lon = f[f"{group}/longitude"][:]
        sm = f[f"{group}/soil_moisture"][:]
        qf = f[f"{group}/retrieval_qual_flag"][:]

    valid = (
        np.isfinite(lat)
        & np.isfinite(lon)
        & np.isfinite(sm)
        & (lat >= bbox["lat_min"])
        & (lat <= bbox["lat_max"])
        & (lon >= bbox["lon_min"])
        & (lon <= bbox["lon_max"])
        & (qf == 0)
    )
    if not np.any(valid):
        return {
            "time": parse_date_from_name(path),
            "n_pixels": 0,
            "soil_moisture_mean": np.nan,
            "soil_moisture_std": np.nan,
            "source_file": path.name,
        }

    vals = sm[valid].astype(np.float64)
    return {
        "time": parse_date_from_name(path),
        "n_pixels": int(valid.sum()),
        "soil_moisture_mean": float(np.nanmean(vals)),
        "soil_moisture_std": float(np.nanstd(vals)),
        "source_file": path.name,
    }


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--spec-path",
        default="/home/ubuntu/work/insar_mcmc/outputs_external_constraints/bologna_external_constraint_spec.json",
    )
    p.add_argument(
        "--smap-dir",
        default="/home/ubuntu/work/insar_mcmc/outputs_external_constraints/smap_matched_raw",
    )
    p.add_argument(
        "--output-dir",
        default="/home/ubuntu/work/insar_mcmc/outputs_external_constraints/smap_processed",
    )
    p.add_argument(
        "--output-prefix",
        default="bologna_smap_surface_soil_moisture",
        help="Prefix for CSV/JSON output files",
    )
    return p


def main() -> None:
    args = build_parser().parse_args()
    spec = json.loads(Path(args.spec_path).read_text())
    bbox = spec["bbox"]

    smap_dir = Path(args.smap_dir)
    files = sorted(smap_dir.glob("*.h5"))
    rows = [extract_one(path, bbox) for path in files]
    df = pd.DataFrame(rows).sort_values("time")

    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_csv = out_dir / f"{args.output_prefix}_timeseries.csv"
    out_json = out_dir / f"{args.output_prefix}_summary.json"
    df.to_csv(out_csv, index=False)

    summary = {
        "n_files": int(len(files)),
        "n_valid_times": int(df["n_pixels"].gt(0).sum()) if not df.empty else 0,
        "time_start": str(df["time"].min().date()) if not df.empty else None,
        "time_end": str(df["time"].max().date()) if not df.empty else None,
        "mean_of_means": float(df["soil_moisture_mean"].mean()) if not df.empty else None,
        "std_of_means": float(df["soil_moisture_mean"].std()) if not df.empty else None,
        "bbox": bbox,
        "smap_dir": str(smap_dir),
    }
    out_json.write_text(json.dumps(summary, indent=2))
    print(df.head())
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
