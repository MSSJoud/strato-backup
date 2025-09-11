import json
import argparse
from simplekml import Kml


def polygon_to_geojson_and_kml(polygon_str, geojson_output_path, kml_output_path):
    polygon_str = polygon_str.replace("POLYGON((", "").replace("))", "")
    coordinates = [[float(coord) for coord in point.split()] for point in polygon_str.split(",")]

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

    with open(geojson_output_path, 'w') as geojson_file:
        json.dump(geojson_data, geojson_file, indent=4)
    print(f"GeoJSON saved to: {geojson_output_path}")

    kml = Kml()
    kml_polygon = kml.newpolygon(name="Polygon")
    kml_polygon.outerboundaryis.coords = [(lon, lat) for lon, lat in coordinates]
    kml_polygon.style.polystyle.color = "7dff0000"
    kml.save(kml_output_path)
    print(f"KML saved to: {kml_output_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Convert polygon string to GeoJSON and KML")
    parser.add_argument("--polygon", required=True, help="Polygon string in POLYGON((...)) format")
    parser.add_argument("--geojson", required=True, help="Path to save the GeoJSON file")
    parser.add_argument("--kml", required=True, help="Path to save the KML file")
    args = parser.parse_args()

    polygon_to_geojson_and_kml(args.polygon, args.geojson, args.kml)
