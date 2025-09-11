import subprocess
import argparse
import numpy as np
import xarray as xr

def get_variable_list(nc_file, base_var, start_year, end_year):
    """
    Extracts unique year-specific variables for a given base variable within a time range.

    Args:
        nc_file (str): Path to NetCDF file.
        base_var (str): Base variable name (e.g., 'Sg_EU').
        start_year (int): Start year for filtering.
        end_year (int): End year for filtering.

    Returns:
        list: List of variable names with years (e.g., ['Sg_EU_2010', 'Sg_EU_2011', ...]).
    """
    command = f"ncdump -h {nc_file} | grep {base_var} | awk '{{print $1}}' | grep -o '{base_var}_[0-9]*'"
    result = subprocess.run(command, shell=True, capture_output=True, text=True, check=True)
    all_variables = result.stdout.strip().split("\n") if result.stdout.strip() else []

    return sorted(set(var for var in all_variables if start_year <= int(var.split("_")[-1]) <= end_year))

def extract_variable_data(nc_file, var_list, start_year, end_year):
    """
    Extracts and concatenates selected variables from NetCDF into an xarray dataset.

    Args:
        nc_file (str): Path to NetCDF file.
        var_list (list): List of variable names.
        start_year (int): Start year.
        end_year (int): End year.

    Returns:
        xarray.Dataset: Dataset with unified time dimension (time, lat, lon).
    """
    ds = xr.open_dataset(nc_file)
    datasets = []  # Store yearly datasets

    for year in range(start_year, end_year + 1):
        var_name = f"Sg_EU_{year}"
        time_dim = f"time_{year}"

        if var_name in ds and time_dim in ds.dims:
            print(f"\u2705 Processing {var_name} with time dimension {time_dim}")
            ds_year = ds[var_name].rename({time_dim: "time"})  # Standardize time dimension
            datasets.append(ds_year)
        else:
            print(f"\u26A0 Warning: {var_name} or {time_dim} not found. Skipping...")

    if not datasets:
        raise ValueError("No valid datasets found for selected years.")
    print("\u25B6 Concatenating datasets along time axis...")

    # Concatenate all datasets along time axis
    merged_ds = xr.concat(datasets, dim="time")

    return merged_ds

def compute_mean_and_anomalies(ds):
    """
    Computes mean values and anomalies (time series - mean) for each point.

    Args:
        ds (xarray.Dataset): Dataset containing time-series data.

    Returns:
        tuple: (mean dataset, anomaly dataset)
    """
    print("\u25B6 Computing mean across time...")
    mean_values = ds.mean(dim="time", keep_attrs=True)  # Compute mean across time
    anomalies = ds - mean_values  # Compute anomalies (timeseries - mean)
    return mean_values, anomalies

def save_netcdf(output_file, ds, description):
    """
    Saves an xarray dataset to NetCDF.

    Args:
        output_file (str): Path to output NetCDF file.
        ds (xarray.Dataset): Dataset to save.
        description (str): Description of the dataset for metadata.
    """
    print(f"\u25B6 Saving {description} to file: {output_file}")
    ds.attrs["Description"] = description
    ds.to_netcdf(output_file, format="NETCDF4")
    print("\u2705 File saved successfully.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Extract mean and anomalies from NetCDF time-series data.")
    parser.add_argument("--input", required=True, help="Path to the NetCDF file")
    parser.add_argument("--variable", required=True, help="Base variable name (e.g., Sg_EU, Sd_EU, Ss_EU, etc.)")
    parser.add_argument("--start_year", type=int, required=True, help="Start year for extraction")
    parser.add_argument("--end_year", type=int, required=True, help="End year for extraction")

    args = parser.parse_args()
    nc_file = args.input
    base_var = args.variable
    start_year = args.start_year
    end_year = args.end_year

    # Get variable list
    print("\u25B6 Retrieving variable list...")
    variable_list = get_variable_list(nc_file, base_var, start_year, end_year)
    if not variable_list:
        raise ValueError(f"No variables found for {base_var} between {start_year} and {end_year}. Check the NetCDF file structure.")

    # Extract dataset
    dataset = extract_variable_data(nc_file, variable_list, start_year, end_year)

    # Compute mean and anomalies
    mean_ds, anomaly_ds = compute_mean_and_anomalies(dataset)

    # Save outputs
    mean_output_file = nc_file.replace(".nc", f"_{base_var}_{start_year}_{end_year}_mean.nc")
    anomaly_output_file = nc_file.replace(".nc", f"_{base_var}_{start_year}_{end_year}_anomaly.nc")

    save_netcdf(mean_output_file, mean_ds, f"Mean values for {base_var} from {start_year} to {end_year}")
    save_netcdf(anomaly_output_file, anomaly_ds, f"Anomalies for {base_var} from {start_year} to {end_year} (time series - mean)")
    print("\u2705 Processing complete!")
