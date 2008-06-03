"""SQLite in-memory storage. Mostly for testing purposes now.
This can be replaced by rewriting the relevant classes and using them
in your own custom handlers.
"""

from pysqlite2 import dbapi2 as sqlite

dbname = 'db'

def DB(name=None, isolationLevel="DEFERRED"):
    """Connects to the database and returns the connection. Uses the default
    isolation level (DEFERRED).
    name -- DB name. This is cached until it's changed, so if the same DB is
            being accessed, just call DB()
    isolationLevel -- None for autocommit. Otherwise, either "DEFERRED",
                      "IMMEDIATE" or "EXCLUSIVE"
    """
    global dbname
    if not name:
        n = dbname
    else:
        n = dbname = name
    db = sqlite.connect(n, timeout=10.0, isolation_level=isolationLevel)
    # allows us to select by column name instead of just by index
    db.row_factory = sqlite.Row
    return db

def DBautocommit():
    """Connects to the database and returns the connection. Uses the autocommit
    isolation level.
    """
    return DB(isolationLevel=None)

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