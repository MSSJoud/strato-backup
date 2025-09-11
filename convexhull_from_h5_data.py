import h5py
import numpy as np
import geopandas as gpd
from shapely.geometry import Polygon, MultiPoint

# Input HDF5 file (modify as needed)
h5_file = "/home/ubuntu/data_AOI-3/time_series_output/timeseries_ERA5.h5"
output_geojson = "/home/ubuntu/data_AOI-3/time_series_output/boundary_convexhull.geojson"

# Read lat/lon from HDF5 dataset
with h5py.File(h5_file, "r") as f:
    metadata = dict(f.attrs)

    # Extract bounding box from metadata
    lat_ref1, lat_ref2, lat_ref3, lat_ref4 = metadata["LAT_REF1"], metadata["LAT_REF2"], metadata["LAT_REF3"], metadata["LAT_REF4"]
    lon_ref1, lon_ref2, lon_ref3, lon_ref4 = metadata["LON_REF1"], metadata["LON_REF2"], metadata["LON_REF3"], metadata["LON_REF4"]

    # Read the actual lat/lon datasets if available
    try:
        lat_data = f["/HDFEOS/GRIDS/timeseries/geometry/latitude"][:]
        lon_data = f["/HDFEOS/GRIDS/timeseries/geometry/longitude"][:]
    except KeyError:
        print("Lat/Lon data not found in HDF5 file, using only metadata references.")
        lat_data = np.array([lat_ref1, lat_ref2, lat_ref3, lat_ref4])
        lon_data = np.array([lon_ref1, lon_ref2, lon_ref3, lon_ref4])

# Create Bounding Box Polygon (from metadata)
bounding_box = Polygon([(lon_ref1, lat_ref1), (lon_ref2, lat_ref2), (lon_ref4, lat_ref4), (lon_ref3, lat_ref3)])

# Create Convex Hull from actual lat/lon points
points = MultiPoint(list(zip(lon_data.flatten(), lat_data.flatten())))
convex_hull = points.convex_hull

# Convert to GeoDataFrame
gdf = gpd.GeoDataFrame({"name": ["Bounding Box", "Convex Hull"]}, geometry=[bounding_box, convex_hull], crs="EPSG:32632")

# Reproject to WGS84 (EPSG:4326) if needed
gdf = gdf.to_crs("EPSG:4326")

# Save as GeoJSON
gdf.to_file(output_geojson, driver="GeoJSON")

import scipy.io
import netCDF4 as nc
import numpy as np
import os

def convert_w3ra_mat_to_netcdf(input_dir, latlon_file, output_file):
    """
    Convert multiple W3RA .mat files into a single NetCDF file with separate layers for each year.

    Parameters:
        input_dir (str): Directory containing the .mat files.
        latlon_file (str): Path to the LatLon.mat file containing latitude and longitude grids.
        output_file (str): Path to save the combined NetCDF file.
    """
    # Load latitude and longitude from LatLon.mat
    latlon_data = scipy.io.loadmat(latlon_file, struct_as_record=False, squeeze_me=True)
    lat = np.array(latlon_data.get('lat_EU')).squeeze()
    lon = np.array(latlon_data.get('lon_EU')).squeeze()

    if lat is None or lon is None:
        raise ValueError(f"Latitude or Longitude variable missing in {latlon_file}. Available keys: {list(latlon_data.keys())}")

    # Get all .mat files and sort them by year
    mat_files = sorted([f for f in os.listdir(input_dir) if f.endswith(".mat") and "LatLon" not in f])
    
    # Extract years from filenames
    years = [int(f.split("_")[-1].split(".")[0]) for f in mat_files]  
    
    # Create NetCDF file
    with nc.Dataset(output_file, "w", format="NETCDF4") as ds:
        # Create dimensions
        ds.createDimension("lat", len(lat))
        ds.createDimension("lon", len(lon))

        # Create coordinate variables
        lat_var = ds.createVariable("lat", "f8", ("lat",))
        lon_var = ds.createVariable("lon", "f8", ("lon",))

        # Assign CF-compliant attributes
        lat_var.units = "degrees_north"
        lon_var.units = "degrees_east"

        # Assign coordinate values
        lat_var[:] = lat
        lon_var[:] = lon

        # Process each file and store each year's data in separate variables
        for idx, mat_file in enumerate(mat_files):
            year = years[idx]
            print(f"\nProcessing {year}: {mat_file}...")  # Debugging
            print("Loading .mat file...")

            # Load .mat file
            mat_data = scipy.io.loadmat(os.path.join(input_dir, mat_file), struct_as_record=False, squeeze_me=True)

            print("Available variables in .mat file:", list(mat_data.keys()))  # Debugging

            # Determine the number of days in the year
            days_in_year = 366 if year % 4 == 0 else 365
            
            # Create time dimension for each year
            ds.createDimension(f"time_{year}", days_in_year)
            time_var = ds.createVariable(f"time_{year}", "i4", (f"time_{year}",))
            time_var.units = f"days since {year}-01-01"
            time_var.calendar = "standard"
            time_var[:] = np.arange(1, days_in_year + 1)

            # Process each variable
            for var in mat_data.keys():
                if var.startswith('__'):  # Skip MATLAB metadata
                    continue
                
                data = mat_data[var]

                # Debugging: Check variable shape before processing
                print(f"Checking variable {var} - Expected shape: ({days_in_year}, 22, 24), Found: {data.shape}")

                if isinstance(data, np.ndarray) and data.shape == (days_in_year, 22, 24):  
                    var_name = f"{var}_{year}"  # Store each year as a separate layer

                    # Create variable for this year
                    data_var = ds.createVariable(var_name, "f4", (f"time_{year}", "lat", "lon"), zlib=True)
                    data_var.units = "mm"
                    data_var.long_name = f"{var} for {year}"
                    
                    # Assign data
                    data_var[:, :, :] = data
                else:
                    print(f"⚠️ WARNING: Skipping variable {var} due to shape mismatch")

    print(f"\n✅ Multi-year NetCDF saved at {output_file}")

# Example usage
if __name__ == "__main__":
    input_dir = "/home/ubuntu/data_AOI-3/w3ra_aoi_3/"
    latlon_file = "/home/ubuntu/data_AOI-3/w3ra_aoi_3/LatLon.mat"
    output_file = "/home/ubuntu/data_AOI-3/w3ra_aoi_3/netcdf/W3RA_2010_2024.nc"

    convert_w3ra_mat_to_netcdf(input_dir, latlon_file, output_file)
print(f"GeoJSON file saved: {output_geojson}")
