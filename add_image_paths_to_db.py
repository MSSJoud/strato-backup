#!/usr/bin/env python3
"""
Add Image Paths to Granule Database

Description:
------------
This script adds the file paths of downloaded SAR images to an existing granule database.
It matches the granule names in the database with the file names (stem) in the specified image directory.

Features:
---------
1. Ensures the database has a column `image_path` in the `granules` table.
   - If the column does not exist, it adds the column.
2. Traverses the specified image directory recursively to find `.tif` files.
3. Matches the file names (stem) with the `Granule Name` field in the database.
4. Updates the database with the full file paths of the matched images.

Usage:
------
Save this script as `add_image_paths.py` and run it as follows:

```bash
python add_image_paths.py --db <path_to_database> --image_dir <path_to_image_directory>
"""


import os
import sqlite3
from pathlib import Path

def add_image_paths_to_db(database_path, image_dir):
    """
    Adds file paths of images to the granule database.

    Args:
        database_path (str): Path to the SQLite database file.
        image_dir (str): Directory containing image files.
    """
    try:
        # Connect to the database
        conn = sqlite3.connect(database_path)
        cursor = conn.cursor()

        # Ensure the 'image_path' column exists
        cursor.execute("PRAGMA table_info(granules);")
        columns = [col[1] for col in cursor.fetchall()]
        if 'image_path' not in columns:
            cursor.execute("ALTER TABLE granules ADD COLUMN image_path TEXT;")
            print("Added 'image_path' column to 'granules' table.")

        # Traverse the image directory and match granules
        for root, _, files in os.walk(image_dir):
            for file in files:
                if file.endswith(('.tif', '.TIF')):  # Adjust extensions if needed
                    file_path = Path(root) / file
                    granule_name = file_path.stem

                    # Update the database with the image path
                    cursor.execute(
                        "UPDATE granules SET image_path = ? WHERE [Granule Name] = ?;",
                        (str(file_path), granule_name)
                    )
                    if cursor.rowcount > 0:
                        print(f"Updated database for granule: {granule_name}")

        # Commit changes and close connection
        conn.commit()
        conn.close()
        print("Database updated successfully with image paths.")

    except sqlite3.Error as e:
        print(f"SQLite error: {e}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    import argparse

    # Argument parser
    parser = argparse.ArgumentParser(description="Add image paths to granule database.")
    parser.add_argument('--db', required=True, help="Path to the SQLite database file.")
    parser.add_argument('--image_dir', required=True, help="Directory containing the image files.")
    args = parser.parse_args()

    # Run the function with provided arguments
    add_image_paths_to_db(args.db, args.image_dir)
