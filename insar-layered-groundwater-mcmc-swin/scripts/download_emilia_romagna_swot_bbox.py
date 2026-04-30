#!/usr/bin/env python3
"""Download SWOT hydrology granules over a broad Emilia-Romagna bbox.

This is the fast path for regional exploration when we do not yet have
feature IDs for Hydrocron. It downloads SWOT RiverSP reach and LakeSP obs
granules whose spatial metadata intersect the requested bounding box.

Important:
- SWOT does not overlap the current Bologna InSAR period. SWOT starts on
  2022-12-16, while the current Bologna InSAR series ends on 2022-10-01.
- These files are best used for regional surface-water analysis and future
  comparison, not direct time-overlap fusion with the current InSAR series.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path


DEFAULT_SHORT_NAMES = (
    "SWOT_L2_HR_RiverSP_reach_2.0",
    "SWOT_L2_HR_LakeSP_obs_2.0",
)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--west", type=float, default=9.15)
    p.add_argument("--south", type=float, default=43.70)
    p.add_argument("--east", type=float, default=12.85)
    p.add_argument("--north", type=float, default=45.15)
    p.add_argument("--start-time", default="2022-12-16")
    p.add_argument("--end-time", default="2026-04-04")
    p.add_argument("--short-name", nargs="+", default=list(DEFAULT_SHORT_NAMES))
    p.add_argument(
        "--filename-substring",
        default="_EU_",
        help="Keep only granules whose first data link contains this substring. Use empty string to disable.",
    )
    p.add_argument(
        "--out-dir",
        default="/home/ubuntu/work/insar_mcmc/outputs_external_constraints/swot_emilia_romagna_raw",
    )
    p.add_argument("--max-per-product", type=int, default=500)
    p.add_argument("--dry-run", action="store_true")
    return p


def main() -> None:
    args = build_parser().parse_args()
    try:
        import earthaccess
    except ModuleNotFoundError as exc:
        raise SystemExit("earthaccess is required. Install it first.") from exc

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    bbox = (args.west, args.south, args.east, args.north)
    earthaccess.login()

    all_items = []
    manifest: dict[str, object] = {
        "bbox": {
            "west": args.west,
            "south": args.south,
            "east": args.east,
            "north": args.north,
        },
        "start_time": args.start_time,
        "end_time": args.end_time,
        "products": {},
    }

    seen_urls: set[str] = set()
    for short_name in args.short_name:
        results = earthaccess.search_data(
            short_name=short_name,
            temporal=(args.start_time, args.end_time),
            bounding_box=bbox,
            count=args.max_per_product,
        )
        rows = []
        for item in results:
            links = item.data_links()
            if not links:
                continue
            url = links[0]
            if args.filename_substring and args.filename_substring not in url:
                continue
            if url in seen_urls:
                continue
            seen_urls.add(url)
            all_items.append(item)
            rows.append(
                {
                    "umm": item.get("umm", {}).get("Meta", {}).get("NativeGranuleId"),
                    "url": url,
                }
            )
        manifest["products"][short_name] = {
            "n_results": len(rows),
            "sample": rows[:5],
        }

    manifest_path = out_dir / "swot_emilia_romagna_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2))
    print(json.dumps(manifest, indent=2))
    print(f"Saved manifest to {manifest_path}")

    if args.dry_run:
        return

    if all_items:
        earthaccess.download(all_items, str(out_dir))
        print(f"Downloaded {len(all_items)} granules to {out_dir}")
    else:
        print("No SWOT granules matched the Emilia-Romagna bbox.")


if __name__ == "__main__":
    main()
