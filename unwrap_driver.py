#!/usr/bin/env python3
"""
unwrap_driver.py — GMTSAR merge/ batch unwrapping with mask/region/parallel options.
Author: MSSJoud
Date: 2025-08-15 - NOT TESTED 
WHAT IT DOES
------------
1) Collects merged IFG directories under the given merge/ path (those containing phasefilt.grd).
2) (Optional) Builds a land/coherence mask and places it in merge/ (mask_def.grd), then symlinks
   that mask (or a user-specified one) into every IFG directory.
3) Runs snaphu_interp.csh inside each IFG directory with:
     snaphu_interp.csh <threshold> <max_discont> [minR/maxR/minAz/maxAz]
4) Shows a tqdm progress bar. Skips IFGs that already have unwrap.grd unless --force.
5) Can run jobs in parallel (use with care; each SNAPHU can use several GB of RAM).

USAGE EXAMPLES
--------------
# basic (sequential), auto-detect mask if present
./unwrap_driver.py --merge . --threshold 0.075 --discont 40

# create a coherence mask at threshold 0.075 from all corr.grd and then unwrap
./unwrap_driver.py --build-coh-mask 0.075 --threshold 0.075 --discont 40

# link an existing mask name (in merge/) and unwrap only a subregion
./unwrap_driver.py --mask mask_def.grd --region 1000 3000 24000 27000 --threshold 0.1 --discont 40

# run in parallel with 6 workers (ensure enough RAM)
./unwrap_driver.py --parallel 6 --threshold 0.075 --discont 40

# dry run (print planned commands; don’t run SNAPHU)
./unwrap_driver.py --dry-run

REQUIREMENTS
------------
- Python 3.7+; tqdm (python -m pip install --user tqdm)
- GMTSAR on PATH (snaphu_interp.csh, optional: gmt)
- In each IFG folder: phasefilt.grd (and corr.grd if you want to build a mask)
"""

from __future__ import annotations
import os
import sys
import shlex
import argparse
import subprocess
from pathlib import Path
from typing import Iterable, List, Optional, Tuple

def run(cmd: List[str], cwd: Optional[Path]=None, check=False) -> subprocess.CompletedProcess:
    """Run a command and return CompletedProcess (stdout+stderr combined)."""
    return subprocess.run(
        cmd, cwd=str(cwd) if cwd else None,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, check=check
    )

def detect_ifgs(merge: Path) -> List[Path]:
    """IFG dirs are those containing phasefilt.grd."""
    return sorted([p for p in merge.iterdir() if p.is_dir() and (p / "phasefilt.grd").exists()])

def build_coh_mask(merge: Path, thresh: float, stack_name="corr_stack.grd", mask_name="mask_def.grd") -> Path:
    """
    Build a coherence stack and threshold it using GMT:
      1) Gather all corr.grd paths under IFG dirs.
      2) Stack by average -> corr_stack.grd (uses GMT 'grdmath').
      3) Threshold -> mask_def.grd (values below 'thresh' masked to NaN, above kept).

    Returns path to mask_def.grd.
    """
    corr_list = [str(p / "corr.grd") for p in detect_ifgs(merge) if (p / "corr.grd").exists()]
    if not corr_list:
        raise RuntimeError("No corr.grd files found; cannot build coherence mask.")

    # Build the grdmath expression: (g1 g2 ADD ... N DIV)
    # Example for 3: g1 g2 ADD g3 ADD 3 DIV
    expr_terms = []
    for i, g in enumerate(corr_list, 1):
        expr_terms.append(g)
        if i > 1:
            expr_terms.append("ADD")
    expr_terms.append(str(len(corr_list)))
    expr_terms.append("DIV")

    stack = merge / stack_name
    mask  = merge / mask_name

    # 1) Average stack
    cmd_stack = ["gmt", "grdmath"] + expr_terms + ["=", str(stack)]
    cp = run(cmd_stack, cwd=merge)
    if cp.returncode != 0:
        raise RuntimeError(f"GMT failed stacking coherence:\n{cp.stdout}")

    # 2) Threshold to mask (GE -> keep; else -> NaN)
    #    corr_stack.grd <thresh> GE 0 NAN =
    cmd_mask = ["gmt", "grdmath", str(stack), str(thresh), "GE", "0", "NAN", "=", str(mask)]
    cp = run(cmd_mask, cwd=merge)
    if cp.returncode != 0:
        raise RuntimeError(f"GMT failed making mask_def.grd:\n{cp.stdout}")

    return mask

def link_mask(ifg_dir: Path, mask_path: Path) -> None:
    target = ifg_dir / mask_path.name
    if not target.exists():
        rel = os.path.relpath(mask_path, ifg_dir)
        try:
            os.symlink(rel, target)
        except FileExistsError:
            pass

def snaphu_cmd(threshold: float, discont: int, region: Optional[Tuple[int,int,int,int]]=None) -> List[str]:
    """
    Build the snaphu_interp.csh command. Region (minR, maxR, minAz, maxAz) if provided.
    """
    base = ["snaphu_interp.csh", str(threshold), str(discont)]
    if region:
        rmin, rmax, amin, amax = region
        base.append(f"{rmin}/{rmax}/{amin}/{amax}")
    return base

