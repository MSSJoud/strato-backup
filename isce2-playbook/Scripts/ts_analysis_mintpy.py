#!/usr/bin/env python3

"""
Script for MintPy time-series analysis on unzipped GeoTIFF files.

Usage:
    python3 ts_analysis_mintpy.py --data_dir <unzipped_data_dir> --work_dir <output_dir> --config_file <path_to_config_file>

Example:
    python3 ts_analysis_mintpy.py --data_dir ~/data_AOI-3/processed_interferograms --work_dir ~/data_AOI-3/time_series_output --config_file ~/mintpy_config.txt
"""

import argparse
from pathlib import Path
from typing import List, Union
from osgeo import gdal
import subprocess
import sys
if not gdal.UseExceptions():
    gdal.UseExceptions()




def get_common_overlap(file_list: List[Union[str, Path]]) -> List[float]:
    """Get the common overlap of GeoTIFF files with valid projWin ordering."""
    corners = [gdal.Info(str(file), format='json')['cornerCoordinates'] for file in file_list]

    # Extract bounding box values
    ulx_raw = [corner['upperLeft'][0] for corner in corners]
    uly_raw = [corner['upperLeft'][1] for corner in corners]
    lrx_raw = [corner['lowerRight'][0] for corner in corners]
    lry_raw = [corner['lowerRight'][1] for corner in corners]

    # Ensure correct ordering:
    ulx = max(min(x1, x2) for x1, x2 in zip(ulx_raw, lrx_raw))
    lrx = min(max(x1, x2) for x1, x2 in zip(ulx_raw, lrx_raw))
    uly = min(max(y1, y2) for y1, y2 in zip(uly_raw, lry_raw))
    lry = max(min(y1, y2) for y1, y2 in zip(uly_raw, lry_raw))

    # Final ordering for GDAL: [ulx, uly, lrx, lry] where ulx < lrx and uly > lry
    # Fix: enforce correct order for GDAL projWin
    if ulx > lrx:
        ulx, lrx = lrx, ulx
    if uly < lry:
        uly, lry = lry, uly

    return [ulx, uly, lrx, lry]




def clip_hyp3_products_to_common_overlap(data_dir: Path, overlap: list[float]) -> None:
    extensions = [
        "_unw_phase.tif", "_corr.tif", "_dem.tif",
        "_lv_theta.tif", "_lv_phi.tif", "_water_mask.tif"
    ]

    for ext in extensions:
        matched_files = list(data_dir.rglob(f"*{ext}"))
        if not matched_files:
            print(f"⚠️ No files found with extension {ext}")
            continue

        for file in matched_files:
            dst_file = file.with_name(file.stem + "_clipped.tif")
            if dst_file.exists():
                print(f"✅ Skipping {file.name}, clipped version exists.")
                continue

            try:
                print(f"🔧 Clipping {file.name} to {dst_file.name}")
                result = gdal.Translate(
                    destName=str(dst_file),
                    srcDS=str(file),
                    projWin=overlap,
                    format="GTiff"
                )
                if result is None:
                    print(f"⚠️ Failed to clip {file}")
            except RuntimeError as e:
                print(f"❌ Error clipping {file}: {e}")


def create_mintpy_config(data_dir: Path, work_dir: Path) -> Path:
    """Create a MintPy configuration file in the work_dir, pointing to data_dir files."""
    
    mintpy_config = work_dir / 'mintpy_config.txt'
    
    config_content = f"""mintpy.load.processor        = hyp3
##---------interferogram datasets
mintpy.load.unwFile          = {data_dir}/*/*_unw_phase_clipped.tif
mintpy.load.corFile          = {data_dir}/*/*_corr_clipped.tif
##---------geometry datasets:
mintpy.load.demFile          = {data_dir}/*/*_dem_clipped.tif
mintpy.load.incAngleFile     = {data_dir}/*/*_lv_theta_clipped.tif
mintpy.load.azAngleFile      = {data_dir}/*/*_lv_phi_clipped.tif
mintpy.load.waterMaskFile    = {data_dir}/*/*_water_mask_clipped.tif
# mintpy.troposphericDelay.method = no
mintpy.network.excludeNan    = yes
"""

    mintpy_config.write_text(config_content)
    print(f"✅ MintPy config written to {mintpy_config}")
    return mintpy_config


def run_mintpy(work_dir: Path, config_file: Path) -> None:
    """Run MintPy time-series analysis."""
    command = ["smallbaselineApp.py", "--dir", str(work_dir), str(config_file)]
    print(f"Running MintPy: {' '.join(command)}")
    subprocess.run(command, check=True)


def main():
    parser = argparse.ArgumentParser(description="MintPy time-series analysis on GeoTIFF files.")
    parser.add_argument("--data_dir", required=True, help="Directory containing unzipped GeoTIFF files")
    parser.add_argument("--work_dir", required=True, help="Output directory for time-series analysis")
    parser.add_argument("--config_file", required=False, help="Optional: custom MintPy configuration file")

    args = parser.parse_args()

    data_dir = Path(args.data_dir)
    work_dir = Path(args.work_dir)
    config_file = Path(args.config_file) if args.config_file else work_dir / "mintpy_config_auto.txt"

    # Ensure output directory exists
    work_dir.mkdir(parents=True, exist_ok=True)

    # Step 1: Find DEMs and get overlap
    files = list(data_dir.glob('*/*_dem.tif'))
    if not files:
        print("❌ No DEM files found.")
        return

    overlap = get_common_overlap(files)
    print(f"✅ Common overlap area: {overlap}")

    # Step 2: Clip products
    clip_hyp3_products_to_common_overlap(data_dir, overlap)

    # Step 3: Create MintPy config if not provided
    if not args.config_file:
        create_mintpy_config(data_dir, work_dir)

    # Step 4: Run MintPy
    run_mintpy(work_dir, config_file)



if __name__ == "__main__":
    main()
