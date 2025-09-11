import psycopg2
import csv
import os
from pathlib import Path

def create_database(db_name, user, password, host='localhost', port=5432):
    """
    Creates a PostgreSQL database.
    """
    try:
        conn = psycopg2.connect(dbname='postgres', user=user, password=password, host=host, port=port)
        conn.autocommit = True
        cursor = conn.cursor()
        cursor.execute(f"CREATE DATABASE \"{db_name}\";")
        print(f"Database '{db_name}' created successfully.")
        conn.close()
    except Exception as e:
        print(f"Failed to create database: {e}")

def create_table(db_name, user, password, host='localhost', port=5432):
    """
    Creates a table in the database for storing interferogram metadata.
    """
    try:
        conn = psycopg2.connect(dbname=db_name, user=user, password=password, host=host, port=port)
        cursor = conn.cursor()

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS interferograms (
            id SERIAL PRIMARY KEY,
            url TEXT,
            file_id TEXT,
            path TEXT,
            start_date DATE,
            end_date DATE,
            platform1 TEXT,
            platform2 TEXT,
            size_mb FLOAT
        );
        """)

        conn.commit()
        print("Table 'interferograms' created successfully.")
        conn.close()
    except Exception as e:
        print(f"Failed to create table: {e}")

def populate_table(db_name, user, password, csv_file, base_dir, host='localhost', port=5432):
    """
    Populates the table with data from the CSV file and additional metadata.
    """
    try:
        conn = psycopg2.connect(dbname=db_name, user=user, password=password, host=host, port=port)
        cursor = conn.cursor()

        with open(csv_file, 'r') as file:
            reader = csv.DictReader(file)
            for row in reader:
                url = row.get('URL') or row.get('Url') or row.get('url')
                file_id = row.get('File ID')
                if not url or not file_id:
                    print(f"Skipping row with missing URL or File ID: {row}")
                    continue

                # Extract metadata from file name
                filename = Path(url).name
                platforms = filename.split('_')[0]
                platform1, platform2 = platforms[:3], platforms[3:]
                start_date = filename.split('_')[1][:8]
                end_date = filename.split('_')[2][:8]
                filepath = os.path.join(base_dir, filename)
                size_mb = os.path.getsize(filepath) / (1024 * 1024) if os.path.exists(filepath) else None

                cursor.execute("""
                INSERT INTO interferograms (url, file_id, path, start_date, end_date, platform1, platform2, size_mb)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """, (url, file_id, filepath, start_date, end_date, platform1, platform2, size_mb))

        conn.commit()
        print("Table 'interferograms' populated successfully.")
        conn.close()
    except Exception as e:
        print(f"Failed to populate table: {e}")

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Create and populate a PostgreSQL database for interferograms.")
    parser.add_argument("--db_name", required=True, help="Name of the database.")
    parser.add_argument("--user", required=True, help="Database username.")
    parser.add_argument("--password", required=False, help="Database password (optional if trust authentication is used).")
    parser.add_argument("--csv_file", required=True, help="Path to the input CSV file.")
    parser.add_argument("--base_dir", required=True, help="Base directory where the interferograms are stored.")
    args = parser.parse_args()

    create_database(args.db_name, args.user, args.password)
    create_table(args.db_name, args.user, args.password)
    populate_table(args.db_name, args.user, args.password, args.csv_file, args.base_dir)
