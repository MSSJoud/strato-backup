#!/usr/bin/env python3
"""
Download precise orbit files (.EOF) for Bologna 2023 SLCs.
Uses sentineleof package.

Install: pip install sentineleof
"""

import subprocess
from pathlib import Path
import argparse

def download_orbits_for_directory(slc_dir, orbit_dir, force=False):
    """
    Download orbit files for all SLCs in a directory.
    Uses sentineleof 'eof' command.
    """
    
    slc_path = Path(slc_dir)
    orbit_path = Path(orbit_dir)
    
    # Create orbit directory
    orbit_path.mkdir(parents=True, exist_ok=True)
    
    print("="*80)
    print("DOWNLOADING PRECISE ORBIT FILES (.EOF)")
    print("="*80)
    print(f"SLC directory:   {slc_path}")
    print(f"Orbit directory: {orbit_path}")
    print()
    
    # Check if eof command is available
    try:
        result = subprocess.run(["eof", "--version"], capture_output=True, text=True)
        print(f"✅ sentineleof version: {result.stdout.strip()}")
    except FileNotFoundError:
        print("❌ ERROR: 'eof' command not found!")
        print("\nInstall sentineleof:")
        print("  pip install sentineleof")
        print("\nOr use ISCE2's fetchOrbit.py:")
        print("  fetchOrbit.py -i <SAFE_dir> -o <orbit_dir>")
        return 1
    
    print()
    print("🛰  Downloading orbits...")
    print()
    
    # Download orbits
    cmd = [
        "eof",
        "--search-path", str(slc_path),
        "--save-dir", str(orbit_path)
    ]
    
    if force:
        cmd.append("--force-asf")
    
    try:
        result = subprocess.run(cmd, check=True, capture_output=True, text=True)
        print(result.stdout)
        
        # Count downloaded orbits
        orbit_files = list(orbit_path.glob("S1*.EOF"))
        print()
        print("="*80)
        print("DOWNLOAD COMPLETE")
        print("="*80)
        print(f"✅ Orbit files: {len(orbit_files)}")
        print(f"   Location: {orbit_path}")
        print()
        
        if len(orbit_files) > 0:
            print("Sample orbit files:")
            for orbit_file in sorted(orbit_files)[:5]:
                print(f"  • {orbit_file.name}")
            if len(orbit_files) > 5:
                print(f"  ... and {len(orbit_files) - 5} more")
        
        return 0
        
    except subprocess.CalledProcessError as e:
        print(f"❌ Orbit download failed!")
        print(f"   Error: {e}")
        print(f"   Output: {e.stdout}")
        print(f"   Error: {e.stderr}")
        return 1

def main():
    parser = argparse.ArgumentParser(
        description="Download precise orbit files for Sentinel-1 SLCs"
    )
    parser.add_argument(
        '--slc-dir',
        required=True,
        help='Directory containing SLC .zip files'
    )
    parser.add_argument(
        '--orbit-dir',
        required=True,
        help='Directory to save orbit .EOF files'
    )
    parser.add_argument(
        '--force',
        action='store_true',
        help='Force download from ASF (skip cache)'
    )
    
    args = parser.parse_args()
    
    return download_orbits_for_directory(args.slc_dir, args.orbit_dir, args.force)

if __name__ == "__main__":
    exit(main())
