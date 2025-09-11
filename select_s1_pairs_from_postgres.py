#!/usr/bin/env python3
"""
select_s1_pairs_from_postgres.py

Author:
Date:

Description:
    Select interferometric pairs from Sentinel-1 metadata in PostgreSQL
    based on max baseline (B⊥) and max temporal span (ΔT). Also provides
    a reusable function for other scripts.

Usage:
    python select_s1_pairs_from_postgres.py --db_name aoi_3_slcs --table_name slc_data --bmax 200 --tmax 300
"""

import psycopg2
import pandas as pd
import numpy as np
import argparse
from logger import log_script_arguments


def select_s1_pairs_from_db(db_name='aoi_3_slcs', table_name='slc_data', bmax=200.0, tmax=300):
    conn = psycopg2.connect(dbname=db_name, user='postgres', host='localhost')
    query = f"SELECT acquisition_date, path_number, orbit, granule_name FROM {table_name} ORDER BY acquisition_date;"
    df = pd.read_sql_query(query, conn)
    conn.close()

    pairs = []
    for path in df['path_number'].unique():
        df_path = df[df['path_number'] == path].reset_index(drop=True)
        for i in range(len(df_path)):
            for j in range(i + 1, len(df_path)):
                date1 = df_path.loc[i, 'acquisition_date']
                date2 = df_path.loc[j, 'acquisition_date']
                delta_t = abs((date2 - date1).days)
                if delta_t <= tmax:
                    b_perp = abs(df_path.loc[j, 'orbit'] - df_path.loc[i, 'orbit'])
                    if b_perp <= bmax:
                        pairs.append({
                            'master': df_path.loc[i, 'granule_name'],
                            'slave': df_path.loc[j, 'granule_name'],
                            'path': path,
                            'Bperp': b_perp,
                            'delta_days': delta_t
                        })
    return pd.DataFrame(pairs)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Select interferometric pairs from Sentinel-1 PostgreSQL DB")
    parser.add_argument('--db_name', default='aoi_3_slcs', help='PostgreSQL database name')
    parser.add_argument('--table_name', default='slc_data', help='Database table name')
    parser.add_argument('--bmax', type=float, default=200.0, help='Maximum B⊥ baseline')
    parser.add_argument('--tmax', type=int, default=300, help='Maximum temporal baseline')

    args = parser.parse_args()

    df = select_s1_pairs_from_db(args.db_name, args.table_name, args.bmax, args.tmax)
    df.to_csv("sel_pairs.csv", index=False)
    np.save("sel_pairs.npy", df[['master', 'slave', 'Bperp', 'delta_days']].values)

    print(f"[✓] Saved {len(df)} pairs to sel_pairs.csv and sel_pairs.npy")

    log_script_arguments(
        "select_s1_pairs_from_postgres.py",
        vars(args),
        {
            'db_name': 'PostgreSQL database name',
            'table_name': 'Name of table inside DB',
            'bmax': 'Max perpendicular baseline (m)',
            'tmax': 'Max temporal baseline (days)'
        }
    )