def unwrap_one(ifg_dir: Path, threshold: float, discont: int,
               region: Optional[Tuple[int,int,int,int]],
               mask_path: Optional[Path], force: bool, dry_run: bool) -> Tuple[str, int, str]:
    """
    Run snaphu in one IFG. Returns (name, returncode, message_tail).
    """
    if not force and (ifg_dir / "unwrap.grd").exists():
        return (ifg_dir.name, 0, "[skip] unwrap.grd exists")

    if mask_path and not (ifg_dir / mask_path.name).exists():
        link_mask(ifg_dir, mask_path)

    cmd = snaphu_cmd(threshold, discont, region)
    if dry_run:
        return (ifg_dir.name, 0, "DRY: " + " ".join(shlex.quote(c) for c in cmd))

    cp = run(cmd, cwd=ifg_dir)
    tail = "\n".join(cp.stdout.splitlines()[-15:])
    return (ifg_dir.name, cp.returncode, tail)

def main():
    ap = argparse.ArgumentParser(description="Batch unwrap with optional mask, region cut, and parallel workers.")
    ap.add_argument("--merge", default=".", help="Path to merge directory (default: current dir)")
    ap.add_argument("--threshold", type=float, default=0.075, help="SNAPHU coherence threshold")
    ap.add_argument("--discont", type=int, default=40, help="SNAPHU max discontinuity")
    ap.add_argument("--mask", default=None, help="Mask file name in merge/ to link (e.g., mask_def.grd)")
    ap.add_argument("--build-coh-mask", type=float, metavar="COH_THR",
                    help="Build mask_def.grd from all corr.grd files at this threshold before unwrapping")
    ap.add_argument("--region", nargs=4, type=int, metavar=("MINR","MAXR","MINAZ","MAXAZ"),
                    help="Optional region cut (range/azimuth) passed to SNAPHU")
    ap.add_argument("--parallel", type=int, default=1, help="Number of parallel workers (>=1). Use with care.")
    ap.add_argument("--force", action="store_true", help="Re-run even if unwrap.grd exists")
    ap.add_argument("--dry-run", action="store_true", help="Print planned actions only")
    args = ap.parse_args()

    merge = Path(args.merge).resolve()
    if not merge.is_dir():
        print(f"ERROR: merge directory not found: {merge}", file=sys.stderr)
        sys.exit(2)

    # 1) gather IFGs
    ifgs = detect_ifgs(merge)
    if not ifgs:
        print("No IFG dirs (with phasefilt.grd) found.")
        sys.exit(1)

    # 2) establish mask (if requested or auto-detect)
    mask_path: Optional[Path] = None
    if args.build_coh_mask is not None:
        print(f"→ Building coherence mask at threshold {args.build_coh_mask} …")
        try:
            mask_path = build_coh_mask(merge, args.build_coh_mask)
        except Exception as e:
            print(f"ERROR building coherence mask: {e}", file=sys.stderr)
            sys.exit(1)
        print(f"   created: {mask_path.name}")

    if args.mask:
        mp = merge / args.mask
        if not mp.exists():
            print(f"ERROR: requested mask not found: {mp}", file=sys.stderr)
            sys.exit(1)
        mask_path = mp
    else:
        # auto-detect a common mask name if present
        for cand in ("mask_def.grd", "landmask_ra.grd"):
            mp = merge / cand
            if mp.exists():
                mask_path = mp
                break

    # 3) summary
    print(f"\n→ Unwrapping with SNAPHU: threshold={args.threshold}  discont={args.discont}")
    if args.region:
        print(f"→ Region cut: {tuple(args.region)} (minR,maxR,minAz,maxAz)")
    if mask_path:
        print(f"→ Using mask: {mask_path.name} (linked into each IFG)")
    print(f"→ IFGs to process: {len(ifgs)}  (parallel={args.parallel})")
    if args.dry_run:
        print("→ DRY RUN (no commands executed)\n")

    # 4) run (sequential or parallel)
    results = []
    try:
        from tqdm import tqdm
        progress = tqdm(total=len(ifgs), unit="ifg", desc="Unwrapping")
        def update(res):
            results.append(res)
            progress.update(1)
    except Exception:
        progress = None
        def update(res): results.append(res)

    if args.parallel <= 1:
        for d in ifgs:
            res = unwrap_one(d, args.threshold, args.discont, tuple(args.region) if args.region else None,
                             mask_path, args.force, args.dry_run)
            update(res)
    else:
        # careful: SNAPHU memory use can be large; set workers reasonably
        from concurrent.futures import ThreadPoolExecutor, as_completed
        with ThreadPoolExecutor(max_workers=args.parallel) as ex:
            futs = [ex.submit(unwrap_one, d, args.threshold, args.discont,
                              tuple(args.region) if args.region else None,
                              mask_path, args.force, args.dry_run)
                    for d in ifgs]
            for fut in as_completed(futs):
                update(fut.result())

    if progress: progress.close()

    # 5) report
    ok = [(n, t) for (n, rc, t) in results if rc == 0]
    bad = [(n, rc, t) for (n, rc, t) in results if rc != 0]

    print("\n=== Summary ===")
    print(f"OK:   {len(ok)}")
    print(f"FAIL: {len(bad)}")
    if bad:
        print("\nFailed interferograms (name : exitcode) — tail of output shown:")
        for n, rc, tail in bad[:12]:
            print(f"\n--- {n} : {rc} ---\n{tail}")
        if len(bad) > 12:
            print(f"\n… and {len(bad)-12} more failures not shown")

if __name__ == "__main__":
    main()
