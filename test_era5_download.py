import cdsapi

# Initialize the client
client = cdsapi.Client()

# Define the dataset and request parameters
dataset = "reanalysis-era5-pressure-levels"  # Use the correct dataset name for ERA5 pressure levels
request = {
    "product_type": "reanalysis",
    "format": "grib",
    "variable": [
        "geopotential", "temperature", "specific_humidity"
    ],
    "pressure_level": [
        "1000", "850", "500", "250", "50"
    ],
    "year": "2020",
    "month": ["01", "02", "03"],
    "day": ["01", "02", "03", "04", "05"],
    "time": ["00:00", "06:00", "12:00", "18:00"],
    "area": [
        50, 0, 40, 20
    ],  # North, West, South, East
}

# Specify the output target file
target = "ERA5_test_download.grib"

# Retrieve the data
print("Requesting data from Copernicus...")
client.retrieve(dataset, request, target)
print(f"Data downloaded successfully and saved to {target}")
