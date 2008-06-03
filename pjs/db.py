"""SQLite in-memory storage. Mostly for testing purposes now."""
    
from pysqlite2 import dbapi2 as sqlite

def DB(isolationLevel="DEFERRED"):
    """Connects to the database and returns the connection. Uses the default
    isolation level (DEFERRED).
    isolationLevel -- None for autocommit. Otherwise, either "DEFERRED",
                      "IMMEDIATE" or "EXCLUSIVE"
    """
    db = sqlite.connect('db', timeout=10.0, isolation_level=isolationLevel)
    # allows us to select by column name instead of just by index
    db.row_factory = sqlite.Row
    return db

def DBautocommit():
    """Connects to the database and returns the connection. Uses the autocommit
    isolation level.
    """
    return DB(None)

def commitSQLiteTransaction(con, cursor):
    """Tries to commit the transaction opened in connection 'con' and close
    the 'cursor'. If commit fails, attempts to rollback. Does nothing if
    rollback fails.
    Returns True if committed; raises the DB exception if failed.
    """
    try:
        con.commit()
    except Exception, e:
        try:
            con.rollback()
        except: pass
        cursor.close()
        raise e
    
    cursor.close()
    return True