import pandas as pd
from shapely.geometry import Polygon, Point
from shapely.ops import unary_union
from geopy.distance import geodesic
import math

# Constants
DEFAULT_PERCENTAGE = 5  # Default percentage if not provided

def load_granules(file_path):
    """Load granules data from CSV"""
    return pd.read_csv(file_path, delimiter='\t')

def compute_bounding_area(df):
    """Compute the bounding box of the entire area covered by the granules"""
    all_points = []
    
    for _, row in df.iterrows():
        points = [
            (row['Near Start Lat'], row['Near Start Lon']),
            (row['Far Start Lat'], row['Far Start Lon']),
            (row['Near End Lat'], row['Near End Lon']),
            (row['Far End Lat'], row['Far End Lon'])
        ]
        all_points.extend(points)
    
    # Create a polygon from all points and get its bounding box
    bounding_polygon = unary_union([Point(lat, lon) for lat, lon in all_points]).convex_hull
    min_lat, min_lon, max_lat, max_lon = bounding_polygon.bounds
    
    return min_lat, min_lon, max_lat, max_lon

def compute_tile_dimensions(min_lat, min_lon, max_lat, max_lon, percentage):
    """Compute the dimensions of each tile based on the total area and percentage"""
    lat_distance = geodesic((min_lat, min_lon), (max_lat, min_lon)).meters
    lon_distance = geodesic((min_lat, min_lon), (min_lat, max_lon)).meters
    
    # Tile dimensions
    tile_height = lat_distance * (percentage / 100)
    tile_width = lon_distance * (percentage / 100)
    
    return tile_height, tile_width

def create_tiles(df, percentage=DEFAULT_PERCENTAGE):
    """Create tiles and group granules within each tile"""
    min_lat, min_lon, max_lat, max_lon = compute_bounding_area(df)
    tile_height, tile_width = compute_tile_dimensions(min_lat, min_lon, max_lat, max_lon, percentage)
    
    tiles = {}
    tile_id = 1
    
    # Iterate through bounding box range, creating tiles by latitude and longitude steps
    current_lat = min_lat
    while current_lat < max_lat:
        current_lon = min_lon
        while current_lon < max_lon:
            tile_key = f"tile_{tile_id}"
            tile_id += 1
            
            # Define the tile polygon
            tile_polygon = Polygon([
                (current_lon, current_lat),
                (current_lon + tile_width, current_lat),
                (current_lon + tile_width, current_lat + tile_height),
                (current_lon, current_lat + tile_height),
                (current_lon, current_lat)
            ])
            
            # Find granules within the tile
            granules_in_tile = []
            for _, row in df.iterrows():
                granule_polygon = Polygon([
                    (row['Near Start Lon'], row['Near Start Lat']),
                    (row['Far Start Lon'], row['Far Start Lat']),
                    (row['Near End Lon'], row['Near End Lat']),
                    (row['Far End Lon'], row['Far End Lat'])
                ])
                if tile_polygon.intersects(granule_polygon):
                    granules_in_tile.append(row['Granule Name'])
            
            # Save tile details
            tiles[tile_key] = {
                'polygon': tile_polygon,
                'granules': granules_in_tile
            }
            
            current_lon += tile_width
        current_lat += tile_height

    return tiles

def main():
    # Set file path to your CSV
    file_path = '/path/to/your/csv_file.csv'
    percentage = float(input("Enter the tile size as a percentage of the area (e.g., 5 for 5%): ") or DEFAULT_PERCENTAGE)
    
    # Load granules data
    df = load_granules(file_path)
    
    # Create tiles
    tiles = create_tiles(df, percentage)
    
    # Output each tile with granules it contains
    for tile_key, tile_info in tiles.items():
        print(f"{tile_key}: {len(tile_info['granules'])} granules, Bounds: {tile_info['polygon'].bounds}")

if __name__ == "__main__":
    main()
