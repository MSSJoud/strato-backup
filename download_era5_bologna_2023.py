#!/usr/bin/env python3
"""
download_era5_bologna_2023.py

Download ERA5 weather model data for tropospheric correction of Bologna InSAR time series.

Requirements:
    pip install cdsapi

Setup:
    1. Register at https://cds.climate.copernicus.eu/#!/home
    2. Get your UID and API key from https://cds.climate.copernicus.eu/api-how-to
    3. Create ~/.cdsapirc with:
       url: https://cds.climate.copernicus.eu/api/v2
       key: YOUR_UID:YOUR_API_KEY

Usage:
    python3 download_era5_bologna_2023.py --output_dir /path/to/era5_data
"""

import argparse
import os
from pathlib import Path
from datetime import datetime
import cdsapi


# Bologna AOI bounds (with ~0.5 degree buffer for safety)
AOI_BOUNDS = {
    'north': 45.2,  # 44.7 + 0.5
    'south': 43.8,  # 44.3 - 0.5
    'west': 10.6,   # 11.1 - 0.5
    'east': 12.1    # 11.6 + 0.5
}

# Sentinel-1 acquisition dates for Bologna 2023 (31 dates)
ACQUISITION_DATES = [
    '2023-01-04', '2023-01-16', '2023-01-28',
    '2023-02-09', '2023-02-21',
    '2023-03-05', '2023-03-17', '2023-03-29',
    '2023-04-10', '2023-04-22',
    '2023-05-04', '2023-05-16', '2023-05-28',
    '2023-06-09', '2023-06-21',
    '2023-07-03', '2023-07-15', '2023-07-27',
    '2023-08-08', '2023-08-20',
    '2023-09-01', '2023-09-13', '2023-09-25',
    '2023-10-07', '2023-10-19', '2023-10-31',
    '2023-11-12', '2023-11-24',
    '2023-12-06', '2023-12-18', '2023-12-30'
]

# ERA5 variables needed for tropospheric delay calculation
ERA5_VARIABLES = [
    'geopotential',                    # Z - geopotential height
    'temperature',                     # T - temperature at pressure levels
    'relative_humidity',               # RH - relative humidity
]

# Pressure levels (hPa) - standard atmosphere levels
PRESSURE_LEVELS = [
    '1', '2', '3', '5', '7', '10', '20', '30', '50', '70',
    '100', '125', '150', '175', '200', '225', '250', '300',
    '350', '400', '450', '500', '550', '600', '650', '700',
    '750', '775', '800', '825', '850', '875', '900', '925',
    '950', '975', '1000'
]

# Time steps (UTC) - download all 6-hourly data, MintPy will interpolate
TIME_STEPS = ['00:00', '06:00', '12:00', '18:00']


