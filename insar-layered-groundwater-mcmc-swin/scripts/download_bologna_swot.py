#!/usr/bin/env python3
"""Fetch SWOT hydrology time series for Bologna-area reaches/lakes.

This script uses the Hydrocron API, which is the fastest route once you know
the relevant SWOT feature IDs.

Important:
- Hydrocron works on SWOT river/lake feature IDs, not an arbitrary bbox alone.
- For rivers, provide reach IDs from the SWORD database.
- For lakes/reservoirs, provide lake IDs from the PLD-linked SWOT products.
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

import requests


HYDROCRON_URL = "https://soto.podaac.earthdatacloud.nasa.gov/hydrocron/v1/timeseries"


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--feature-type", choices=("Reach", "Node", "Lake"), default="Reach")
    p.add_argument("--feature-ids", nargs="+", help="One or more SWOT feature IDs.")
    p.add_argument("--feature-id-file", help="CSV/TXT file with one feature ID per line.")
    p.add_argument("--start-time", required=True, help="YYYY-MM-DD")
    p.add_argument("--end-time", required=True, help="YYYY-MM-DD")
    p.add_argument("--fields", nargs="+", default=["wse", "width", "slope2", "d_x_area"])
    p.add_argument("--output-path", default="/home/ubuntu/work/insar_mcmc/outputs_external_constraints/swot_hydrocron_timeseries.json")
    return p


def load_feature_ids(args: argparse.Namespace) -> list[str]:
    ids: list[str] = []
    if args.feature_ids:
        ids.extend(args.feature_ids)
    if args.feature_id_file:
        path = Path(args.feature_id_file)
        text = path.read_text().splitlines()
        ids.extend([line.strip() for line in text if line.strip()])
    if not ids:
        raise SystemExit("Provide --feature-ids or --feature-id-file.")
    return ids


def fetch_one(feature_type: str, feature_id: str, start_time: str, end_time: str, fields: list[str]) -> dict:
    params = {
        "feature": feature_type,
        "feature_id": feature_id,
        "start_time": start_time,
        "end_time": end_time,
        "output": "json",
        "fields": ",".join(fields),
    }
    resp = requests.get(HYDROCRON_URL, params=params, timeout=120)
    resp.raise_for_status()
    return resp.json()


def main() -> None:
    args = build_parser().parse_args()
    feature_ids = load_feature_ids(args)
    output_path = Path(args.output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    payload = {
        "feature_type": args.feature_type,
        "start_time": args.start_time,
        "end_time": args.end_time,
        "fields": args.fields,
        "results": {},
    }
    for feature_id in feature_ids:
        print(f"Fetching {args.feature_type} {feature_id}...")
        payload["results"][feature_id] = fetch_one(
            feature_type=args.feature_type,
            feature_id=feature_id,
            start_time=args.start_time,
            end_time=args.end_time,
            fields=args.fields,
        )

    output_path.write_text(json.dumps(payload, indent=2))

    csv_path = output_path.with_suffix(".csv")
    with csv_path.open("w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["feature_id", "time_str", *args.fields])
        for feature_id, result in payload["results"].items():
            records = result.get("results", [])
            for row in records:
                writer.writerow([feature_id, row.get("time_str"), *[row.get(field) for field in args.fields]])

    print(f"Saved JSON to {output_path}")
    print(f"Saved CSV to {csv_path}")


if __name__ == "__main__":
    main()
