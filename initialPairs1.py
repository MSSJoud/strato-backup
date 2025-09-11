import json
import argparse
from pathlib import Path
import asf_search as asf
import pandas as pd

def get_aoi_bounds(aoi_json_path):
    with open(aoi_json_path) as f:
        aoi = json.load(f)
    coordinates = aoi["features"][0]["geometry"]["coordinates"][0]
    minLon = min([coord[0] for coord in coordinates])
    maxLon = max([coord[0] for coord in coordinates])
    minLat = min([coord[1] for coord in coordinates])
    maxLat = max([coord[1] for coord in coordinates])
    return minLat, maxLat, minLon, maxLon

def get_initial_pairs(aoi_bounds, start_date, end_date, asf_user, asf_pwd):
    minLat, maxLat, minLon, maxLon = aoi_bounds
    results = asf.geo_search(platform=['SENTINEL-1A', 'SENTINEL-1B'],
                             start=start_date,
                             end=end_date,
                             intersectsWith=f'POLYGON(({minLon} {minLat},{maxLon} {minLat},{maxLon} {maxLat},{minLon} {maxLat},{minLon} {minLat}))')
    return results

def save_pairs_to_csv(results, output_csv):
    data = []
    for result in results:
        entry = {
            "Reference": result.properties['sceneName'],
            "Secondary": "",  # Placeholder
            "TemporalBaseline": "",  # Placeholder
            "SpatialBaseline": ""   # Placeholder
        }
        data.append(entry)
    
    df = pd.DataFrame(data)
    df.to_csv(output_csv, index=False)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate initial pairs based on AOI and criteria")
    parser.add_argument('-c', '--config', required=True, help='path to config file (*.py)')
    args = parser.parse_args()

    config_path = Path(args.config)
    config_dir = config_path.parent
    config_module = config_path.stem

    sys.path.append(str(config_dir))
    config = __import__(config_module)

    aoi_bounds = get_aoi_bounds(config.aoi_json_path)
    results = get_initial_pairs(aoi_bounds, f"{config.startYear}0101", f"{config.endYear}1231", config.ASFUsr, config.ASFPwd)
    save_pairs_to_csv(results, config.fnInitPairs)
