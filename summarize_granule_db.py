import sqlite3
import csv
from pathlib import Path

def query_database(database_path, queries):
    """Executes a set of SQL queries on the database and returns the results."""
    results = {}
    try:
        conn = sqlite3.connect(database_path)
        cursor = conn.cursor()
        for query_name, query in queries.items():
            cursor.execute(query)
            results[query_name] = cursor.fetchall()
        conn.close()
    except Exception as e:
        print(f"Error querying database: {e}")
    return results

def summarize_database(database_path, output_csv):
    """Summarizes the database and writes the results to a CSV file."""
    queries = {
        "start_end_date": """
            SELECT 
                MIN([Acquisition Date]) AS Start_Date, 
                MAX([Acquisition Date]) AS End_Date 
            FROM granules;
        """,
        "total_granules": """
            SELECT COUNT(*) AS Total_Granules 
            FROM granules;
        """,
        "unique_paths": """
            SELECT DISTINCT [Path Number] 
            FROM granules;
        """,
        "asc_desc_count_by_year": """
            SELECT 
                strftime('%Y', [Acquisition Date]) AS Year, 
                [Ascending or Descending?] AS Orbit, 
                COUNT(*) AS Total 
            FROM granules 
            GROUP BY Year, Orbit;
        """,
    }

    results = query_database(database_path, queries)

    # Extract data from query results
    start_date, end_date = results["start_end_date"][0]
    total_granules = results["total_granules"][0][0]
    unique_paths = [row[0] for row in results["unique_paths"]]
    asc_desc_counts = results["asc_desc_count_by_year"]

    # Prepare summary data
    summary_data = {
        "Start Date": start_date,
        "End Date": end_date,
        "Total Granules": total_granules,
        "Unique Paths": len(unique_paths),
        "Path List": ", ".join(map(str, unique_paths)),
        "Ascending/Descending Counts": asc_desc_counts,
    }

    # Write summary to CSV
    output_path = Path(output_csv)
    with open(output_path, "w", newline="") as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(["Metric", "Value"])

        # Write general statistics
        writer.writerow(["Start Date", summary_data["Start Date"]])
        writer.writerow(["End Date", summary_data["End Date"]])
        writer.writerow(["Total Granules", summary_data["Total Granules"]])
        writer.writerow(["Unique Paths", summary_data["Unique Paths"]])
        writer.writerow(["Path List", summary_data["Path List"]])

        # Write ascending/descending counts by year
        writer.writerow([])  # Blank line
        writer.writerow(["Year", "Orbit", "Total"])
        for row in summary_data["Ascending/Descending Counts"]:
            writer.writerow(row)

    print(f"Summary written to {output_path}")

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Summarize granule database.")
    parser.add_argument("--db", required=True, help="Path to the SQLite database file.")
    parser.add_argument("--output_csv", required=True, help="Path to the output CSV file.")
    args = parser.parse_args()

    summarize_database(args.db, args.output_csv)
