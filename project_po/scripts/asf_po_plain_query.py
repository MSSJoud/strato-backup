import asf_search as asf
from datetime import datetime
import json
from pathlib import Path
'''
This script queries the ASF (Alaska Satellite Facility) API for satellite imagery
manifests over a specified Area of Interest (AOI) and time range. It retrieves
data for multiple satellite platforms and saves the results in JSON format. 
Adjust the AOI and time ranges as needed.   
Requires the asf_search package: pip install asf-search
Usage: python asf_po_plain_query.py

'''
# --- AOI polygon (GeoJSON dict) ---
aoi_geojson = {
  "type": "Polygon",
  "coordinates": [[
    [8.5, 44.0],
    [13.5, 44.0],
    [13.5, 46.2],
    [8.5, 46.2],
    [8.5, 44.0]
  ]]
}

OUTDIR = Path("data/_asf_manifests")
OUTDIR.mkdir(parents=True, exist_ok=True)

def save_results(name, results):
    items = []
    for r in results:
        # store the most useful fields (extend as needed)
        items.append({
            "granule": r.properties.get("fileID") or r.properties.get("sceneName") or r.properties.get("granuleName"),
            "platform": r.properties.get("platform"),
            "startTime": r.properties.get("startTime"),
            "stopTime": r.properties.get("stopTime"),
            "beamModeType": r.properties.get("beamModeType"),
            "flightDirection": r.properties.get("flightDirection"),
            "pathNumber": r.properties.get("pathNumber"),
            "frameNumber": r.properties.get("frameNumber"),
            "url": r.properties.get("url"),
            "downloadUrl": r.properties.get("downloadUrl"),
        })
    (OUTDIR / f"{name}.json").write_text(json.dumps(items, indent=2))
    print(f"[OK] {name}: {len(items)} scenes → {OUTDIR/name}.json")

# --- Sentinel-1 IW (start with ONE orbit direction; change later) ---
s1 = asf.search(
    platform=asf.PLATFORM.SENTINEL1,
    intersectsWith=aoi_geojson,
    processingLevel=asf.PRODUCT_TYPE.SLC,
    beamMode=asf.BEAMMODE.IW,
    start="2014-01-01",
    end=datetime.utcnow().strftime("%Y-%m-%d"),
    # flightDirection="ASCENDING",   # or "DESCENDING"
)
save_results("S1_IW_SLC", s1)

# --- Envisat (ASAR) ---
# Note: availability varies; keep the query broad first.
env = asf.search(
    platform=asf.PLATFORM.ENVISAT,
    intersectsWith=aoi_geojson,
    start="2002-01-01",
    end="2012-12-31",
)
save_results("ENV", env)

# --- ERS-1/2 ---
ers = asf.search(
    platform=asf.PLATFORM.ERS,
    intersectsWith=aoi_geojson,
    start="1991-01-01",
    end="2011-12-31",
)
save_results("ERS", ers)

# --- ALOS-1 (PALSAR) ---
alos1 = asf.search(
    platform=asf.PLATFORM.ALOS,
    intersectsWith=aoi_geojson,
    start="2006-01-01",
    end="2011-12-31",
)
save_results("ALOS1", alos1)
