#!/usr/bin/env python3
"""
Granule Database Management Script

Description:
------------
This script creates a SQLite database from a CSV file containing Sentinel-1 granule metadata. 
It also supports querying the database using SQL commands provided as input.

Features:
---------
1. **Create Database**: Reads a CSV file and converts it into a SQLite database.
2. **Execute Queries**: Allows the user to run SQL queries against the database.
3. **User-Friendly Inputs**: Accepts input CSV file, database path, and SQL queries as command-line arguments.

Usage:
------
To create a database:
    python granule_database.py --csv path/to/your_granules.csv --db path/to/your_database.db

To create a database and query it:
    python granule_database.py --csv path/to/your_granules.csv --db path/to/your_database.db --query "SELECT * FROM granules WHERE Year = 2024"

Arguments:
----------
--csv    : Path to the input CSV file containing granule metadata.
--db     : Path to the SQLite database file to be created.
--query  : (Optional) SQL query to execute after creating the database.

Example:
--------
Create the database:
    python granule_database.py --csv granules.csv --db granule_data.db

Run a query:
    python granule_database.py --csv granules.csv --db granule_data.db --query "SELECT * FROM granules WHERE Path_Number = 35"
"""

import sqlite3
import pandas as pd
import argparse

def create_database(database_path, csv_path):
    """
    Creates a SQLite database from a CSV file.

    Args:
        database_path (str): Path to the SQLite database file.
        csv_path (str): Path to the input CSV file.
    """
    try:
        # Read CSV into a DataFrame
        print(f"Reading data from CSV file: {csv_path}")
        data = pd.read_csv(csv_path)

        # Create a SQLite database
        print(f"Creating SQLite database at: {database_path}")
        conn = sqlite3.connect(database_path)
        data.to_sql('granules', conn, if_exists='replace', index=False)
        conn.close()
        print("Database created successfully!")
    except Exception as e:
        print(f"Error creating database: {e}")


def query_database(database_path, query):
    """
    Executes a SQL query on the database.

    Args:
        database_path (str): Path to the SQLite database file.
        query (str): SQL query string.

    Returns:
        pd.DataFrame: Results of the query.
    """
    try:
        print(f"Executing query: {query}")
        conn = sqlite3.connect(database_path)
        result = pd.read_sql_query(query, conn)
        conn.close()
        return result
    except Exception as e:
        print(f"Error executing query: {e}")
        return None


def main():
    parser = argparse.ArgumentParser(description="Create and query a granule database from a CSV file.")
    parser.add_argument('--csv', help="Path to the CSV file containing granule data.")
    parser.add_argument('--db', required=True, help="Path to the SQLite database file.")
    parser.add_argument('--query', help="SQL query to execute on the database.")
    args = parser.parse_args()

    # Create the database from the specified CSV file if the --csv argument is provided
    if args.csv:
        print(f"Creating database {args.db} from {args.csv}")
        create_database(args.db, args.csv)

    # If a query is provided, execute it and display the results
    if args.query:
        results = query_database(args.db, args.query)
        if results is not None:
            print("Query Results:")
            print(results)
    elif not args.csv:
        print("Please provide either a --csv file to create a database or a --query to execute.")


if __name__ == "__main__":
    main()

