import netCDF4 as nc
import geopandas as gpd
import pandas as pd
from shapely.geometry import Point
import os
import argparse

def extract_netcdf_data(netcdf_file):
    """
    Extracts latitude, longitude, and time-series data from a NetCDF file.
    
    Parameters:
        netcdf_file (str): Path to the NetCDF file.
    
    Returns:
        list: List of dictionaries containing extracted data.
    """
    dataset = nc.Dataset(netcdf_file, "r")
    
    # Read lat/lon values
    latitudes = dataset.variables["lat"][:]
    longitudes = dataset.variables["lon"][:]
    
    # Identify available time-series variables
    data_vars = [var for var in dataset.variables if "time" in dataset.variables[var].dimensions]
    
    records = []
    for i, lat in enumerate(latitudes):
        for j, lon in enumerate(longitudes):
            geom = Point(lon, lat)
            record = {"geometry": geom, "latitude": lat, "longitude": lon}
            for var in data_vars:
                record[var] = dataset.variables[var][:, i, j].tolist()  # Store time series as a list
            records.append(record)
    
    return records

def save_as_shapefile(records, output_shp):
    """
    Saves extracted NetCDF data as a Shapefile.
    
    Parameters:
        records (list): List of dictionaries containing extracted data.
        output_shp (str): Path to save the shapefile.
    """
    gdf = gpd.GeoDataFrame(records, geometry="geometry", crs="EPSG:4326")
    os.makedirs(os.path.dirname(output_shp), exist_ok=True)
    gdf.to_file(output_shp)
    print(f"\u2705 Shapefile saved: {output_shp}")

def save_as_csv(records, output_csv):
    """
    Saves extracted NetCDF data as a CSV file.
    
    Parameters:
        records (list): List of dictionaries containing extracted data.
        output_csv (str): Path to save the CSV file.
    """
    df = pd.DataFrame(records)
    os.makedirs(os.path.dirname(output_csv), exist_ok=True)
    df.to_csv(output_csv, index=False)
    print(f"\u2705 CSV saved: {output_csv}")

def netcdf_to_geodata(netcdf_file, output_file, file_type="shp", verbose=False):
    """
    Converts NetCDF to either Shapefile or CSV.
    
    Parameters:
        netcdf_file (str): Path to the NetCDF file.
        output_file (str): Path to save the output file.
        file_type (str): Output format, either "shp" or "csv".
    """
    records = extract_netcdf_data(netcdf_file)
    
    if file_type == "shp":
        save_as_shapefile(records, output_file)
    elif file_type == "csv":
        save_as_csv(records, output_file)
    else:
        raise ValueError("Invalid file_type. Choose 'shp' or 'csv'.")
    
    if verbose:
        print(f"Processing NetCDF: {netcdf_file}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Convert NetCDF to Shapefile or CSV.")
    parser.add_argument("--input", required=True, help="Path to the NetCDF file")
    parser.add_argument("--output", required=True, help="Path to the output file")
    parser.add_argument("--type", choices=["shp", "csv"], required=True, help="Output format: shp or csv")
    parser.add_argument("--verbose", action="store_true", help="Enable verbose debugging output")
   
    args = parser.parse_args()
    
    netcdf_to_geodata(args.input, args.output, args.type)
