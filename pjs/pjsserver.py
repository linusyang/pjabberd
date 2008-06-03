import pjs.conf.conf
import logging
import os, os.path, sys

from pjs.db import DB, sqlite

class PJSLauncher:
    """The one and only instance of the server. This controls all other
    components.
    """
    def __init__(self):
        self.servers = []
        
        self.c2sport = 5222
        self.s2sport = 5269
        
        self.hostname = 'localhost'
        
        self._c2s, self._s2s = (None, None)
        
    def run(self):
        from pjs.server import C2SServer, S2SServer
        self._c2s = C2SServer(self.hostname, self.c2sport, self)
        self.servers.append(self._c2s)
        
        self._s2s = S2SServer(self.hostname, self.s2sport, self)
        self.servers.append(self._s2s)
        
        from pjs.connection import LocalTriggerConnection
        
        # see connection.LocalTriggerConnection.__doc__
        self.triggerConn = LocalTriggerConnection(self.hostname, self.c2sport)
        
        def notifyFunc():
            self.triggerConn.send(' ')
            
        self._c2s.createThreadpool(5, notifyFunc)
        self._s2s.createThreadpool(5, notifyFunc)
        
    def stop(self):
        self.triggerConn.handle_close()
        self._c2s.handle_close()
        self._s2s.handle_close()
        
    def getC2SServer(self):
        return self._c2s
    def getS2SServer(self):
        return self._s2s

if __name__ == '__main__':
    launcher = PJSLauncher()
    pjs.conf.conf.launcher = launcher
    
    # TODO: move all of this into a config file + parser
    
    logFileName = 'server-log'
    logDir = 'log'
    logLoc = os.path.join(logDir, logFileName)
    logLevel = logging.DEBUG
    
    def configLogging(filename=logFileName, level=logLevel,
                     format='%(asctime)s %(levelname)-8s %(message)s'):
        try:
            logging.basicConfig(filename=filename, level=level, format=format)
        except IOError:
            print >> sys.stderr, 'Could not create a log file. Logging to stderr.'
            logging.basicConfig(level=level, format=format)
    
    if os.path.exists('log'):
        if os.path.isdir('log') and os.access('log', os.W_OK):
            configLogging(logLoc)
        else:
            print >> sys.stderr, 'Logging directory is not accessible'
            configLogging()
    else:
        try:
            os.mkdir('log')
            configLogging(logLoc)
        except IOError:
            print >> sys.stderr, 'Could not create logging directory'
            configLogging()
        
    con = DB()
    c = con.cursor()
    try:
        c.execute("CREATE TABLE jids (id INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,\
                                        jid TEXT NOT NULL,\
                                        password TEXT NOT NULL,\
                                        UNIQUE(jid))")
        c.execute("CREATE TABLE roster (userid INTEGER REFERENCES jids NOT NULL,\
                                        contactid INTEGER REFERENCES jids NOT NULL,\
                                        name TEXT,\
                                        subscription INTEGER DEFAULT 0,\
                                        PRIMARY KEY (userid, contactid)\
                                        )")
        c.execute("CREATE TABLE rostergroups (groupid INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,\
                                              userid INTEGER REFERENCES jids NOT NULL,\
                                              name TEXT NOT NULL,\
                                              UNIQUE(userid, name)\
                                              )")
        c.execute("CREATE TABLE rostergroupitems\
                    (groupid INTEGER REFERENCES rostergroup NOT NULL,\
                     contactid INTEGER REFERENCES jids NOT NULL,\
                     PRIMARY KEY (groupid, contactid))")
        c.execute("INSERT INTO jids (jid, password) VALUES ('tro@localhost', 'test')")
        c.execute("INSERT INTO jids (jid, password) VALUES ('dv@localhost', 'test')")
        c.execute("INSERT INTO jids (jid, password) VALUES ('bob@localhost', 'test')")
        c.execute("INSERT INTO jids (jid, password) VALUES ('alice@localhost', 'test')")
        con.commit()
#        c.execute("INSERT INTO roster (userid, contactid, subscription) VALUES (1, 2, 8)")
#        c.execute("INSERT INTO roster (userid, contactid, subscription) VALUES (2, 1, 8)")
#        c.execute("INSERT INTO rostergroups (userid, name) VALUES (1, 'friends')")
#        c.execute("INSERT INTO rostergroups (userid, name) VALUES (1, 'weirdos')")
#        c.execute("INSERT INTO rostergroupitems (groupid, contactid) VALUES (1, 2)")
    except sqlite.OperationalError, e:
        if e.message.find('already exists') >= 0: pass
        else: raise
    c.close()
    
    launcher.run()
    logging.info('server started')
    
    import pjs.async.core
    
    try:
        pjs.async.core.loop()
    except KeyboardInterrupt:
        # clean up
        logging.info("KeyboardInterrupt sent. Shutting down...")
        logging.shutdown()