import os
import subprocess

# File paths
ts_file = '/home/ubuntu/data_AOI-3/time_series_output/timeseries_ERA5.h5'
temporal_coherence_file = '/home/ubuntu/data_AOI-3/time_series_output/temporalCoherence.h5'
avg_spatial_coherence_file = '/home/ubuntu/data_AOI-3/time_series_output/avgSpatialCoh.h5'
mask_file = '/home/ubuntu/data_AOI-3/time_series_output/maskTempCoh.h5'
geom_file = '/home/ubuntu/data_AOI-3/time_series_output/inputs/geometryGeo.h5'
output_he5 = '/home/ubuntu/data_AOI-3/time_series_output/timeseries_ERA5.h5'

# Build the command
command = [
    "save_hdfeos5.py",
    ts_file,
    "--tc", temporal_coherence_file,
    "--asc", avg_spatial_coherence_file,
    "-m", mask_file,
    "-g", geom_file,
    "-o", output_he5
]

# Run the command
print(f"Running command: {' '.join(command)}")
result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

# Check for errors
if result.returncode == 0:
    print("Successfully saved time-series as HDF-EOS5.")
else:
    print("Error occurred:")
    print(result.stderr.decode())
