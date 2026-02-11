'''
This script generates pairs of satellite imagery granules from ASF manifests
based on specified time difference criteria. It reads manifest JSON files,
identifies pairs of granules within a defined time window, and saves the pairs
to CSV files for further processing.
Usage: python make_pairs.py
'''

import json
from pathlib import Path
from datetime import datetime
import itertools

def parse_date(s):
    # ASF startTime example: "2019-01-01T17:23:00.000Z"
    return datetime.fromisoformat(s.replace("Z","").replace("000",""))

def make_pairs(manifest_json, out_csv, dt_max_days=365):
    items = json.loads(Path(manifest_json).read_text())
    # sort by startTime
    items = [x for x in items if x.get("startTime")]
    items.sort(key=lambda x: x["startTime"])

    rows = []
    for a, b in itertools.combinations(items, 2):
        ta = parse_date(a["startTime"])
        tb = parse_date(b["startTime"])
        dt = abs((tb - ta).days)
        if dt == 0 or dt > dt_max_days:
            continue
        rows.append((a["granule"], b["granule"], a["startTime"], b["startTime"], dt))

    out = ["ref,sec,ref_time,sec_time,dt_days\n"] + [
        f"{r[0]},{r[1]},{r[2]},{r[3]},{r[4]}\n" for r in rows
    ]
    Path(out_csv).parent.mkdir(parents=True, exist_ok=True)
    Path(out_csv).write_text("".join(out))
    print(f"[OK] {out_csv}: {len(rows)} pairs")

if __name__ == "__main__":
    make_pairs("data/_asf_manifests/ERS.json",  "pairs/pairs_ERS.csv",  dt_max_days=365)
    make_pairs("data/_asf_manifests/ENV.json",  "pairs/pairs_ENV.csv",  dt_max_days=365)
    make_pairs("data/_asf_manifests/ALOS1.json","pairs/pairs_ALOS.csv", dt_max_days=365)
    make_pairs("data/_asf_manifests/S1_IW_SLC.json","pairs/pairs_S1.csv", dt_max_days=24)
