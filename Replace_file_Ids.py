import os
import pandas as pd
from pathlib import Path

# Paths
data_dir = Path("~/data_AOI-3/AOI-3_1_interferograms").expanduser()
csv_file = Path("AOI-3_1.csv").resolve()

# Read the CSV file
data = pd.read_csv(csv_file)


url_column = next((col for col in data.columns if col.lower() == 'url'), None)
if not url_column:
        raise ValueError("CSV file must contain a column named 'URL' (case-insensitive).")


# Ensure the directory exists
if not data_dir.is_dir():
    print(f"Error: Directory {data_dir} does not exist.")
    exit(1)


# Create a dictionary of File IDs and corresponding filenames
file_map = {}
for _, row in data.iterrows():
    url = row[url_column]
    if not isinstance(url, str):
        continue  # Skip invalid rows
    filename = url.split('/')[-1]
    file_id = filename.split('.')[0]
    file_map[file_id] = filename

# Rename files in the data directory
for file in data_dir.glob("*.zip"):
    file_id = file.stem  # Current file ID (stem of the file)
    if file_id in file_map:
        new_name = data_dir / file_map[file_id]
        print(f"Renaming {file.name} -> {new_name.name}")
        file.rename(new_name)
    else:
        print(f"No match found for {file.name}, skipping.")
