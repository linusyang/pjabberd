from pjs.connection import Connection
from pjs.async.core import dispatcher
import pjs.async.core
import socket
from pjs.db import db

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
        
    def handle_accept(self):
        sock, addr = self.accept()
        conn = Connection(sock, addr, self)
        self.conns.append(conn)
        
    def handle_close(self):
        for c in self.conns:
            c.handle_close()
        self.close()
        
if __name__ == '__main__':
    
    c = db.cursor()
    c.execute("CREATE TABLE users (id INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,\
                                   jid TEXT NOT NULL,\
                                   username TEXT NOT NULL,\
                                   password TEXT NOT NULL,\
                                   UNIQUE(jid))")
    c.execute("INSERT INTO users (jid, username, password) VALUES ('tro@localhost', 'tro', 'test')")
    c.close()
    
    s = Server('localhost', 44444)
    pjs.async.core.loop()