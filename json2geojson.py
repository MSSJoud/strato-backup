import json
import os
import argparse

def json2geojson(input_json_file):
    # Read the input JSON file
    with open(input_json_file, 'r') as f:
        data = json.load(f)

    # Extract the polygon coordinates from the JSON data
    if 'intersectsWith' not in data or 'POLYGON' not in data['intersectsWith']:
        raise ValueError("Invalid JSON format. The 'intersectsWith' key with 'POLYGON' value is required.")

    # Extract coordinates from the POLYGON string
    polygon_str = data['intersectsWith'].replace("POLYGON((", "").replace("))", "")
    coordinates = [[float(coord) for coord in point.split()] for point in polygon_str.split(",")]

    # Create the GeoJSON structure
    geojson_data = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [coordinates]
                },
                "properties": {}
            }
        ]
    }

    # Create the output file path
    base_name = os.path.splitext(input_json_file)[0]
    output_geojson_file = base_name + '.geojson'

    # Save the GeoJSON data to the output file
    with open(output_geojson_file, 'w') as f:
        json.dump(geojson_data, f, indent=4)

    print(f"GeoJSON file '{output_geojson_file}' created successfully.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Convert a JSON file to GeoJSON format")
    parser.add_argument('input', help='path to the input JSON file')
    args = parser.parse_args()

    json2geojson(args.input)
