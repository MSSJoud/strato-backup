#!/usr/bin/env python3
"""
Populate PostgreSQL database with SLC metadata for interferometric pair selection.
Only includes essential columns: granule_name, acquisition_date, path_number, orbit.
"""

import pandas as pd
import psycopg2
import argparse
from pathlib import Path

def create_database_and_table(db_name, user='postgres', host='localhost'):
    """Create database and slc_data table if they don't exist."""
    
    # Connect to PostgreSQL default database to create new database
    try:
        conn = psycopg2.connect(dbname='postgres', user=user, host=host)
        conn.autocommit = True
        cur = conn.cursor()
        
        # Check if database exists
        cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (db_name,))
        if cur.fetchone():
            print(f"⚠️  Database '{db_name}' already exists. Will use existing database.")
        else:
            cur.execute(f"CREATE DATABASE {db_name}")
            print(f"✅ Created database: {db_name}")
        
        cur.close()
        conn.close()
    except Exception as e:
        print(f"Error creating database: {e}")
        raise
    
    # Connect to the new database and create table
    try:
        conn = psycopg2.connect(dbname=db_name, user=user, host=host)
        cur = conn.cursor()
        
        # Create table with essential columns for pair selection
        cur.execute("""
            CREATE TABLE IF NOT EXISTS slc_data (
                id SERIAL PRIMARY KEY,
                granule_name VARCHAR(255) UNIQUE NOT NULL,
                acquisition_date DATE NOT NULL,
                path_number INTEGER NOT NULL,
                orbit INTEGER NOT NULL,
                platform VARCHAR(50),
                frame_number INTEGER,
                size_mb FLOAT,
                center_lat FLOAT,
                center_lon FLOAT,
                orbit_direction VARCHAR(20)
            )
        """)
        
        conn.commit()
        cur.close()
        conn.close()
        print(f"✅ Created table 'slc_data' in database '{db_name}'")
        
    except Exception as e:
        print(f"Error creating table: {e}")
        raise

def import_slc_metadata(csv_file, db_name, user='postgres', host='localhost'):
    """Import SLC metadata from CSV to PostgreSQL."""
    
    # Read CSV
    print(f"\n📄 Reading CSV: {csv_file}")
    df = pd.read_csv(csv_file)
    
    print(f"   Rows: {len(df)}")
    print(f"   Columns: {list(df.columns)}")
    
    # Map columns to database schema
    # Our CSV has: filename, platform, acquisition_date, orbit_number, etc.
    column_mapping = {
        'filename': 'granule_name',
        'acquisition_date': 'acquisition_date',
        'orbit_number': 'orbit',
        'platform': 'platform',
        'size_gb': 'size_mb'  # Convert later
    }
    
    # Check if we need to extract path_number from filename
    if 'path_number' not in df.columns and 'filename' in df.columns:
        # Path 15 for all these SLCs
        df['path_number'] = 15
        print("   Added path_number column (Path 15)")
    
    # Convert size from GB to MB if needed
    if 'size_gb' in df.columns:
        df['size_mb'] = df['size_gb'] * 1024
    
    # Convert acquisition_date to proper format
    # Date is stored as integer YYYYMMDD (e.g., 20230104)
    df['acquisition_date'] = pd.to_datetime(df['acquisition_date'], format='%Y%m%d').dt.date
    
    # Select only columns we need
    required_cols = ['filename', 'acquisition_date', 'path_number', 'orbit_number', 'platform']
    missing_cols = [col for col in required_cols if col not in df.columns]
    if missing_cols:
        print(f"⚠️  Warning: Missing columns: {missing_cols}")
        print(f"   Available columns: {list(df.columns)}")
    
    # Connect and insert
    conn = psycopg2.connect(dbname=db_name, user=user, host=host)
    cur = conn.cursor()
    
    inserted = 0
    skipped = 0
    
    print(f"\n💾 Importing SLCs to database...")
    
    for idx, row in df.iterrows():
        try:
            granule_name = row.get('filename', '').replace('.zip', '')
            acquisition_date = row.get('acquisition_date')
            path_number = row.get('path_number', 15)
            orbit = row.get('orbit_number', 0)
            platform = row.get('platform', 'Unknown')
            
            cur.execute("""
                INSERT INTO slc_data (granule_name, acquisition_date, path_number, orbit, platform)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (granule_name) DO NOTHING
            """, (granule_name, acquisition_date, path_number, orbit, platform))
            
            if cur.rowcount > 0:
                inserted += 1
                if inserted <= 5 or inserted % 10 == 0:
                    print(f"   [{inserted:3d}/{len(df)}] {granule_name}")
            else:
                skipped += 1
                
        except Exception as e:
            print(f"   ⚠️  Error inserting row {idx}: {e}")
            continue
    
    conn.commit()
    cur.close()
    conn.close()
    
    print(f"\n{'='*80}")
    print(f"SUMMARY")
    print(f"{'='*80}")
    print(f"  • Inserted: {inserted}")
    print(f"  • Skipped:  {skipped}")
    print(f"  • Total:    {len(df)}")
    print(f"\n✅ Database populated successfully!")
    print(f"\nNext step:")
    print(f"  python select_s1_pairs_from_postgres.py --db_name {db_name} \\")
    print(f"    --bmax 100 --tmax 48 --table_name slc_data")

def main():
    parser = argparse.ArgumentParser(
        description='Populate PostgreSQL database with SLC metadata for pair selection'
    )
    parser.add_argument('--csv', required=True, help='Path to CSV file with SLC metadata')
    parser.add_argument('--db', required=True, help='PostgreSQL database name')
    parser.add_argument('--user', default='postgres', help='PostgreSQL username (default: postgres)')
    parser.add_argument('--host', default='localhost', help='PostgreSQL host (default: localhost)')
    
    args = parser.parse_args()
    
    # Check if CSV exists
    csv_path = Path(args.csv)
    if not csv_path.exists():
        print(f"❌ CSV file not found: {args.csv}")
        return 1
    
    print("="*80)
    print("POPULATE POSTGRESQL DATABASE FOR INTERFEROMETRIC PAIR SELECTION")
    print("="*80)
    print(f"\nDatabase: {args.db}")
    print(f"CSV file: {args.csv}")
    print(f"User:     {args.user}")
    print(f"Host:     {args.host}")
    print()
    
    # Create database and table
    create_database_and_table(args.db, args.user, args.host)
    
    # Import metadata
    import_slc_metadata(args.csv, args.db, args.user, args.host)
    
    return 0

if __name__ == "__main__":
    exit(main())
