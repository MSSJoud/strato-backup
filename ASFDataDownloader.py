#!/usr/bin/env python3
"""
ASF Data Downloader and Tiling Utility

Description:
------------
This Python script divides a geographic area into tiles based on a specified percentage of the entire area 
and downloads Sentinel-1 SAR data from the Alaska Satellite Facility (ASF) for each tile. The granules are 
organized by year, orbit direction (ascending/descending), and path number in a structured directory format. 
The script also supports filtering by latitude and longitude range to focus on specific sub-areas.

Features:
---------
1. **Tile Creation**: Divides the input area (based on the latitude and longitude bounds of granules) into 
   smaller tiles based on a specified percentage of the total area.
2. **Tile Filtering**: Selects tiles based on user-specified latitude/longitude bounds.
3. **ASF Granule Download**: Retrieves data for each tile based on ASF metadata, and organizes files by year, 
   orbit direction, and path number in the specified output directory.
4. **User-Specified Filtering**: Supports filtering by year, orbit direction, path number, and geographic bounds.

Directory Structure:
--------------------
The downloaded files are organized in a hierarchical directory structure:

    output_dir/
    ├── tile_1/
    │   ├── 2020/
    │   │   ├── ascending/
    │   │   │   ├── path_35/
    │   │   │   │   ├── <granule_1>.zip
    │   │   │   │   ├── ...
    │   │   ├── descending/
    │   │   │   ├── path_225/
    │   │   │   │   ├── <granule_1>.zip
    │   │   │   │   ├── ...
        │   ├── ...
    ├── tile_2/
    │   ├── ...

Usage:
------
```bash
python ASFDataDownloader.py --input_csv path/to/granules.csv --tile_percentage 5 --output_dir path/to/ucloud \
                            --lat_min 10 --lat_max 15 --lon_min 20 --lon_max 25 --year 2020 --orbit ASCENDING
"""


import os
import argparse
import asf_search as asf
import pandas as pd
from pathlib import Path
from GeoTileMapper import calculate_area_bounds, generate_tiles, select_granules_for_tile

# Import configuration for ASF authentication
from credentials import ASFUsr, ASFPwd


class ASFDataDownloader:
    def __init__(self, csv_file, output_dir):
        self.granules = pd.read_csv(csv_file, parse_dates=['Acquisition Date'])
        self.output_dir = Path(output_dir)
        self.session = self.authenticate_asf()

    def authenticate_asf(self):
        """Authenticate with ASF using credentials from the config file."""
        session = asf.ASFSession().auth_with_creds(ASFUsr, ASFPwd)
        return session
    
    def download_granules(self, granules, tile_name=None):
        """Download granules and organize them into directories."""
        for _, row in granules.iterrows():
            # Define orbit and path directories
            orbit_dir = self.output_dir / (tile_name if tile_name else "all_data") / row['Ascending or Descending?'].lower()
            path_dir = orbit_dir / f"path_{row['Path Number']}"

            # Handle conflicting files that may block directory creation
            if path_dir.exists() and not path_dir.is_dir():
                print(f"Conflicting file found at {path_dir}. Removing it to create directory.")
                path_dir.unlink()  # Remove the file

            # Create the path directory if it does not exist
            path_dir.mkdir(parents=True, exist_ok=True)

            # Construct the file path
            filename = row['URL'].split('/')[-1]
            filepath = path_dir / filename

            # Skip if the file already exists
            if filepath.exists():
                print(f"{filename} already exists. Skipping.")
                continue

            # Attempt to download the file
            try:
                asf.download_url(row['URL'], session=self.session, path=str(filepath.parent))
                print(f"Downloaded {filename} to {filepath}")
            except Exception as e:
                print(f"Failed to download {filename}: {e}")


    def execute(self, tile_percentage=None, lat_min=None, lat_max=None, lon_min=None, lon_max=None, year=None, orbit=None, path=None):
        if tile_percentage:
            area_bounds = calculate_area_bounds(self.granules)
            tiles = generate_tiles(area_bounds, tile_percentage)

            # Optional filtering by lat/lon range
            if lat_min and lat_max and lon_min and lon_max:
                tiles = self.filter_tiles_by_lat_lon(tiles, lat_min, lat_max, lon_min, lon_max)

            for i, tile in enumerate(tiles, start=1):
                tile_name = f"tile_{i}"
                tile_granules = select_granules_for_tile(self.granules, tile)
                self.download_granules(tile_granules, tile_name)
        else:
            # No tiling, download all data
            filtered_granules = self.granules
            if year:
                filtered_granules = filtered_granules[filtered_granules['Acquisition Date'].dt.year == year]
            if orbit:
                filtered_granules = filtered_granules[filtered_granules['Ascending or Descending?'] == orbit]
            if path:
                filtered_granules = filtered_granules[filtered_granules['Path Number'] == path]
            self.download_granules(filtered_granules)


def main():
    parser = argparse.ArgumentParser(description="ASF Data Downloader")
    parser.add_argument('--input_csv', required=True, help="Path to the input CSV file.")
    parser.add_argument('--output_dir', required=True, help="Output directory for downloaded data.")
    parser.add_argument('--tile_percentage', type=float, help="Tile size as a percentage of the area (optional).")
    parser.add_argument('--year', type=int, help="Filter by year (optional).")
    parser.add_argument('--orbit', choices=['ASCENDING', 'DESCENDING'], help="Filter by orbit (optional).")
    parser.add_argument('--path', type=int, help="Filter by path number (optional).")
    parser.add_argument('--lat_min', type=float, help="Minimum latitude for filtering (optional).")
    parser.add_argument('--lat_max', type=float, help="Maximum latitude for filtering (optional).")
    parser.add_argument('--lon_min', type=float, help="Minimum longitude for filtering (optional).")
    parser.add_argument('--lon_max', type=float, help="Maximum longitude for filtering (optional).")
    args = parser.parse_args()

    downloader = ASFDataDownloader(args.input_csv, args.output_dir)
    downloader.execute(
        tile_percentage=args.tile_percentage,
        lat_min=args.lat_min,
        lat_max=args.lat_max,
        lon_min=args.lon_min,
        lon_max=args.lon_max,
        year=args.year,
        orbit=args.orbit,
        path=args.path
    )

if __name__ == "__main__":
    main()
