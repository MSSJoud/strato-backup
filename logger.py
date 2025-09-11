# logger.py

import os
import json
from datetime import datetime

METADATA_FILE = "processing_metadata.json"

def log_script_arguments(script_name, arguments_dict, descriptions_dict):
    # Load existing metadata
    if os.path.exists(METADATA_FILE):
        with open(METADATA_FILE, "r") as f:
            metadata = json.load(f)
    else:
        metadata = {
            "updated": str(datetime.utcnow()),
            "scripts": {}
        }

    # Add/Update this script's section
    metadata["scripts"][script_name] = {
        "timestamp": str(datetime.utcnow()),
        "arguments": [
            {
                "name": key,
                "value": value,
                "description": descriptions_dict.get(key, "N/A")
            } for key, value in arguments_dict.items()
        ]
    }

    # Save back to file
    metadata["updated"] = str(datetime.utcnow())
    with open(METADATA_FILE, "w") as f:
        json.dump(metadata, f, indent=4)
