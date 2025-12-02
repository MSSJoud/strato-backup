import os
import glob
import zipfile
import re
import numpy as np
import matplotlib.pyplot as plt
import rasterio
import pandas as pd
from datetime import datetime

# Configuration
DATA_DIR = "/home/ubuntu/work/slc_stack_test_subset/data/slcs"
SUB_SWATH = "iw1"
POLARIZATION = "vv"

print(f"Looking for data in: {DATA_DIR}")

def get_slc_files(data_dir):
    slc_files = sorted(glob.glob(os.path.join(data_dir, "*.zip")))
    print(f"Found {len(slc_files)} SLC zip files.")
    return slc_files

def parse_date_from_filename(filename):
    # Example: S1A_IW_SLC__1SDV_20250310T113934_...
    match = re.search(r"(\d{8}T\d{6})", os.path.basename(filename))
    if match:
        return datetime.strptime(match.group(1), "%Y%m%dT%H%M%S")
    return None

slc_files = get_slc_files(DATA_DIR)
dates = [parse_date_from_filename(f) for f in slc_files]

df = pd.DataFrame({"filename": slc_files, "date": dates})
df = df.sort_values("date").reset_index(drop=True)
print(df.head())

def read_slc_amplitude(zip_path, sub_swath="iw1", polarization="vv", downsample_factor=10):
    """
    Reads a specific TIFF from the SLC zip and calculates mean amplitude.
    Uses rasterio to read from zip.
    """
    tiff_path = None
    try:
        with zipfile.ZipFile(zip_path, 'r') as z:
            for name in z.namelist():
                # Case insensitive check might be safer but S1 is usually consistent
                if f"measurement/s1" in name and sub_swath in name and polarization in name and name.endswith(".tiff"):
                    tiff_path = name
                    break
        
        if not tiff_path:
            print(f"Warning: Could not find {sub_swath} {polarization} in {os.path.basename(zip_path)}")
            return None
        
        # Read with rasterio
        full_path = f"zip://{zip_path}!{tiff_path}"
        
        with rasterio.open(full_path) as src:
            # Calculate new shape
            out_shape = (
                src.count,
                int(src.height / downsample_factor),
                int(src.width / downsample_factor)
            )
            
            data = src.read(
                out_shape=out_shape,
                resampling=rasterio.enums.Resampling.average
            )
            
            # S1 SLC is complex int16 usually
            if np.iscomplexobj(data):
                amplitude = np.abs(data)
            else:
                # If it's not complex, it might be read as 2 bands or just magnitude?
                # Usually rasterio handles complex types if GDAL supports it.
                # If it returns real, we assume it's amplitude or we take abs.
                amplitude = np.abs(data)
                
            return np.mean(amplitude)
            
    except Exception as e:
        print(f"Error reading {zip_path}: {e}")
        return None

# Process all files
amplitudes = []
valid_dates = []

print("Processing files...")
for idx, row in df.iterrows():
    print(f"Processing {idx+1}/{len(df)}: {os.path.basename(row['filename'])}")
    amp = read_slc_amplitude(row['filename'], SUB_SWATH, POLARIZATION)
    if amp is not None:
        amplitudes.append(amp)
        valid_dates.append(row['date'])
    else:
        print(f"Skipping {row['filename']}")

print(f"Processed {len(amplitudes)} files.")

# Plotting
plt.figure(figsize=(12, 6))
plt.plot(valid_dates, amplitudes, 'o-', label='Mean Amplitude')
plt.title(f"Sentinel-1 SLC Amplitude Time Series ({SUB_SWATH.upper()} {POLARIZATION.upper()})")
plt.xlabel("Date")
plt.ylabel("Mean Amplitude (DN)")
plt.grid(True)
plt.legend()
plt.tight_layout()
plt.savefig("slc_amplitude_timeseries.png")
print("Plot saved to slc_amplitude_timeseries.png")
