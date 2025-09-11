import os
import numpy as np
from mintpy.utils import readfile, utils as ut
import matplotlib.pyplot as plt


# File paths
ts_file = '/home/ubuntu/data_AOI-3/time_series_output/timeseries_ERA5.h5'
geom_file = '/home/ubuntu/data_AOI-3/time_series_output/inputs/geometryGeo.h5'
mask_file = '/home/ubuntu/data_AOI-3/time_series_output/maskTempCoh.h5'
out_file = '/home/ubuntu/data_AOI-3/time_series_output/timeseries_data.csv'

# Read time-series metadata and attributes

dis, atr = readfile.read(ts_file, datasetName=date2)
dis -= readfile.read(ts_file, datasetName=date1)[0]

# Read geometry data
lat, lon = ut.get_lat_lon(atr)
inc_angle = readfile.read(geom_file, datasetName='incidenceAngle')[0] * np.pi / 180.
az_angle = readfile.read(geom_file, datasetName='azimuthAngle')[0] * np.pi / 180.

# Apply mask
mask = readfile.read(mask_file)[0]
mask *= ~np.isnan(inc_angle)
dis[mask == 0] = np.nan
lat[mask == 0] = np.nan
lon[mask == 0] = np.nan
inc_angle[mask == 0] = np.nan
az_angle[mask == 0] = np.nan

# Calculate unit vectors
ve = np.sin(inc_angle) * np.sin(az_angle) * -1
vn = np.sin(inc_angle) * np.cos(az_angle)
vu = np.cos(inc_angle)

# Prepare data for output
header = 'latitude,longitude,displacement[m],Vz,Vn,Ve'
data = np.column_stack((lat[mask].flatten(), lon[mask].flatten(), dis[mask].flatten(), vu[mask].flatten(), vn[mask].flatten(), ve[mask].flatten()))

# Save to CSV
np.savetxt(out_file, data, header=header, delimiter=',', fmt='%10.6f')
print(f"Time-series data saved to: {out_file}")
