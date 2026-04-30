#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
import shutil


REQUIRED_SUFFIXES = (
    "_unw_phase_clipped.tif",
    "_corr_clipped.tif",
    "_dem_clipped.tif",
    "_lv_theta_clipped.tif",
    "_lv_phi_clipped.tif",
    "_water_mask_clipped.tif",
)


def is_complete(pair_dir: Path) -> tuple[bool, list[str]]:
    missing: list[str] = []
    for suffix in REQUIRED_SUFFIXES:
        if not any(pair_dir.glob(f"*{suffix}")):
            missing.append(suffix)
    return (len(missing) == 0, missing)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Create a filtered symlink view of complete HyP3 interferogram folders."
    )
    parser.add_argument("--source", required=True, help="Source HyP3 pair directory root")
    parser.add_argument("--output", required=True, help="Filtered output directory")
    parser.add_argument(
        "--prefix",
        default="S1",
        help="Directory name prefix to treat as HyP3 pair folders (default: S1)",
    )
    args = parser.parse_args()

    source = Path(args.source)
    output = Path(args.output)

    if not source.is_dir():
        raise SystemExit(f"Source directory not found: {source}")

    output.mkdir(parents=True, exist_ok=True)

    kept = 0
    skipped = 0
    manifest_lines = []

    for pair_dir in sorted(p for p in source.iterdir() if p.is_dir() and p.name.startswith(args.prefix)):
        ok, missing = is_complete(pair_dir)
        target = output / pair_dir.name

        if target.exists() or target.is_symlink():
            if target.is_symlink() or target.is_file():
                target.unlink()
            else:
                shutil.rmtree(target)

        if ok:
            target.symlink_to(pair_dir, target_is_directory=True)
            kept += 1
            manifest_lines.append(f"KEEP {pair_dir.name}")
        else:
            skipped += 1
            manifest_lines.append(f"SKIP {pair_dir.name} :: missing {', '.join(missing)}")

    manifest = output / "manifest.txt"
    manifest.write_text("\n".join(manifest_lines) + ("\n" if manifest_lines else ""))

    print(f"Source : {source}")
    print(f"Output : {output}")
    print(f"Kept   : {kept}")
    print(f"Skipped: {skipped}")
    print(f"Manifest: {manifest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
