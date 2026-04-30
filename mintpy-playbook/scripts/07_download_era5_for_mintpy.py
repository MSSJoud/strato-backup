#!/usr/bin/env python3
"""Prepare or download ERA5 pressure-level GRIB files for MintPy/PyAPS."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

import h5py


PRESSURE_LEVELS = [
    "1", "2", "3", "5", "7", "10", "20", "30", "50", "70",
    "100", "125", "150", "175", "200", "225", "250", "300", "350", "400",
    "450", "500", "550", "600", "650", "700", "750", "775", "800", "825",
    "850", "875", "900", "925", "950", "975", "1000",
]

VARIABLES = ["geopotential", "temperature", "specific_humidity"]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Download ERA5 pressure-level files in the format MintPy/PyAPS expects."
    )
    parser.add_argument(
        "--timeseries",
        default="/mnt/data/aoi_3_bologna/mintpy_filtered/timeseries_SET.h5",
        help="MintPy time-series file containing the acquisition dates.",
    )
    parser.add_argument(
        "--weather-dir",
        default="/mnt/data/aoi_3_bologna_weather",
        help="Parent weather directory. Files are stored in WEATHER_DIR/ERA5.",
    )
    parser.add_argument(
        "--hour",
        default="05",
        help="UTC hour string expected by PyAPS, e.g. 05 or 12.",
    )
    parser.add_argument(
        "--bbox",
        default="40,50,0,20",
        help="South,North,West,East in degrees. Default matches the failed MintPy request.",
    )
    parser.add_argument(
        "--dataset",
        default="reanalysis-era5-pressure-levels",
        help="CDS dataset name.",
    )
    parser.add_argument(
        "--download",
        action="store_true",
        help="Actually download with cdsapi. Without this, only print a plan.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Optional limit on number of dates to process, useful for testing.",
    )
    return parser.parse_args()


def read_dates(timeseries_file: Path) -> list[str]:
    with h5py.File(timeseries_file, "r") as f:
        raw = f["date"][:]
    dates = [d.decode("utf-8") if isinstance(d, bytes) else str(d) for d in raw]
    return dates


def bbox_parts(bbox_text: str) -> tuple[float, float, float, float]:
    south, north, west, east = [float(x.strip()) for x in bbox_text.split(",")]
    return south, north, west, east


def fmt_coord(prefix_pos: str, prefix_neg: str, value: float) -> str:
    prefix = prefix_pos if value >= 0 else prefix_neg
    magnitude = int(abs(value))
    return f"{prefix}{magnitude}"


def output_name(south: float, north: float, west: float, east: float, date: str, hour: str) -> str:
    south_tag = fmt_coord("N", "S", south)
    north_tag = fmt_coord("N", "S", north)
    west_tag = fmt_coord("E", "W", west)
    east_tag = fmt_coord("E", "W", east)
    return f"ERA5_{south_tag}_{north_tag}_{west_tag}_{east_tag}_{date}_{hour}.grb"


def request_payload(date: str, hour: str, south: float, north: float, west: float, east: float) -> dict:
    return {
        "product_type": ["reanalysis"],
        "variable": VARIABLES,
        "year": [date[0:4]],
        "month": [date[4:6]],
        "day": [date[6:8]],
        "time": [f"{hour}:00"],
        "pressure_level": PRESSURE_LEVELS,
        "data_format": "grib",
        "area": [north, west, south, east],
    }


def main() -> int:
    args = parse_args()
    timeseries_file = Path(args.timeseries)
    weather_dir = Path(args.weather_dir)
    era5_dir = weather_dir / "ERA5"
    era5_dir.mkdir(parents=True, exist_ok=True)

    south, north, west, east = bbox_parts(args.bbox)
    dates = read_dates(timeseries_file)
    if args.limit > 0:
        dates = dates[: args.limit]

    jobs: list[tuple[str, Path, dict]] = []
    existing = 0
    for date in dates:
        out_file = era5_dir / output_name(south, north, west, east, date, args.hour)
        if out_file.exists() and out_file.stat().st_size > 0:
            existing += 1
            continue
        jobs.append((date, out_file, request_payload(date, args.hour, south, north, west, east)))

    print(f"Timeseries file: {timeseries_file}")
    print(f"Weather dir:     {weather_dir}")
    print(f"ERA5 dir:        {era5_dir}")
    print(f"Hour:            {args.hour}:00 UTC")
    print(f"BBox S,N,W,E:    {south},{north},{west},{east}")
    print(f"Dates in stack:  {len(dates)}")
    print(f"Existing files:  {existing}")
    print(f"Missing files:   {len(jobs)}")
    if jobs:
        print(f"First target:    {jobs[0][1]}")
        print(f"Last target:     {jobs[-1][1]}")

    if not args.download:
        print("")
        print("Dry run only. Re-run with --download after CDS API access is configured.")
        return 0

    try:
        import cdsapi
    except ImportError:
        print("ERROR: cdsapi is not installed in this Python environment.", file=sys.stderr)
        return 2

    client = cdsapi.Client()
    for idx, (date, out_file, payload) in enumerate(jobs, start=1):
        print(f"[{idx}/{len(jobs)}] {date} -> {out_file.name}")
        client.retrieve(args.dataset, payload, str(out_file))

    print("Download complete.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
