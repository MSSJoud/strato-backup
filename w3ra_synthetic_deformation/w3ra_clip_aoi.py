import numpy as np
import xarray as xr
import geopandas as gpd
from shapely.vectorized import contains

def clip_w3ra_to_aoi(
    nc_in,
    polygon_file,
    nc_out,
    var_names=None,
    lat_name="lat",
    lon_name="lon",
):
    """
    Clip global W3RA NetCDF to an area of interest defined by a polygon.

    Parameters
    ----------
    nc_in : str
        Path to global W3RA NetCDF file.
    polygon_file : str
        Path to polygon file (Shapefile, GeoJSON, etc.).
    nc_out : str
        Output NetCDF for clipped subset.
    var_names : list of str or None
        Names of variables to keep. If None, keep all data variables.
    lat_name, lon_name : str
        Names of latitude and longitude coordinates in the NetCDF.

    Returns
    -------
    ds_clip : xarray.Dataset
        The clipped dataset (also written to disk).
    """
    # Open dataset
    ds = xr.open_dataset(nc_in)

    # Select variables
    if var_names is None:
        data_vars = list(ds.data_vars)
    else:
        data_vars = var_names
    ds = ds[data_vars]

    # Read polygon
    gdf = gpd.read_file(polygon_file)
    if gdf.crs is None:
        # assume lat/lon if not set
        gdf = gdf.set_crs("EPSG:4326")
    else:
        gdf = gdf.to_crs("EPSG:4326")
    poly = gdf.unary_union  # single geometry

    # Lat/lon grid
    lat = ds[lat_name].values
    lon = ds[lon_name].values
    lon2d, lat2d = np.meshgrid(lon, lat)

    # Boolean mask inside polygon
    mask = contains(poly, lon2d, lat2d)  # shape (nlat, nlon)

    # First reduce to bounding box to save memory
    idx_lat = np.any(mask, axis=1)
    idx_lon = np.any(mask, axis=0)

    ds_bb = ds.isel({lat_name: idx_lat, lon_name: idx_lon})
    mask_bb = mask[np.ix_(idx_lat, idx_lon)]

    # Apply mask (cells outside polygon -> NaN)
    ds_clip = ds_bb.where(mask_bb)

    # Write out
    ds_clip.to_netcdf(nc_out)
    print(f"AOI-clipped W3RA written to {nc_out}")
    return ds_clip
