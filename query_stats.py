import sqlite3

def count_granules_per_year(database_path):
    """Get the number of granules for each year."""
    query = """
        SELECT strftime('%Y', `Acquisition Date`) AS year, COUNT(*) AS count
        FROM granules
        GROUP BY year
        ORDER BY year;
    """
    with sqlite3.connect(database_path) as conn:
        result = conn.execute(query).fetchall()
    return result


def count_granules_per_orbit(database_path):
    """Get the number of granules for ascending vs descending orbits."""
    query = """
        SELECT `Ascending or Descending?` AS orbit, COUNT(*) AS count
        FROM granules
        GROUP BY orbit
        ORDER BY orbit;
    """
    with sqlite3.connect(database_path) as conn:
        result = conn.execute(query).fetchall()
    return result


def count_granules_per_path(database_path):
    """Get the number of granules for each path."""
    query = """
        SELECT `Path Number` AS path, COUNT(*) AS count
        FROM granules
        GROUP BY path
        ORDER BY path;
    """
    with sqlite3.connect(database_path) as conn:
        result = conn.execute(query).fetchall()
    return result
