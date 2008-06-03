"""SQLite in-memory storage. Mostly for testing purposes now."""

try:
    import sqlite3 as sqlite
except ImportError:
    from pysqlite2 import dbapi2 as sqlite

def DB():
    """Connects to the database and returns the connection"""
    db = sqlite.connect('db', timeout=99999999)
    # allows us to select by column name instead of just by index
    db.row_factory = sqlite.Row
    return db