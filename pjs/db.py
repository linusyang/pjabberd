"""SQLite in-memory storage. Mostly for testing purposes now."""

try:
    import sqlite3 as sqlite
except ImportError:
    from pysqlite2 import dbapi2 as sqlite
    
db = sqlite.connect(':memory:')
db.row_factory = sqlite.Row