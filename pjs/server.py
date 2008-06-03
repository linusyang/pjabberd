import pjs.threadpool as threadpool
import socket

from pjs.connection import Connection, ClientConnection, \
                           ServerInConnection, ServerOutConnection, \
                           LocalServerInConnection, LocalServerOutConnection
from pjs.async.core import dispatcher
from pjs.utils import SynchronizedDict

class Server(dispatcher):
    def __init__(self, ip, port, launcher):
        dispatcher.__init__(self)
        self.launcher = launcher
        # maintains a mapping of connection ids to connections
        # this includes both c2s and s2s connections
        # used by dispatchers to look up connections
        # {connId => (JID, Connection)}
        #self.conns = SynchronizedDict()
        self.conns = {}
        
        self.ip = ip
        self.hostname = ip
        self.port = port
        self.create_socket(socket.AF_INET, socket.SOCK_STREAM)
        self.set_reuse_addr()
        self.bind((ip, port))
        self.listen(5)
        
        # Server-wide data. ie. used for finding all connections for a certain
        # JID.
        # TODO: make this accessible even when the server's clustered
        #       ie. different machines should be able to access this.
        #self.data = SynchronizedDict()
        self.data = {}
        self.data['info'] = {}
        
        
    def createThreadpool(self, numWorkers, notifyFunc=None):
        self.threadpool = threadpool.ThreadPool(numWorkers, notifyFunc=notifyFunc)
        
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

        self.data['resources'] = {}
#        self.data['resources']['tro@localhost'] = {
#                                                   'resource' : <Connection obj>
#                                                   }
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
        #self.s2sConns = SynchronizedDict()
        self.s2sConns = {}
        
    def createOutConnection(self, sock):
        conn = ServerOutConnection(sock, sock.getpeername(), self)
        self.conns[conn.id] = ('localhost-out', conn)
        return conn
    
    def createLocalConnection(self, sock):
        conn = LocalServerOutConnection(sock)
        self.conns[conn.id] = (conn.id, conn)
        self.s2sConns.setdefault('localhost', [None, None])[1] = conn
        
        return conn
        
    def handle_accept(self):
        sock, addr = self.accept()
        if addr[0] == '127.0.0.1':
            conn = LocalServerInConnection(sock, addr, self)
        else:
            conn = ServerInConnection(sock, addr, self)
        # TODO: don't assume localhost here
        self.s2sConns.setdefault('localhost', [None, None])[0] = conn
        # we don't know the hostname until stream starts
        self.conns[conn.id] = ('localhost-in', conn)