def download_era5_for_date(date_str, output_dir, client):
    """
    Download ERA5 data for a specific date.
    
    Args:
        date_str: Date in YYYY-MM-DD format
        output_dir: Directory to save ERA5 files
        client: Initialized CDS API client
    """
    date_obj = datetime.strptime(date_str, '%Y-%m-%d')
    year = date_obj.strftime('%Y')
    month = date_obj.strftime('%m')
    day = date_obj.strftime('%d')
    
    output_file = output_dir / f'era5_bologna_{date_str}.nc'
    
    if output_file.exists():
        print(f"✓ Already exists: {output_file.name}")
        return True
    
    print(f"⬇️  Downloading ERA5 for {date_str}...")
    
    try:
        client.retrieve(
            'reanalysis-era5-pressure-levels',
            {
                'product_type': 'reanalysis',
                'variable': ERA5_VARIABLES,
                'pressure_level': PRESSURE_LEVELS,
                'year': year,
                'month': month,
                'day': day,
                'time': TIME_STEPS,
                'area': [
                    AOI_BOUNDS['north'],
                    AOI_BOUNDS['west'],
                    AOI_BOUNDS['south'],
                    AOI_BOUNDS['east']
                ],
                'format': 'netcdf',
            },
            str(output_file)
        )
        print(f"✅ Downloaded: {output_file.name}")
        return True
        
    except Exception as e:
        print(f"❌ Error downloading {date_str}: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(
        description='Download ERA5 weather data for Bologna InSAR tropospheric correction',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Download all dates
  python3 download_era5_bologna_2023.py --output_dir /mnt/data/sbas_vs_ps_test_bologna/era5
  
  # Download specific date range
  python3 download_era5_bologna_2023.py --output_dir ./era5_data --start_date 2023-01-04 --end_date 2023-03-31
  
Setup Required:
  1. Register at: https://cds.climate.copernicus.eu/
  2. Get API key from: https://cds.climate.copernicus.eu/api-how-to
  3. Create ~/.cdsapirc:
     url: https://cds.climate.copernicus.eu/api/v2
     key: YOUR_UID:YOUR_API_KEY
        """
    )
    
    parser.add_argument('--output_dir', required=True,
                        help='Output directory for ERA5 NetCDF files')
    parser.add_argument('--start_date', default=None,
                        help='Start date (YYYY-MM-DD), default: first acquisition')
    parser.add_argument('--end_date', default=None,
                        help='End date (YYYY-MM-DD), default: last acquisition')
    parser.add_argument('--force', action='store_true',
                        help='Re-download even if files exist')
    
    args = parser.parse_args()
    
    # Create output directory
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    print(f"📁 Output directory: {output_dir}")
    print(f"📍 AOI: Bologna ({AOI_BOUNDS['west']}°W to {AOI_BOUNDS['east']}°E, "
          f"{AOI_BOUNDS['south']}°S to {AOI_BOUNDS['north']}°N)")
    print()
    
    # Filter dates if requested
    dates_to_download = ACQUISITION_DATES.copy()
    if args.start_date:
        dates_to_download = [d for d in dates_to_download if d >= args.start_date]
    if args.end_date:
        dates_to_download = [d for d in dates_to_download if d <= args.end_date]
    
    print(f"📅 Total dates to download: {len(dates_to_download)}")
    print(f"   First: {dates_to_download[0]}")
    print(f"   Last:  {dates_to_download[-1]}")
    print()
    
    # Initialize CDS API client
    try:
        client = cdsapi.Client()
        print("✅ CDS API client initialized")
        print()
    except Exception as e:
        print(f"❌ Failed to initialize CDS API client: {e}")
        print()
        print("Setup instructions:")
        print("1. Register at: https://cds.climate.copernicus.eu/")
        print("2. Get your API key from: https://cds.climate.copernicus.eu/api-how-to")
        print("3. Create ~/.cdsapirc with:")
        print("   url: https://cds.climate.copernicus.eu/api/v2")
        print("   key: YOUR_UID:YOUR_API_KEY")
        return 1
    
    # Download data for each date
    print("━" * 80)
    success_count = 0
    failed_dates = []
    
    for i, date_str in enumerate(dates_to_download, 1):
        print(f"[{i}/{len(dates_to_download)}] {date_str}")
        
        if download_era5_for_date(date_str, output_dir, client):
            success_count += 1
        else:
            failed_dates.append(date_str)
        
        print()
    
    # Summary
    print("━" * 80)
    print(f"📊 DOWNLOAD SUMMARY")
    print(f"   Total dates:    {len(dates_to_download)}")
    print(f"   Successful:     {success_count} ✅")
    print(f"   Failed:         {len(failed_dates)} ❌")
    
    if failed_dates:
        print()
        print("Failed dates:")
        for date in failed_dates:
            print(f"  - {date}")
        return 1
    else:
        print()
        print("✅ All ERA5 data downloaded successfully!")
        print()
        print(f"📂 Files saved to: {output_dir}")
        print()
        print("Next steps:")
        print("1. Wait for ISCE2 processing to complete")
        print("2. Organize ISCE2 outputs for MintPy (Phase 4)")
        print("3. Run MintPy with ERA5 tropospheric correction (Phase 5)")
        print(f"   mintpy.weatherModel.weatherDir = {output_dir}")
        return 0


if __name__ == "__main__":
    exit(main())
