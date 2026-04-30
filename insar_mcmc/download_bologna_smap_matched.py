#!/usr/bin/env python3
"""Download one SMAP daily granule per Bologna InSAR date.

This keeps the first pass small and aligned with the actual InSAR observation
times, which is much faster than pulling the full SMAP archive.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

import pandas as pd

from insar_mcmc.mintpy_h5_utils import load_insar_times


DATE_RE = re.compile(r"(\d{8})")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--insar-path", default="/mnt/data/aoi_3_bologna/mintpy_filtered/timeseries_SET_ERA5_ramp_demErr.h5")
    p.add_argument("--short-name", default="SPL3SMP_E")
    p.add_argument("--version", default=None)
    p.add_argument("--out-dir", default="/home/ubuntu/work/insar_mcmc/outputs_external_constraints/smap_matched_raw")
    p.add_argument("--count", type=int, default=5000)
    p.add_argument("--threads", type=int, default=8)
    p.add_argument("--force", action="store_true")
    p.add_argument("--dry-run", action="store_true")
    return p


def load_dates(insar_path: str) -> pd.DatetimeIndex:
    return pd.DatetimeIndex(load_insar_times(insar_path).normalize().unique())


def parse_item_date(item) -> pd.Timestamp | None:
    umm = item.get("umm", {}) if isinstance(item, dict) else item.get("umm", {})
    native = None
    if isinstance(umm, dict):
        native = umm.get("Meta", {}).get("NativeGranuleId")
    if native:
        m = DATE_RE.search(str(native))
        if m:
            return pd.to_datetime(m.group(1), format="%Y%m%d").normalize()
    for link in item.data_links() or []:
        m = DATE_RE.search(str(link))
        if m:
            return pd.to_datetime(m.group(1), format="%Y%m%d").normalize()
    return None


def main() -> None:
    args = build_parser().parse_args()
    try:
        import earthaccess
    except ModuleNotFoundError as exc:
        raise SystemExit("earthaccess is required. Install it first.") from exc

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    dates = load_dates(args.insar_path)
    earthaccess.login()

    search_kwargs = dict(
        short_name=args.short_name,
        temporal=(dates.min().strftime("%Y-%m-%d"), (dates.max() + pd.Timedelta(days=1)).strftime("%Y-%m-%d")),
        count=args.count,
        cloud_hosted=True,
    )
    if args.version:
        search_kwargs["version"] = args.version

    results = earthaccess.search_data(**search_kwargs)
    by_date: dict[pd.Timestamp, list] = {}
    for item in results:
        item_date = parse_item_date(item)
        if item_date is None:
            continue
        by_date.setdefault(item_date, []).append(item)

    selected = []
    seen_urls = set()
    manifest = []
    for date in dates:
        t0 = pd.Timestamp(date).normalize()
        key = t0
        candidates = by_date.get(key, [])
        if not candidates:
            manifest.append({"insar_date": t0.strftime("%Y-%m-%d"), "status": "no_match"})
            continue
        chosen = None
        for item in candidates:
            links = item.data_links()
            if not links:
                continue
            url = links[0]
            if url not in seen_urls:
                chosen = item
                seen_urls.add(url)
                manifest.append({"insar_date": t0.strftime("%Y-%m-%d"), "status": "matched", "url": url})
                break
        if chosen is not None:
            selected.append(chosen)
        else:
            url = candidates[0].data_links()[0] if candidates[0].data_links() else None
            manifest.append({"insar_date": t0.strftime("%Y-%m-%d"), "status": "duplicate", "url": url})

    manifest_path = out_dir / "smap_matched_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2))
    print(f"Matched {len(selected)} unique SMAP granules for {len(dates)} InSAR dates.")
    print(f"Saved manifest to {manifest_path}")

    if args.dry_run:
        for row in manifest[:10]:
            print(row)
        return

    if selected:
        earthaccess.download(selected, str(out_dir), threads=args.threads, force=args.force)
        print(f"Downloaded {len(selected)} granules to {out_dir}")


if __name__ == "__main__":
    main()
