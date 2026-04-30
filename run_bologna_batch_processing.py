#!/usr/bin/env python3
"""
run_bologna_batch_processing.py

Batch process all Bologna 2023 interferograms with ISCE2.
Creates DEM symlinks in each run directory automatically.

Usage:
    python run_bologna_batch_processing.py --mode sbas --start 0 --count 10
    python run_bologna_batch_processing.py --mode ps --start 0 --count 10
"""

import os
import subprocess
from pathlib import Path
import argparse
from datetime import datetime

# Configuration
DEM_SOURCE = Path("/home/ubuntu/work/demLat_N45_N46_Lon_E011_E012.dem.wgs84")
DEM_XML = Path("/home/ubuntu/work/demLat_N45_N46_Lon_E011_E012.dem.wgs84.xml")
DEM_VRT = Path("/home/ubuntu/work/demLat_N45_N46_Lon_E011_E012.dem.wgs84.vrt")

def setup_run_directory(xml_path, run_root):
    """
    Create run directory and symlink DEM files.
    
    Returns: run_dir (Path object)
    """
    xml_name = xml_path.stem.replace('_topsApp', '')
    path_folder = xml_path.parent.name
    run_dir = run_root / path_folder / xml_name
    run_dir.mkdir(parents=True, exist_ok=True)
    
    # Symlink DEM files
    for src_file in [DEM_SOURCE, DEM_XML, DEM_VRT]:
        dst_file = run_dir / src_file.name
        if not dst_file.exists():
            dst_file.symlink_to(src_file)
    
    return run_dir

def run_isce2_pair(xml_path, run_dir, log_file):
    """
    Run ISCE2 topsApp.py for a single pair.
    
    Returns: (success, stdout, stderr)
    """
    cmd = [
        "bash", "-c",
        f"source ~/anaconda3/etc/profile.d/conda.sh && "
        f"conda activate isce2 && "
        f"topsApp.py {xml_path}"
    ]
    
    print(f"  Starting: {xml_path.name}")
    start_time = datetime.now()
    
    with open(log_file, 'w') as log:
        result = subprocess.run(
            cmd,
            cwd=run_dir,
            stdout=log,
            stderr=subprocess.STDOUT,
            text=True
        )
    
    duration = (datetime.now() - start_time).total_seconds() / 60
    success = result.returncode == 0
    
    status = "✓ SUCCESS" if success else f"✗ FAILED (exit {result.returncode})"
    print(f"  {status} - {duration:.1f} min - {xml_path.stem}")
    
    return success, duration

def main():
    parser = argparse.ArgumentParser(description='Batch process Bologna interferograms')
    parser.add_argument('--mode', choices=['sbas', 'ps'], required=True,
                        help='Processing mode: sbas (114 pairs) or ps (345 pairs)')
    parser.add_argument('--start', type=int, default=0,
                        help='Start index (0-based)')
    parser.add_argument('--count', type=int, default=None,
                        help='Number of pairs to process (default: all remaining)')
    parser.add_argument('--xml_root', type=str, default=None,
                        help='Override XML directory (default: bologna_sbas_ps_2023/xml_{mode}/)')
    parser.add_argument('--run_root', type=str, default=None,
                        help='Override run directory (default: bologna_sbas_ps_2023/run_{mode}/)')
    
    args = parser.parse_args()
    
    # Set defaults
    project_root = Path("/home/ubuntu/work/bologna_sbas_ps_2023")
    xml_root = Path(args.xml_root) if args.xml_root else project_root / f"xml_{args.mode}"
    run_root = Path(args.run_root) if args.run_root else project_root / f"run_{args.mode}"
    
    # Get XML files
    xml_files = sorted((xml_root / "path_15").glob("*.xml"))
    if not xml_files:
        print(f"[ERROR] No XML files found in {xml_root}/path_15/")
        return 1
    
    # Apply start/count filtering
    end_idx = args.start + args.count if args.count else len(xml_files)
    xml_files_subset = xml_files[args.start:end_idx]
    
    if not xml_files_subset:
        print(f"[ERROR] No files in range {args.start}:{end_idx}")
        return 1
    
    print("=" * 100)
    print(f"BOLOGNA {args.mode.upper()} BATCH PROCESSING")
    print("=" * 100)
    print(f"Mode:       {args.mode}")
    print(f"XML root:   {xml_root}")
    print(f"Run root:   {run_root}")
    print(f"Total XMLs: {len(xml_files)}")
    print(f"Processing: {args.start} to {end_idx - 1} ({len(xml_files_subset)} pairs)")
    print(f"DEM:        {DEM_SOURCE}")
    print("=" * 100)
    
    # Create run root
    run_root.mkdir(parents=True, exist_ok=True)
    
    # Process each pair
    results = []
    total_time = 0
    
    for i, xml_path in enumerate(xml_files_subset, start=args.start):
        print(f"\n[{i+1}/{len(xml_files)}] Processing pair {i+1}:")
        
        # Setup run directory with DEM symlinks
        run_dir = setup_run_directory(xml_path, run_root)
        log_file = run_dir / "topsApp.log"
        
        # Run ISCE2
        success, duration = run_isce2_pair(xml_path, run_dir, log_file)
        total_time += duration
        
        results.append({
            'index': i,
            'xml': xml_path.name,
            'run_dir': run_dir,
            'success': success,
            'duration': duration,
            'log': log_file
        })
        
        # Stop on first failure (optional - could continue)
        if not success:
            print(f"\n[ERROR] Processing failed. See log: {log_file}")
            print(f"        Stopping batch processing.")
            break
    
    # Summary
    print("\n" + "=" * 100)
    print("BATCH PROCESSING SUMMARY")
    print("=" * 100)
    successes = sum(1 for r in results if r['success'])
    failures = len(results) - successes
    print(f"Processed: {len(results)} pairs")
    print(f"Success:   {successes}")
    print(f"Failed:    {failures}")
    print(f"Total time: {total_time/60:.1f} hours")
    print(f"Avg time:  {total_time/len(results):.1f} min per pair")
    
    if failures > 0:
        print("\nFailed pairs:")
        for r in results:
            if not r['success']:
                print(f"  - {r['xml']}")
                print(f"    Log: {r['log']}")
    
    print("=" * 100)
    
    return 0 if failures == 0 else 1

if __name__ == "__main__":
    exit(main())
