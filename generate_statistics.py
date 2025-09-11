import sqlite3
import csv

def fetch_statistics(database_path, output_csv):
    """
    Fetch and save statistics about filtered granules from the database.

    Args:
        database_path (str): Path to the SQLite database file.
        output_csv (str): Path to save the output statistics CSV.
    """
    queries = {
        "time_duration": """
            SELECT 
                MIN([Acquisition Date]) AS Start_Date, 
                MAX([Acquisition Date]) AS End_Date 
            FROM granules;
        """,
        "total_granules": """
            SELECT COUNT(*) AS Total_Granules 
            FROM granules;
        """,
        "distinct_paths": """
            SELECT DISTINCT [Path Number] 
            FROM granules;
        """,
        "asc_desc_count_by_year": """
            SELECT 
                strftime('%Y', [Acquisition Date]) AS Year, 
                [Ascending or Descending?] AS Orbit, 
                COUNT(*) AS Count 
            FROM granules 
            GROUP BY Year, Orbit;
        """
    }

    statistics = {}
    paths = []

    try:
        # Connect to the database
        conn = sqlite3.connect(database_path)
        cursor = conn.cursor()

        # Time duration
        cursor.execute(queries["time_duration"])
        row = cursor.fetchone()
        statistics["Start Date"], statistics["End Date"] = row

        # Total granules
        cursor.execute(queries["total_granules"])
        statistics["Total Granules"] = cursor.fetchone()[0]

        # Distinct paths
        cursor.execute(queries["distinct_paths"])
        paths = [row[0] for row in cursor.fetchall()]
        statistics["Total Paths"] = len(paths)
        statistics["Path List"] = ", ".join(map(str, paths))

        # Ascending/Descending counts by year
        cursor.execute(queries["asc_desc_count_by_year"])
        asc_desc_by_year = cursor.fetchall()

        # Save the results to CSV
        with open(output_csv, mode="w", newline="") as csvfile:
            writer = csv.writer(csvfile)

            # Write general statistics
            writer.writerow(["Statistic", "Value"])
            writer.writerow(["Start Date", statistics["Start Date"]])
            writer.writerow(["End Date", statistics["End Date"]])
            writer.writerow(["Total Granules", statistics["Total Granules"]])
            writer.writerow(["Total Paths", statistics["Total Paths"]])
            writer.writerow(["Path List", statistics["Path List"]])
            writer.writerow([])  # Empty row

            # Write Ascending/Descending counts by year
            writer.writerow(["Year", "Orbit", "Count"])
            writer.writerows(asc_desc_by_year)

        print(f"Statistics saved to: {output_csv}")

    except sqlite3.Error as e:
        print(f"Database error: {e}")
    except Exception as e:
        print(f"Error: {e}")
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    # Database path and output CSV path
    database_path = "./LakeVictoria/filter_granule_data.db"
    output_csv = "./LakeVictoria/LakeVictoria_statistics.csv"

    fetch_statistics(database_path, output_csv)
