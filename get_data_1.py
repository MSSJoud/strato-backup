import asf_search as asf
from datetime import datetime
import json

# Function to load AOI from JSON file
def load_aoi_from_json(json_file: str) -> dict:
    with open(json_file, 'r') as f:
        aoi_data = json.load(f)
    return aoi_data

# Define time span
start_date = datetime(2014, 1, 1).strftime('%Y-%m-%d')
end_date = datetime(2017, 12, 31).strftime('%Y-%m-%d')

# Load AOI 1 from JSON file
aoi_1_file = '/work/ISCE2/NileBasins/AOI-1.json'
options_1: dict = load_aoi_from_json(aoi_1_file)
options_1.update({
    'platform': [asf.PLATFORM.SENTINEL1],
    'start': start_date,
    'end': end_date,
    'maxResults': 250
})

# Load AOI 2 from JSON file
aoi_2_file = '/work/ISCE2/NileBasins/AOI-2.json'
options_2: dict = load_aoi_from_json(aoi_2_file)
options_2.update({
    'platform': [asf.PLATFORM.SENTINEL1],
    'start': start_date,
    'end': end_date,
    'maxResults': 250
})

# Perform the search for AOI 1
results_1 = asf.geo_search(**options_1)
print(f"Results for AOI 1: {len(results_1)} products found.")

# Perform the search for AOI 2
results_2 = asf.geo_search(**options_2)
print(f"Results for AOI 2: {len(results_2)} products found.")

# Download the data
session = asf.ASFSession().auth_with_creds('your_username', 'your_password')

# Download results for AOI 1
results_1.download(path='/path/to/your/download/directory', session=session)

# Download results for AOI 2
results_2.download(path='/path/to/your/download/directory', session=session)
