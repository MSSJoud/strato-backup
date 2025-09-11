import sqlite3

db_path = './LakeVictoria/filter_granule_data.db'

def check_database(db_path):
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # List all tables
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = cursor.fetchall()

        if tables:
            print("Tables in the database:")
            for table in tables:
                print(f"- {table[0]}")
        else:
            print("No tables found in the database.")

        conn.close()
    except sqlite3.Error as e:
        print(f"Error checking database: {e}")

if __name__ == "__main__":
    check_database(db_path)
