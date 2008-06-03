import pjs.async.core
import pjs.threadpool as threadpool
import socket
import logging
import os, os.path, sys

from pjs.connection import Connection, LocalTriggerConnection
from pjs.async.core import dispatcher
from pjs.db import DB, sqlite

class Server(dispatcher):
    def __init__(self, ip, port):
        dispatcher.__init__(self)
        self.conns = []
        self.ip = ip
        self.hostname = ip
        self.port = port
        self.create_socket(socket.AF_INET, socket.SOCK_STREAM)
        self.set_reuse_addr()
        self.bind((ip, port))
        self.listen(5)
        
        # see connection.LocalTriggerConnection.__doc__ 
        self.localConn = LocalTriggerConnection(self.ip, self.port)
        
        def notifyFunc():
            self.localConn.send(' ')
        
        # TODO: make this configurable
        self.threadpool = threadpool.ThreadPool(5, notifyFunc=notifyFunc)
        
    def handle_accept(self):
        sock, addr = self.accept()
        conn = Connection(sock, addr, self)
        self.conns.append(conn)
        
    def handle_close(self):
        for c in self.conns:
            c.handle_close()
        self.close()
        
if __name__ == '__main__':

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
        c.execute("CREATE TABLE users (id INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,\
                                       jid TEXT NOT NULL,\
                                       username TEXT NOT NULL,\
                                       password TEXT NOT NULL,\
                                       UNIQUE(jid))")
        c.execute("INSERT INTO users (jid, username, password) VALUES ('tro@localhost', 'tro', 'test')")
    except sqlite.OperationalError, e:
        if e.message.find('already exists') >= 0: pass
        else: raise
    c.close()
    
    s = Server('localhost', 5222)
    
    logging.info('server started')
    
    try:
        pjs.async.core.loop()
    except KeyboardInterrupt:
        # clean up
        logging.info("KeyboardInterrupt sent. Shutting down...")
        logging.shutdown()
