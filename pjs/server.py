import pjs.threadpool as threadpool
import socket

from pjs.connection import Connection, LocalTriggerConnection, ClientConnection, ServerInConnection, ServerOutConnection
from pjs.async.core import dispatcher
from pjs.router import Router

class Server(dispatcher):
    def __init__(self, ip, port, launcher):
        dispatcher.__init__(self)
        self.launcher = launcher
        # maintains a mapping of connection ids to connections
        # this includes both c2s and s2s connections
        # used by dispatchers to look up connections
        # {connId => (JID, Connection)}
        self.conns = {}
        
        self.ip = ip
        self.hostname = ip
        self.port = port
        self.create_socket(socket.AF_INET, socket.SOCK_STREAM)
        self.set_reuse_addr()
        self.bind((ip, port))
        self.listen(5)
        
        # see connection.LocalTriggerConnection.__doc__
        self.triggerConn = LocalTriggerConnection(self.ip, self.port)
        
        def notifyFunc():
            self.triggerConn.send(' ')
        
        # TODO: make this configurable
        self.threadpool = threadpool.ThreadPool(5, notifyFunc=notifyFunc)
        
        # Server-wide data. ie. used for finding all connections for a certain
        # JID.
        # TODO: make this accessible even when the server's clustered
        #       ie. different machines should be able to access this.
        self.data = {}
        self.data['resources'] = {}
#        self.data['resources']['tro@localhost'] = {
#                                                   'resource' : <Connection obj>
#                                                   }
        self.data['info'] = {}
        
    def handle_accept(self):
        sock, addr = self.accept()
        conn = Connection(sock, addr, self)
        # we don't know the JID until client logs in
        self.conns[conn.id] = (None, conn)
        
    def handle_close(self):
        for c in self.conns:
            c[1].handle_close()
        self.close()

class C2SServer(Server):
    def __init__(self, ip, port, launcher):
        Server.__init__(self, ip, port, launcher)
        self.data['info']['type'] = 'c2s'
        
    def handle_accept(self):
        sock, addr = self.accept()
        conn = ClientConnection(sock, addr, self)
        # we don't know the JID until client logs in
        self.conns[conn.id] = (None, conn)

class S2SServer(Server):
    def __init__(self, ip, port, launcher):
        Server.__init__(self, ip, port, launcher)
        self.data['info']['type'] = 's2s'
        
        # {'domain' => [<Connection> for in, <Connection> for out]}
        self.s2sConns = {}
        
    def createOutConnection(self, sock):
        return ServerOutConnection(sock, sock.getsockname(), self)
        
    def handle_accept(self):
        sock, addr = self.accept()
        conn = ServerInConnection(sock, addr, self)
        # we don't know the hostname until stream starts
        self.conns[conn.id] = (None, conn)