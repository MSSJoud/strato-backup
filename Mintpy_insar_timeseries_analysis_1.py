# Set up the working directory and unzip the data
from pathlib import Path
import hyp3_sdk as sdk
import zipfile
import os
import shutil

# Define paths
project_name = 'time_series_analysis'
work_dir = Path('/media/mehdi/Elements/InSAR/NB/AOI-1/Interferograms-Hyp3-Vertex')
data_dir = work_dir / 'data'

# Create the data directory if it doesn't exist
data_dir.mkdir(parents=True, exist_ok=True)

# Unzip the interferograms using hyp3_sdk
insar_products = []  # List to store product paths

# Add your zipped files here
for zip_file in work_dir.glob('*.zip'):
    insar_products.append(zip_file)

# Extract using sdk ##
# insar_products = [sdk.util.extract_zipped_product(ii) for ii in insar_products]
# for product in insar_products:
#     for item in product.iterdir():
#         shutil.move(str(item), data_dir)
# for zip_file in insar_products:
#     sdk.util.extract_zipped_product(zip_file, data_dir)

# # Unzip the interferograms
# for zip_file in work_dir.glob('*.zip'):
#     with zipfile.ZipFile(zip_file, 'r') as zip_ref:
#         zip_ref.extractall(data_dir)


# Clip the interferograms to their common overlap
from osgeo import gdal
from typing import List, Union

def get_common_overlap(file_list: List[Union[str, Path]]) -> List[float]:
    """Get the common overlap of  a list of GeoTIFF files
    Arg:
        file_list: a list of GeoTIFF files
    
    Returns:
         [ulx, uly, lrx, lry], the upper-left x, upper-left y, lower-right x, and lower-right y
         corner coordinates of the common overlap
    """

    corners = [gdal.Info(str(dem), format='json')['cornerCoordinates'] for dem in file_list]
    ulx = max(corner['upperLeft'][0] for corner in corners)
    uly = min(corner['upperLeft'][1] for corner in corners)
    lrx = min(corner['lowerRight'][0] for corner in corners)
    lry = max(corner['lowerRight'][1] for corner in corners)
    return [ulx, uly, lrx, lry]

# Print the directory structure to verify file locations
for root, dirs, files in os.walk(data_dir):
    level = root.replace(str(data_dir), '').count(os.sep)
    indent = ' ' * 4 * (level)
    print('{}{}/'.format(indent, os.path.basename(root)))
    sub_indent = ' ' * 4 * (level + 1)
    for f in files:
        print('{}{}'.format(sub_indent, f))

# Find the DEM files
# files = list(data_dir.rglob('*_dem.tif'))
#files = list(data_dir.glob('*/*_dem.tif'))
files = list(work_dir.glob('*/*_dem.tif'))

overlap = get_common_overlap(files)

def clip_hyp3_products_to_common_overlap(data_dir: Union[str, Path], overlap: List[float]) -> None:
    """Clip all GeoTIFF files to their common overlap
    
    Args:
        data_dir:
            directory containing the GeoTIFF files to clip
        overlap:
            a list of the upper-left x, upper-left y, lower-right-x, and lower-tight y
            corner coordinates of the common overlap
    Returns: None
    """
    files_for_mintpy = ['_water_mask.tif', '_corr.tif', '_unw_phase.tif', '_dem.tif', '_lv_theta.tif', '_lv_phi.tif']
    for extension in files_for_mintpy:
        for file in data_dir.rglob(f'*{extension}'):
            dst_file = file.parent / f'{file.stem}_clipped{file.suffix}'
            gdal.Translate(destName=str(dst_file), srcDS=str(file), projWin=overlap)

# clip_hyp3_products_to_common_overlap(work_dir, overlap)


# Create the MintPy configuration file
mintpy_config = work_dir / 'mintpy_config.txt'
mintpy_config.write_text(
f"""
mintpy.load.processor        = hyp3
##---------interferogram datasets
mintpy.load.unwFile          = {work_dir}/*/*_unw_phase_clipped.tif
mintpy.load.corFile          = {work_dir}/*/*_corr_clipped.tif
##---------geometry datasets:
mintpy.load.demFile          = {work_dir}/*/*_dem_clipped.tif
mintpy.load.incAngleFile     = {work_dir}/*/*_lv_theta_clipped.tif
mintpy.load.azAngleFile      = {work_dir}/*/*_lv_phi_clipped.tif
mintpy.load.waterMaskFile    = {work_dir}/*/*_water_mask_clipped.tif
# mintpy.troposphericDelay.method = no
"""
)
# Run MintPy for time-series analysis
# import os

# os.system(f'smallbaselineApp.py --dir {work_dir} {mintpy_config}')

# # Visualize the results
# from mintpy.cli import view, tsview

# get_ipython().run_line_magic('matplotlib', 'widget')

# # View velocity
# view.main([f'{work_dir}/velocity.h5'])

# # View time series
# tsview.main([f'{work_dir}/timeseries.h5'])


import subprocess

# Run MintPy to visualize velocity
subprocess.run(['smallbaselineApp.py', '--dir', str(work_dir), str(mintpy_config)])

# For viewing results, you may need to adapt this part depending on your setup
import mintpy.cli.view as view
import mintpy.cli.tsview as tsview

# view.main([f'{work_dir}/velocity.h5'])
tsview.main([f'{work_dir}/timeseries.h5'])

import h5py

# Load the HDF5 file
with h5py.File(f'{work_dir}/timeseries.h5','r') as f:
    # Print all root level object names (aka keys)
    print("Keys:  ", list(f.keys()))

    # Access a specific dataset
    dataset = f[''][:] 
    print(dataset) 
