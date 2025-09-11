#!/usr/bin/env python3

"""
Script to process interferogram zip files by unzipping them based on a given date range.

Usage:
    python3 process_interferograms.py --db_name <DB_NAME> --user <USER> --password <PASSWORD> --host <HOST>
                                      --input_dir <INPUT_DIR> --output_dir <OUTPUT_DIR>
                                      --start_date <YYYYMMDD> --end_date <YYYYMMDD>
                                      --unzip_files <y/n> --delete_zip <y/n>

Example:
    python3 process_interferograms.py --db_name AOI_3_interferograms --user postgres --password your_password --host localhost 
                                      --input_dir ~/data_AOI-3/AOI-3_1_interferograms 
                                      --output_dir ~/data_AOI-3/processed_interferograms 
                                      --start_date 20200101 --end_date 20201231 
                                      --unzip_files y --delete_zip n
"""

import argparse
import psycopg2
import os
import zipfile
from pathlib import Path
from datetime import datetime

def query_database(db_name, user, password, host, start_date, end_date):
    """Query the database for files within the date range."""
    try:
        conn = psycopg2.connect(
            dbname=db_name, user=user, password=password, host=host
        )
        cursor = conn.cursor()

        query = f"""
            SELECT path, start_date, end_date, platform1, platform2
            FROM interferograms
            WHERE start_date >= '{start_date}'
              AND end_date <= '{end_date}';
        """
        cursor.execute(query)
        results = cursor.fetchall()

        conn.close()
        return results

    except Exception as e:
        print(f"Error querying database: {e}")
        return []

def process_files(files, output_dir, unzip_files, delete_zip):
    """Process files: unzip and optionally delete original zip files."""
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    for file in files:
        file_path = Path(file[0])
        if not file_path.exists():
            print(f"File not found: {file_path}")
            continue

        if unzip_files:
            try:
                with zipfile.ZipFile(file_path, 'r') as zip_ref:
                    zip_ref.extractall(output_path)
                    print(f"Unzipped: {file_path}")

                if delete_zip:
                    file_path.unlink()
                    print(f"Deleted original zip: {file_path}")
            except Exception as e:
                print(f"Failed to unzip {file_path}: {e}")
        else:
            print(f"Skipping unzip for: {file_path}")

def main():
    parser = argparse.ArgumentParser(description="Process interferograms zip files.")
    parser.add_argument("--db_name", required=True, help="Name of the PostgreSQL database")
    parser.add_argument("--user", required=True, help="Database user")
    parser.add_argument("--password", required=True, help="Database password")
    parser.add_argument("--host", required=True, help="Database host")
    parser.add_argument("--input_dir", required=True, help="Input directory containing zip files")
    parser.add_argument("--output_dir", required=True, help="Output directory for unzipped files")
    parser.add_argument("--start_date", required=True, help="Start date in YYYYMMDD format")
    parser.add_argument("--end_date", required=True, help="End date in YYYYMMDD format")
    parser.add_argument("--unzip_files", choices=['y', 'n'], default='y', help="Unzip files (y/n)")
    parser.add_argument("--delete_zip", choices=['y', 'n'], default='n', help="Delete zip files after unzipping (y/n)")

    args = parser.parse_args()

    # Convert dates to YYYY-MM-DD for PostgreSQL
    start_date = datetime.strptime(args.start_date, "%Y%m%d").strftime("%Y-%m-%d")
    end_date = datetime.strptime(args.end_date, "%Y%m%d").strftime("%Y-%m-%d")

    # Query database
    files = query_database(args.db_name, args.user, args.password, args.host, start_date, end_date)

    # Process files
    process_files(files, args.output_dir, args.unzip_files == 'y', args.delete_zip == 'y')

if __name__ == "__main__":
    main()
