import sqlite3
import pandas as pd

# Define the function to query the database and save filtered information
def query_filter_statistics(database_path, output_csv):
    # Connect to the SQLite database
    conn = sqlite3.connect(database_path)
    
    # Queries to extract desired information
    queries = {
        "time_duration": "SELECT MIN([Acquisition Date]) AS Start_Date, MAX([Acquisition Date]) AS End_Date FROM granules;",
        "total_granules": "SELECT COUNT(*) AS Total_Granules FROM granules;",
        "path_numbers": "SELECT DISTINCT [Path Number] FROM granules;",
        "asc_desc_by_year": "SELECT strftime('%Y', [Acquisition Date]) AS Year, [Ascending or Descending?], COUNT(*) AS Total FROM granules GROUP BY Year, [Ascending or Descending?];"
    }

    # Execute queries and store results
    results = {}
    for key, query in queries.items():
        try:
            results[key] = pd.read_sql_query(query, conn)
        except Exception as e:
            print(f"Error executing query for {key}: {e}")

    # Close the connection
    conn.close()

    # Process and save the results
    try:
        # Extract time duration
        time_duration = results["time_duration"]
        start_date = time_duration.iloc[0]["Start_Date"]
        end_date = time_duration.iloc[0]["End_Date"]

        # Extract total granules
        total_granules = results["total_granules"].iloc[0]["Total_Granules"]

        # Extract path numbers
        path_numbers = results["path_numbers"]["Path Number"].tolist()

        # Extract asc/desc counts by year
        asc_desc_by_year = results["asc_desc_by_year"]
        asc_desc_summary = asc_desc_by_year.groupby(["Year", "Ascending or Descending?"]).sum().reset_index()

        # Save all results to a CSV
        summary = {
            "Start Date": [start_date],
            "End Date": [end_date],
            "Total Granules": [total_granules],
            "Path Numbers": [path_numbers],
        }
        summary_df = pd.DataFrame(summary)
        summary_df.to_csv(output_csv, index=False)

        asc_desc_summary.to_csv(output_csv.replace(".csv", "_asc_desc_by_year.csv"), index=False)

        print(f"Summary saved to {output_csv}")
        print(f"Ascending/Descending by year saved to {output_csv.replace('.csv', '_asc_desc_by_year.csv')}")

    except Exception as e:
        print(f"Error processing and saving results: {e}")

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Query filtered granules statistics and save to CSV.")
    parser.add_argument("--db", required=True, help="Path to the SQLite database file.")
    parser.add_argument("--output_csv", required=True, help="Path to the output CSV file.")
    args = parser.parse_args()

    query_filter_statistics(args.db, args.output_csv)
