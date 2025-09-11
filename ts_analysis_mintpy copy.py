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


def get_common_overlap(file_list: List[Union[str, Path]]) -> List[float]:
    """Get the common overlap of GeoTIFF files."""
    corners = [gdal.Info(str(file), format='json')['cornerCoordinates'] for file in file_list]
    ulx = max(corner['upperLeft'][0] for corner in corners)
    uly = min(corner['upperLeft'][1] for corner in corners)
    lrx = min(corner['lowerRight'][0] for corner in corners)
    lry = max(corner['lowerRight'][1] for corner in corners)
    return [ulx, uly, lrx, lry]


def clip_hyp3_products_to_common_overlap(data_dir: Union[str, Path], overlap: List[float]) -> None:
    """Clip GeoTIFF files to the common overlap."""
    data_dir = Path(data_dir)
    files_for_mintpy = ['_water_mask.tif', '_corr.tif', '_unw_phase.tif', '_dem.tif', '_lv_theta.tif', '_lv_phi.tif']

    for extension in files_for_mintpy:
        for file in data_dir.rglob(f'*{extension}'):
            dst_file = file.parent / f'{file.stem}_clipped{file.suffix}'
            gdal.Translate(destName=str(dst_file), srcDS=str(file), projWin=overlap)
            print(f"Clipped {file} to {dst_file}")


def create_mintpy_config(data_dir: Path, config_file: Path) -> None:
    """Create a MintPy configuration file."""
    config_content = f"""
mintpy.load.processor        = hyp3
##---------interferogram datasets
mintpy.load.unwFile          = {data_dir}/*/*_unw_phase_clipped.tif
mintpy.load.corFile          = {data_dir}/*/*_corr_clipped.tif
##---------geometry datasets:
mintpy.load.demFile          = {data_dir}/*/*_dem_clipped.tif
mintpy.load.incAngleFile     = {data_dir}/*/*_lv_theta_clipped.tif
mintpy.load.azAngleFile      = {data_dir}/*/*_lv_phi_clipped.tif
mintpy.load.waterMaskFile    = {data_dir}/*/*_water_mask_clipped.tif
# mintpy.troposphericDelay.method = no
"""
    config_file.write_text(config_content)
    print(f"MintPy configuration file written to {config_file}")


def run_mintpy(work_dir: Path, config_file: Path) -> None:
    """Run MintPy time-series analysis."""
    command = ["smallbaselineApp.py", "--dir", str(work_dir), str(config_file)]
    print(f"Running MintPy: {' '.join(command)}")
    subprocess.run(command, check=True)


def main():
    parser = argparse.ArgumentParser(description="MintPy time-series analysis on GeoTIFF files.")
    parser.add_argument("--data_dir", required=True, help="Directory containing unzipped GeoTIFF files")
    parser.add_argument("--work_dir", required=True, help="Output directory for time-series analysis")
    parser.add_argument("--config_file", required=True, help="Path to save the MintPy configuration file")

    args = parser.parse_args()

    data_dir = Path(args.data_dir)
    work_dir = Path(args.work_dir)
    config_file = Path(args.config_file)

    # Ensure directories exist
    work_dir.mkdir(parents=True, exist_ok=True)

    # Step 1: Find common overlap
    files = list(data_dir.glob('*/*_dem.tif'))
    if not files:
        print("No DEM files found in the data directory.")
        return

    overlap = get_common_overlap(files)
    print(f"Common overlap: {overlap}")

    # Step 2: Clip files to common overlap
    clip_hyp3_products_to_common_overlap(data_dir, overlap)

    # Step 3: Create MintPy configuration
    create_mintpy_config(data_dir, config_file)

    # Step 4: Run MintPy
    run_mintpy(work_dir, config_file)


if __name__ == "__main__":
    main()
