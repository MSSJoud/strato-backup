#!/usr/bin/env python3
"""
Granule PostgreSQL Database Management Script

Description:
------------
This script creates a PostgreSQL database from a CSV file containing Sentinel-1 granule metadata.
It also supports querying the database using SQL commands provided as input.

Features:
---------
1. **Create Database & Table**: Reads a CSV file and converts it into a PostgreSQL database.
2. **Execute Queries**: Allows users to run SQL queries against the database.
3. **Handles Authentication**: Detects whether a password is needed.
4. **User-Friendly Inputs**: Accepts database name, user credentials, CSV path, and queries as arguments.

Usage:
------
To create a database and import CSV:
    python granule_psql_database.py --csv path/to/granules.csv --db aoi_3_slcs --user postgres

To query an existing database:
    python granule_psql_database.py --db aoi_3_slcs --user postgres --query "SELECT * FROM slc_data WHERE platform = 'Sentinel-1A'"

Arguments:
----------
--csv    : (Optional) Path to the input CSV file containing granule metadata.
--db     : (Required) Name of the PostgreSQL database.
--user   : (Required) PostgreSQL username (e.g., "postgres").
--host   : (Optional) Database host (default: "localhost").
--port   : (Optional) Database port (default: "5432").
--query  : (Optional) SQL query to execute after creating the database.
--password : (Optional) PostgreSQL password (if required).

Example:
--------
Create database and import CSV:
    python granule_psql_database.py --csv ~/work/AOI-3.csv --db aoi_3_slcs --user postgres

Run a query:
    python granule_psql_database.py --db aoi_3_slcs --user postgres --query "SELECT * FROM slc_data WHERE path_number = 44"
"""

import pandas as pd
import argparse
import psycopg2
from psycopg2 import sql
from sqlalchemy import create_engine
import getpass

def create_database(db_name, user, host="localhost", port="5432", password=None):
    """
    Creates a PostgreSQL database if it doesn't exist.
    """
    try:
        # Connect to PostgreSQL (without specifying a database)
        conn = psycopg2.connect(dbname="postgres", user=user, host=host, port=port, password=password)
        conn.autocommit = True
        cur = conn.cursor()

        # Check if the database already exists
        cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (db_name,))
        exists = cur.fetchone()
        if not exists:
            cur.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(db_name)))
            print(f"✅ Database '{db_name}' created successfully.")
        else:
            print(f"⚠️ Database '{db_name}' already exists.")
        
        cur.close()
        conn.close()
    except Exception as e:
        print(f"❌ Error creating database: {e}")

def import_csv_to_postgres(db_name, user, csv_file, host="localhost", port="5432", password=None):
    """
    Imports a CSV file into a PostgreSQL database.
    """
    try:
        # Connect using SQLAlchemy
        engine = create_engine(f"postgresql://{user}:{password}@{host}:{port}/{db_name}")

        # Read CSV file
        df = pd.read_csv(csv_file)

        # Replace empty strings with NULL
        df = df.where(pd.notna(df), None)

        # Write to PostgreSQL
        df.to_sql("slc_data", engine, if_exists="replace", index=False)
        
        print(f"✅ Data from '{csv_file}' imported successfully into database '{db_name}' (Table: slc_data).")
    except Exception as e:
        print(f"❌ Error importing CSV: {e}")

def execute_query(db_name, user, query, host="localhost", port="5432", password=None):
    """
    Executes an SQL query on the PostgreSQL database and prints the results.
    """
    try:
        conn = psycopg2.connect(dbname=db_name, user=user, host=host, port=port, password=password)
        cur = conn.cursor()
        
        cur.execute(query)
        results = cur.fetchall()

        # Print query results
        for row in results:
            print(row)

        cur.close()
        conn.close()
    except Exception as e:
        print(f"❌ Error executing query: {e}")

def main():
    parser = argparse.ArgumentParser(description="Create and query a PostgreSQL granule database from a CSV file.")
    parser.add_argument('--csv', help="Path to the CSV file containing granule data.")
    parser.add_argument('--db', required=True, help="PostgreSQL database name.")
    parser.add_argument('--user', required=True, help="PostgreSQL username.")
    parser.add_argument('--host', default="localhost", help="Database host (default: localhost).")
    parser.add_argument('--port', default="5432", help="Database port (default: 5432).")
    parser.add_argument('--query', help="SQL query to execute on the database.")
    parser.add_argument('--password', help="PostgreSQL password (optional).")

    args = parser.parse_args()

    # If no password is provided, prompt the user for one (to keep it secure)
    if args.password is None:
        try:
            args.password = getpass.getpass("🔑 Enter PostgreSQL password (leave empty if not required): ")
            if args.password.strip() == "":
                args.password = None
        except KeyboardInterrupt:
            print("\n❌ Operation cancelled.")
            return

    # Step 1: Create database (if not exists)
    create_database(args.db, args.user, args.host, args.port, args.password)

    # Step 2: Import CSV into database
    if args.csv:
        import_csv_to_postgres(args.db, args.user, args.csv, args.host, args.port, args.password)

    # Step 3: Execute query (if provided)
    if args.query:
        print(f"🔍 Running query on database '{args.db}':\n{args.query}")
        execute_query(args.db, args.user, args.query)
    elif not args.csv:
        print("⚠️ No CSV file or query provided. Database is ready for future operations.")

if __name__ == "__main__":
    main()
