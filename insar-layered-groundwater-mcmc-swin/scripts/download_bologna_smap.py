#!/usr/bin/env python3
"""Download SMAP files for the Bologna bbox with earthaccess.

Fastest intended use:
- generate a bbox/time spec from ``prepare_bologna_external_constraints.py``
- authenticate with Earthdata Login
- search and download the chosen SMAP product

Recommended starting products for this project:
- ``SPL4SMGP`` for surface/root-zone soil moisture constraints
- ``SPL3SMP_E`` if you want a simpler radiometer-only surface-soil product
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def load_spec(path: str) -> dict:
    return json.loads(Path(path).read_text())


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--spec-path",
        default="/home/ubuntu/work/insar_mcmc/outputs_external_constraints/bologna_external_constraint_spec.json",
    )
    p.add_argument("--short-name", default="SPL4SMGP")
    p.add_argument("--version", default=None)
    p.add_argument("--count", type=int, default=1000)
    p.add_argument("--out-dir", default="/home/ubuntu/work/insar_mcmc/outputs_external_constraints/smap_raw")
    p.add_argument("--dry-run", action="store_true")
    return p


def main() -> None:
    args = build_parser().parse_args()
    spec = load_spec(args.spec_path)
    bbox = spec["bbox"]
    temporal = tuple(spec["temporal"])
    bounding_box = (bbox["lon_min"], bbox["lat_min"], bbox["lon_max"], bbox["lat_max"])

    try:
        import earthaccess
    except ModuleNotFoundError as exc:
        raise SystemExit(
            "earthaccess is required. Install it in the active environment, for example:\n"
            "  pip install earthaccess"
        ) from exc

    print("Authenticating with Earthdata Login...")
    earthaccess.login()

    print("Searching SMAP granules...")
    search_kwargs = dict(
        short_name=args.short_name,
        cloud_hosted=True,
        temporal=temporal,
        bounding_box=bounding_box,
        count=args.count,
    )
    if args.version:
        search_kwargs["version"] = args.version
    results = earthaccess.search_data(**search_kwargs)
    version_label = args.version if args.version else "latest-visible"
    print(f"Found {len(results)} granules for {args.short_name} ({version_label}).")

    if args.dry_run:
        for item in results[:5]:
            print(item)
        return

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    earthaccess.download(results, str(out_dir))
    print(f"Downloaded files to {out_dir}")


if __name__ == "__main__":
    main()
