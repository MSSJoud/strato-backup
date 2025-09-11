#!/usr/bin/env python3

"""
Geo-KML Converter
=================

A simple tool to convert between GeoJSON/JSON and KML formats.
Supports multi-vertex polygons and retains geometry and properties.

Dependencies:
-------------
- geopandas
- fastkml
- shapely

Install via pip:
    pip install geopandas fastkml shapely

Usage Examples:
---------------
1. Convert GeoJSON to KML:
    python geo_kml_converter.py myfile.geojson --to kml

2. Convert KML to GeoJSON:
    python geo_kml_converter.py myfile.kml --to geojson

The output file will be saved in the same directory with the same name and new extension.
"""

import os
import argparse
import json
from fastkml import kml
import geopandas as gpd
from shapely.geometry import shape
from shapely import wkt

def geojson_to_kml(input_path):
    with open(input_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    # If it's not GeoJSON, convert it using your custom logic
    if 'features' not in data:
        if 'intersectsWith' not in data or 'POLYGON' not in data['intersectsWith']:
            print("Unsupported JSON structure.")
            return

        # Convert to GeoJSON-style dictionary
        polygon_str = data['intersectsWith'].replace("POLYGON((", "").replace("))", "")
        coordinates = [[float(coord) for coord in point.split()] for point in polygon_str.split(",")]
        data = {
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

    # Now proceed as if it's a normal GeoJSON
    kml_doc = kml.KML()
    ns = '{http://www.opengis.net/kml/2.2}'
    document = kml.Document(ns=ns, id='docid', name='doc name')
    #document = kml.Document(ns=ns, id='docid', name='doc name', name_spaces={})
    #document.description = "doc description"

    kml_doc.append(document)

    for i, feature in enumerate(data['features']):
        geom = shape(feature['geometry'])
        props = feature.get('properties', {})
        name = props.get('name', f'Feature {i}')
        placemark = kml.Placemark(ns=ns, id=str(i), name=name, geometry=geom)
        placemark.description = ""


        document.append(placemark)

    output_path = os.path.splitext(input_path)[0] + '.kml'
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(kml_doc.to_string(prettyprint=True))
    print("Saved:", output_path)




def kml_to_geojson(input_path):
    with open(input_path, 'rb') as f:
        doc = f.read()

    k = kml.KML()
    k.from_string(doc)

    features = list(k.features())
    placemarks = []
    for d in features:
        placemarks.extend(list(d.features()))

    data = {
        "type": "FeatureCollection",
        "features": []
    }

    for p in placemarks:
        feature = {
            "type": "Feature",
            "properties": {
                "name": p.name or ""
            },
            "geometry": json.loads(gpd.GeoSeries([p.geometry]).to_json())['features'][0]['geometry']
        }
        data["features"].append(feature)

    output_path = os.path.splitext(input_path)[0] + '.geojson'
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2)
    print(f"✔️ Saved: {output_path}")

def main():
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("input_file", help="Path to the input file (.geojson/.json/.kml)")
    parser.add_argument("--to", choices=["kml", "geojson"], required=True,
                        help="Target format: 'kml' or 'geojson'")

    args = parser.parse_args()

    ext = os.path.splitext(args.input_file)[1].lower()
    if args.to == "kml" and ext in [".geojson", ".json"]:
        geojson_to_kml(args.input_file)
    elif args.to == "geojson" and ext == ".kml":
        kml_to_geojson(args.input_file)
    else:
        print("❌ Unsupported conversion. Please check file extension and '--to' format.")

if __name__ == "__main__":
    main()
