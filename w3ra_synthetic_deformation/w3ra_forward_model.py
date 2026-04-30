def w3ra_ds_to_forward_inputs(
    ds_clip,
    var_map,
    lat_name="lat",
    lon_name="lon",
):
    """
    Convert clipped W3RA Dataset to forward-model inputs.

    Parameters
    ----------
    ds_clip : xarray.Dataset
        Output from clip_w3ra_to_aoi, with dims (time, lat, lon).
    var_map : dict
        Mapping from logical layer names to variable names in ds_clip.
        Example:
        {
          "S0": "S0",   # topsoil
          "Ss": "Ss",
          "Sd": "Sd",
          "Sg": "Sg",
          "Sr": "Sr",
        }
    lat_name, lon_name : str
        Names of coordinate variables.

    Returns
    -------
    x, y : ndarray, shape (N,)
        Projected coordinates (here just lon/lat or transformed later).
    cell_area : float
        Approximate cell area [m^2] (assumed constant here).
    dS_layers : dict
        Mapping layer_name -> ndarray of shape (N, T) with storage anomalies [m].
    """
    import numpy as np

    # Coordinates
    lat = ds_clip[lat_name].values
    lon = ds_clip[lon_name].values
    lon2d, lat2d = np.meshgrid(lon, lat)  # (nlat, nlon)

    # Use the first variable to define "valid" cells (inside AOI)
    any_var_name = next(iter(var_map.values()))
    data0 = ds_clip[any_var_name].isel(time=0).values  # (nlat, nlon)
    valid_mask = np.isfinite(data0)

    # Flatten
    x_flat = lon2d[valid_mask]
    y_flat = lat2d[valid_mask]

    # Approximate cell area (10 km grid, spherical approx)
    # You can replace this with exact values if you have them.
    # Here: compute mean spacing and convert degrees to meters roughly.
    # (Better: reproject to UTM before computing x,y!)
    nlat, nlon = lat.size, lon.size
    # Simple hack: assume 10 km x 10 km
    cell_area = 10_000.0 * 10_000.0

    # Build dS_layers
    T = ds_clip.dims["time"]
    dS_layers = {}
    for logical_name, var_name in var_map.items():
        arr = ds_clip[var_name].values  # (T, nlat, nlon) or (time,lat,lon)
        if arr.shape[0] == T:
            arr = arr  # time is first axis
        else:
            # adapt if order different
            arr = np.moveaxis(arr, arr.shape.index(T), 0)
        # reshape to (T, N)
        arr2 = arr[:, valid_mask]           # (T, N)
        # anomalies (remove time-mean)
        arr2 = arr2 - np.nanmean(arr2, axis=0, keepdims=True)
        dS_layers[logical_name] = arr2.T    # (N, T)

    return x_flat, y_flat, cell_area, dS_layers
