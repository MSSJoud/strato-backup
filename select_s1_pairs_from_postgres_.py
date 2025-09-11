#!/usr/bin/env python3

"""
===============================================================================
Title: Sentinel-1 Interferometric Pair Selector from PostgreSQL Database
Author: 
Date: 

Description:
    This script connects to a PostgreSQL database containing Sentinel-1 SLC 
    metadata and selects suitable interferometric pairs based on constraints 
    in perpendicular baseline (B⊥) and temporal separation (ΔT). Outputs are 
    saved as:
        - sel_pairs.csv (date1, date2, perp_baseline, temporal_baseline)
        - sel_pairs.npy  (NumPy format for efficient reuse)

Usage:
    python select_s1_pairs_from_postgres.py --db_name aoi_3_slcs --table_name slc_data
                                            --bmax 200 --tmax 300

Arguments:
    --db_name       PostgreSQL database name (default: aoi_3_slcs)
    --table_name    Table name inside the database (default: slc_data)
    --bmax          Maximum perpendicular baseline in meters (default: 200)
    --tmax          Maximum temporal separation in days (default: 300)

Outputs:
    sel_pairs.csv, sel_pairs.npy

===============================================================================
Suggestions for Future Improvements:
    - [ ] Add support for multiple polarizations or burst IDs
    - [ ] Allow date range filtering or orbit selection
    - [ ] Add optional spatial filtering (e.g. AOI bounding box)
    - [ ] Modularize for import into larger workflows
===============================================================================
"""

import psycopg2
import pandas as pd
import numpy as np
import argparse
from datetime import datetime
import json
from datetime import datetime
from logger import log_script_arguments  # import central logger

# --- CLI Arguments ---
parser = argparse.ArgumentParser(description="Select interferometric pairs from Sentinel-1 metadata in PostgreSQL.")
parser.add_argument('--db_name', type=str, default='aoi_3_slcs', help='PostgreSQL database name')
parser.add_argument('--table_name', type=str, default='slc_data', help='Table name in the database')
parser.add_argument('--bmax', type=float, default=200.0, help='Max perpendicular baseline in meters')
parser.add_argument('--tmax', type=int, default=300, help='Max temporal baseline in days')

args = parser.parse_args()

arg_descriptions = {
    'db_name': 'PostgreSQL database name (default: aoi_3_slcs)',
    'table_name': 'Table name inside the database (default: slc_data)',
    'bmax': 'Maximum perpendicular baseline in meters',
    'tmax': 'Maximum temporal separation in days'
}

# --- PostgreSQL Connection ---
conn = psycopg2.connect(dbname=args.db_name, user='postgres')
query = f"SELECT acquisition_date, path_number, orbit, granule_name FROM {args.table_name} ORDER BY acquisition_date;"
df = pd.read_sql_query(query, conn)

# --- Prepare Interferometric Pairs ---
pairs = []
for path in df['path_number'].unique():
    df_path = df[df['path_number'] == path].reset_index(drop=True)
    for i in range(len(df_path)):
        for j in range(i + 1, len(df_path)):
            date1 = df_path.loc[i, 'acquisition_date']
            date2 = df_path.loc[j, 'acquisition_date']
            delta_t = abs((date2 - date1).days)
            if delta_t <= args.tmax:
                b_perp = abs(df_path.loc[j, 'orbit'] - df_path.loc[i, 'orbit'])  # simple proxy
                if b_perp <= args.bmax:
                    pairs.append([date1.strftime('%Y%m%d'), date2.strftime('%Y%m%d'), b_perp, delta_t])

# --- Save Pairs ---
pairs_np = np.array(pairs)
np.save('sel_pairs.npy', pairs_np)
pd.DataFrame(pairs_np, columns=['Date1', 'Date2', 'Bperp', 'DeltaT']).to_csv('sel_pairs.csv', index=False)

print(f"\n✅ Selected {len(pairs)} pairs and saved to 'sel_pairs.csv' and 'sel_pairs.npy'.")

# Save metadata to central logger
log_script_arguments(
    script_name="select_s1_pairs_from_postgres.py",
    arguments_dict=vars(args),
    descriptions_dict=arg_descriptions
)
print(" Logged arguments to 'processing_metadata.json'")
