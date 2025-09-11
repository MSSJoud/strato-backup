import sqlite3
import pandas as pd
from pathlib import Path

def query_database(database_path, query):
    """Query the database and return results as a DataFrame."""
    conn = sqlite3.connect(database_path)
    result = pd.read_sql_query(query, conn)
    conn.close()
    return result

def generate_statistics(granules):
    """Generate statistics for the selected granules."""
    total_granules = len(granules)
    total_size = granules['Size (MB)'].sum()
    
    ascending = granules[granules['Ascending or Descending?'] == 'ASCENDING']
    descending = granules[granules['Ascending or Descending?'] == 'DESCENDING']
    
    stats = {
        'Total Granules': total_granules,
        'Total Size (MB)': total_size,
        'Ascending Granules': len(ascending),
        'Descending Granules': len(descending),
        'Ascending Size (MB)': ascending['Size (MB)'].sum(),
        'Descending Size (MB)': descending['Size (MB)'].sum()
    }
    return stats

def list_paths(granules):
    """List unique paths for ascending and descending orbits."""
    ascending_paths = sorted(granules[granules['Ascending or Descending?'] == 'ASCENDING']['Path Number'].unique())
    descending_paths = sorted(granules[granules['Ascending or Descending?'] == 'DESCENDING']['Path Number'].unique())
    return ascending_paths, descending_paths

def save_granules_to_csv(granules, output_dir):
    """Save the filtered granules to a CSV file."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    output_file = output_dir / "filter_granules.csv"
    granules.to_csv(output_file, index=False)
    print(f"Filtered granules saved to: {output_file}")

if __name__ == "__main__":
    db_path = "AOI-2_1-DB.db"
    output_dir = "./LakeVictoria"
    
    # Query for granules over Lake Victoria in 2023-2024
    lake_query = """
    SELECT * 
    FROM granules
    WHERE strftime('%Y-%m-%d', [Acquisition Date]) BETWEEN '2023-10-15' AND '2024-10-15'
      AND [Near Start Lat] >= -2.5 AND [Near Start Lat] <= -1.0
      AND [Near Start Lon] >= 32.0 AND [Near Start Lon] <= 33.5;
    """
    granules = query_database(db_path, lake_query)
    
    if granules.empty:
        print("No granules found for the specified filter.")
    else:
        print(f"Found {len(granules)} granules.")

        # Generate and display statistics
        stats = generate_statistics(granules)
        print("\nStatistics:")
        for key, value in stats.items():
            print(f"{key}: {value}")
        
        # List paths for ascending and descending orbits
        asc_paths, desc_paths = list_paths(granules)
        print("\nAscending Paths:", asc_paths)
        print("Descending Paths:", desc_paths)

        # Save granules to CSV
        save_granules_to_csv(granules, output_dir)
