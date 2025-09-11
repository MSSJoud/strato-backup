#!/usr/bin/env python3

"""
Import Sentinel-1 SLC metadata from CSV to PostgreSQL.

Usage:
    python import_slcs_to_postgres.py --csv ~/work/AOI-3.csv --db aoi_3_slcs --user postgres --host localhost
"""

import pandas as pd
import psycopg2
import argparse

def import_csv_to_postgres(csv_file, db_name, user, host):
    """Reads a CSV and inserts data into PostgreSQL while handling missing values."""

    # Connect to PostgreSQL
    conn = psycopg2.connect(dbname=db_name, user=user, host=host)
    cur = conn.cursor()

    # Read CSV with proper handling of empty values
    print(f"Reading CSV file: {csv_file}")
    df = pd.read_csv(csv_file, dtype=str)  # Read all as string first

    # Replace empty strings with NULL
    df = df.where(pd.notnull(df), None)

    # Convert specific columns to appropriate types
    convert_dict = {
        "orbit": pd.to_numeric,
        "path_number": pd.to_numeric,
        "frame_number": pd.to_numeric,
        "size_mb": pd.to_numeric,
        "center_lat": pd.to_numeric,
        "center_lon": pd.to_numeric,
        "near_start_lat": pd.to_numeric,
        "near_start_lon": pd.to_numeric,
        "far_start_lat": pd.to_numeric,
        "far_start_lon": pd.to_numeric,
        "near_end_lat": pd.to_numeric,
        "near_end_lon": pd.to_numeric,
        "far_end_lat": pd.to_numeric,
        "far_end_lon": pd.to_numeric,
        "doppler": pd.to_numeric,
        "pointing_angle": pd.to_numeric,
        "samples_per_burst": pd.to_numeric,
        "azimuth_time": pd.to_datetime,
        "azimuth_anx_time": pd.to_datetime,
        "acquisition_date": pd.to_datetime,
        "processing_date": pd.to_datetime,
        "start_time": pd.to_datetime,
        "end_time": pd.to_datetime
    }

    for col, func in convert_dict.items():
        if col in df.columns:
            df[col] = df[col].apply(lambda x: func(x) if x is not None else None)

    # Insert into PostgreSQL
    for _, row in df.iterrows():
        cur.execute("""
            INSERT INTO slc_data (
                granule_name, platform, sensor, beam_mode, beam_mode_description, 
                orbit, path_number, frame_number, acquisition_date, processing_date, 
                processing_level, start_time, end_time, center_lat, center_lon, 
                near_start_lat, near_start_lon, far_start_lat, far_start_lon, 
                near_end_lat, near_end_lon, far_end_lat, far_end_lon, faraday_rotation, 
                ascending_or_descending, url, size_mb, off_nadir_angle, stack_size, 
                doppler, group_id, pointing_angle, relative_burst_id, absolute_burst_id, 
                full_burst_id, burst_index, azimuth_time, azimuth_anx_time, samples_per_burst, subswath
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, tuple(row))

    conn.commit()
    cur.close()
    conn.close()
    print("✅ CSV data successfully imported into PostgreSQL!")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Import SLC metadata from CSV to PostgreSQL.")
    parser.add_argument('--csv', required=True, help="Path to the CSV file")
    parser.add_argument('--db', required=True, help="PostgreSQL database name")
    parser.add_argument('--user', required=True, help="PostgreSQL username")
    parser.add_argument('--host', default="localhost", help="PostgreSQL host (default: localhost)")

    args = parser.parse_args()
    import_csv_to_postgres(args.csv, args.db, args.user, args.host)
