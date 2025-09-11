import os
from pathlib import Path
from typing import List, Union
import h5py
import rasterio
import matplotlib.pyplot as plt
from osgeo import gdal
from pykml.factory import KML_ElementMaker as KML
from lxml import etree
import json
import geojson


def get_common_overlap(file_list: List[Union[str, Path]]) -> List[float]:
    """Get the common overlap of a list of GeoTIFF files."""
    corners = [gdal.Info(str(file), format='json')['cornerCoordinates'] for file in file_list]
    ulx = max(corner['upperLeft'][0] for corner in corners)
    uly = min(corner['upperLeft'][1] for corner in corners)
    lrx = min(corner['lowerRight'][0] for corner in corners)
    lry = max(corner['lowerRight'][1] for corner in corners)
    return [ulx, uly, lrx, lry]


def visualize_time_series(timeseries_file: str, pixel_coords: tuple):
    """Visualize time series at a given pixel."""
    with h5py.File(timeseries_file, 'r') as f:
        data = f['timeseries'][:, pixel_coords[0], pixel_coords[1]]
        dates = [d.decode('utf-8') for d in f['date'][:]]

    plt.figure(figsize=(12, 6))
    plt.plot(dates, data, marker='o')
    plt.xticks(rotation=45)
    plt.ylabel('Displacement (cm)')
    plt.title(f'Time Series at Pixel {pixel_coords}')
    plt.grid()
    plt.tight_layout()
    plt.show()


def export_to_geojson(file_list: List[Path], output_geojson: Path, overlap: List[float]):
    """Export a common overlap region to GeoJSON."""
    polygon = geojson.Polygon([[
        (overlap[0], overlap[1]),
        (overlap[0], overlap[3]),
        (overlap[2], overlap[3]),
        (overlap[2], overlap[1]),
        (overlap[0], overlap[1])
    ]])

    features = []
    for file in file_list:
        features.append(geojson.Feature(geometry=polygon, properties={"file": str(file)}))

    feature_collection = geojson.FeatureCollection(features)

    with open(output_geojson, 'w') as f:
        json.dump(feature_collection, f, indent=4)


def export_to_kml(file_list: List[Path], timeseries_file: str, output_kml: Path):
    """Generate KML with points for time-series data."""
    with h5py.File(timeseries_file, 'r') as f:
        lon = f['longitude'][:]
        lat = f['latitude'][:]

    kml = KML.kml(
        KML.Document(
            *[
                KML.Placemark(
                    KML.name(f"Point {i}"),
                    KML.Point(KML.coordinates(f"{lon[i]},{lat[i]}")),
                    KML.description(f"Time-series available at index {i}.")
                )
                for i in range(len(lon))
            ]
        )
    )

    with open(output_kml, 'w') as f:
        f.write(etree.tostring(kml, pretty_print=True).decode('utf-8'))


def clip_to_overlap(data_dir: Path, overlap: List[float]):
    """Clip all GeoTIFF files to common overlap."""
    files_to_clip = ['_water_mask.tif', '_corr.tif', '_unw_phase.tif', '_dem.tif', '_lv_theta.tif', '_lv_phi.tif']
    for ext in files_to_clip:
        for file in data_dir.rglob(f'*{ext}'):
            dst_file = file.parent / f'{file.stem}_clipped{file.suffix}'
            gdal.Translate(destName=str(dst_file), srcDS=str(file), projWin=overlap)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="GeoTIFF Analysis and Visualization for MintPy")
    parser.add_argument("--data_dir", type=str, required=True, help="Path to the data directory.")
    parser.add_argument("--timeseries_file", type=str, required=True, help="Path to the time-series file.")
    parser.add_argument("--output_dir", type=str, required=True, help="Path to the output directory.")
    parser.add_argument("--start_date", type=str, help="Start date for filtering data (optional).")
    parser.add_argument("--end_date", type=str, help="End date for filtering data (optional).")
    parser.add_argument("--generate_geojson", action="store_true", help="Generate GeoJSON from overlap.")
    parser.add_argument("--generate_kml", action="store_true", help="Generate KML file for time series.")
    args = parser.parse_args()

    data_dir = Path(args.data_dir)
    output_dir = Path(args.output_dir)
    timeseries_file = args.timeseries_file

    # Process GeoTIFFs and get overlap
    files = list(data_dir.glob('*/*_unw_phase.tif'))
    overlap = get_common_overlap(files)
    clip_to_overlap(data_dir, overlap)

    # Export GeoJSON or KML if requested
    if args.generate_geojson:
        geojson_path = output_dir / "region_overlap.geojson"
        export_to_geojson(files, geojson_path, overlap)

    if args.generate_kml:
        kml_path = output_dir / "time_series_points.kml"
        export_to_kml(files, timeseries_file, kml_path)
