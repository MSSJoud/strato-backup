#!/usr/bin/env python3


"""
unwrap_all.py  —  Batch symlink mask + unwrap merged interferograms with SNAPHU.
Author: MSSJoud
Date: 2025-08-15 - NOT TESTED 
DESCRIPTION
-----------
This script automates the GMTSAR interferogram unwrapping step in the `merge/` directory:
1. Finds all subdirectories that contain `phasefilt.grd` (treated as merged IFG folders).
2. Optionally symlinks a mask file (e.g., mask_def.grd or landmask_ra.grd) into each IFG folder.
3. Runs `snaphu_interp.csh <threshold> <max_discontinuity>` inside each IFG folder.
4. Displays a tqdm progress bar and prints a summary at the end.

USAGE EXAMPLES
--------------
# Basic run from inside merge/ (auto-detect mask)
python3 unwrap_all.py

# Run from any location, specify merge dir
python3 unwrap_all.py --merge /path/to/merge

# Specify SNAPHU parameters
python3 unwrap_all.py --threshold 0.075 --discont 40

# Specify a custom mask file name in merge/
python3 unwrap_all.py --mask mask_def.grd

# Dry run (only show planned actions without running SNAPHU)
python3 unwrap_all.py --dry-run

REQUIRED PACKAGES
-----------------
- Python 3.7+
- tqdm (progress bar)  →  install via:  python3 -m pip install --user tqdm

SYSTEM REQUIREMENTS
-------------------
- GMTSAR installed and `snaphu_interp.csh` available in your PATH.
- `phasefilt.grd` already generated in each merged IFG folder.
- Optional: mask file (e.g., mask_def.grd or landmask_ra.grd) in merge root.

NOTES
-----
- The script runs unwrapping sequentially (safe for memory usage).
- Summary of successes/failures is printed at the end.
"""

import os
import sys
import argparse
import subprocess
from pathlib import Path

def main():
    ap = argparse.ArgumentParser(description="Symlink mask and unwrap merged interferograms with tqdm progress.")
    ap.add_argument("--merge", default=".", help="Path to merge directory (default: current dir)")
    ap.add_argument("--threshold", type=float, default=0.075, help="SNAPHU coherence threshold (default: 0.075)")
    ap.add_argument("--discont", type=int, default=40, help="SNAPHU max discontinuity (default: 40)")
    ap.add_argument("--mask", default=None, help="Mask filename in merge/ to link into each IFG (auto-detect if omitted)")
    ap.add_argument("--dry-run", action="store_true", help="Show what would be done without running snaphu")
    args = ap.parse_args()

    merge = Path(args.merge).resolve()
    if not merge.is_dir():
        print(f"ERROR: merge directory not found: {merge}", file=sys.stderr)
        sys.exit(2)

    # auto-detect a mask in the merge root if not provided
    mask_candidates = ["mask_def.grd", "landmask_ra.grd"]
    mask_path = None
    if args.mask:
        mp = merge / args.mask
        if mp.exists():
            mask_path = mp
        else:
            print(f"WARNING: requested mask {mp} not found; continuing without mask link.")
    else:
        for name in mask_candidates:
            mp = merge / name
            if mp.exists():
                mask_path = mp
                break

    # pick IFG dirs: any subdir that contains phasefilt.grd
    ifg_dirs = []
    for p in sorted(merge.iterdir()):
        if p.is_dir():
            if (p / "phasefilt.grd").exists():
                ifg_dirs.append(p)

    if not ifg_dirs:
        print("No interferogram directories with phasefilt.grd found under:", merge)
        sys.exit(1)

    n = len(ifg_dirs)
    print(f"\n→ Unwrapping with SNAPHU: threshold={args.threshold}  max_discontinuity={args.discont}")
    print(f"→ Merge dir: {merge}")
    print(f"→ Interferograms to process: {n}")
    if mask_path:
        print(f"→ Will link mask: {mask_path.name} into each directory")
    else:
        print("→ No mask found/provided; proceeding without mask links.")

    # tqdm is optional; fall back gracefully if not installed
    try:
        from tqdm import tqdm
        bar = tqdm(ifg_dirs, total=n, unit="ifg", desc="Unwrapping")
    except Exception:
        bar = ifg_dirs  # simple iterable; no progress bar

    successes, failures = [], []

    for d in bar:
        # 1) link mask if requested/available
        if mask_path:
            link_target = d / mask_path.name
            if not link_target.exists():
                try:
                    # link from ../maskname (nice relative link) if merge is parent
                    rel = os.path.relpath(mask_path, d)
                    os.symlink(rel, link_target)
                except FileExistsError:
                    pass
                except Exception as e:
                    print(f"WARNING: could not link mask in {d.name}: {e}", file=sys.stderr)

        if args.dry_run:
            print(f"[DRY] would run in {d.name}: snaphu_interp.csh {args.threshold} {args.discont}")
            successes.append(d.name + " (DRY)")
            continue

        # 2) run snaphu_interp.csh inside the IFG dir
        try:
            proc = subprocess.run(
                ["snaphu_interp.csh", str(args.threshold), str(args.discont)],
                cwd=str(d),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                check=False  # don't raise automatically; we inspect returncode
            )
            if proc.returncode == 0:
                successes.append(d.name)
            else:
                failures.append((d.name, proc.returncode))
                # print a short tail of output to help debug
                tail = "\n".join(proc.stdout.splitlines()[-15:])
                print(f"\nERROR ({d.name}): snaphu exited {proc.returncode}\n{tail}\n", file=sys.stderr)
        except FileNotFoundError:
            print("\nERROR: snaphu_interp.csh not found in PATH. Make sure GMTSAR bin is on PATH.\n", file=sys.stderr)
            sys.exit(127)
        except Exception as e:
            failures.append((d.name, -1))
            print(f"\nERROR ({d.name}): {e}\n", file=sys.stderr)

    # summary
    print("\n=== Summary ===")
    print(f"OK: {len(successes)}")
    print(f"FAIL: {len(failures)}")
    if failures:
        print("Failed interferograms (name : exitcode):")
        for name, code in failures[:20]:
            print(f"  {name} : {code}")
        if len(failures) > 20:
            print(f"  ... and {len(failures)-20} more")

if __name__ == "__main__":
    main()
