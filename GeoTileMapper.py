"""
GeoTileMapper

This module provides functionality to divide a geospatial area into tiles, select granules within each tile based on geographic bounds, and organize them for further processing.

Functions:
- `calculate_area_bounds(granules)`: Calculates the bounding box of the entire area based on granules.
- `generate_tiles(area_bounds, percentage)`: Divides the area into tiles based on a specified percentage.
- `select_granules_for_tile(granules, tile_bounds)`: Selects granules that fall within the boundaries of a given tile.

Usage:
    This module is intended to be used as part of a larger system for tiling geospatial data and retrieving data from ASF.

Requirements:
- Geopy
"""

from geopy.distance import geodesic
import pandas as pd
from typing import List, Tuple, Dict


def calculate_area_bounds(granules: pd.DataFrame) -> Tuple[float, float, float, float]:
    """Calculates the bounding box of the entire area based on granule data."""
    min_lat = granules['Near Start Lat'].min()
    max_lat = granules['Far End Lat'].max()
    min_lon = granules['Near Start Lon'].min()
    max_lon = granules['Far End Lon'].max()
    return min_lat, max_lat, min_lon, max_lon


def generate_tiles(area_bounds: Tuple[float, float, float, float], percentage: float) -> List[Dict[str, Tuple[float, float]]]:
    """
    Divides the area into tiles based on a specified percentage.
    Each tile's dimensions are approximately `percentage` of the full area.
    """
    min_lat, max_lat, min_lon, max_lon = area_bounds
    area_height_km = geodesic((min_lat, min_lon), (max_lat, min_lon)).km
    area_width_km = geodesic((min_lat, min_lon), (min_lat, max_lon)).km
    tile_height_km = area_height_km * (percentage / 100)
    tile_width_km = area_width_km * (percentage / 100)

    tiles = []
    lat = min_lat
    while lat < max_lat:
        lon = min_lon
        while lon < max_lon:
            tile_bounds = {
                'min_lat': lat,
                'max_lat': min(lat + (tile_height_km / area_height_km) * (max_lat - min_lat), max_lat),
                'min_lon': lon,
                'max_lon': min(lon + (tile_width_km / area_width_km) * (max_lon - min_lon), max_lon)
            }
            tiles.append(tile_bounds)
            lon = tile_bounds['max_lon']
        lat = tile_bounds['max_lat']
    return tiles


def select_granules_for_tile(granules: pd.DataFrame, tile_bounds: Dict[str, float]) -> pd.DataFrame:
    """Selects granules within the specified tile boundaries."""
    return granules[
        (granules['Near Start Lat'] >= tile_bounds['min_lat']) &
        (granules['Far End Lat'] <= tile_bounds['max_lat']) &
        (granules['Near Start Lon'] >= tile_bounds['min_lon']) &
        (granules['Far End Lon'] <= tile_bounds['max_lon'])
    ]
