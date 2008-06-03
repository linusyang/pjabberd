"""Server classes. These bind to sockets and accept connections from client
and servers and create the appropriate Connection instances.
"""

import pjs.threadpool as threadpool
import socket

from pjs.connection import Connection, ClientConnection, \
                           ServerInConnection, ServerOutConnection, \
                           LocalServerInConnection, LocalServerOutConnection
from pjs.async.core import dispatcher
from pjs.utils import SynchronizedDict

class Server(dispatcher):
    """General server that accepts connections, creates threadpools and stores
    some server-wide data.
    """
    def __init__(self, ip, port, launcher):
        """Binds to a socket.

        ip -- IP of this server.
        port -- port on which to listen for connections.
        launcher -- reference to the main launcher process. This is how
                    handlers can get to the main launcher.
        """
        # TODO: reevaluate the launcher. We may not need it here at all
        # and handlers shouldn't be accessing the main process anyway.

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

        # sometimes binding takes a couple of tries if the server was quickly
        # restarted
        for i in range(3):
            try:
                self.create_socket(socket.AF_INET, socket.SOCK_STREAM)
                self.set_reuse_addr()
                self.bind((ip, port))
                break
            except socket.error, e:
                if i == 2: raise

        self.listen(5)

        # Server-wide data. ie. used for finding all connections for a certain
        # JID.
        # TODO: make this accessible even when the server's clustered
        #       ie. different machines should be able to access this.
        #self.data = SynchronizedDict()
        self.data = {}
        self.data['info'] = {}


    def createThreadpool(self, numWorkers, notifyFunc=None):
        """Initializes a threadpool with numWorkers in it. notifyFunc
        will be called after each job in the pool completes.
        """
        self.threadpool = threadpool.ThreadPool(numWorkers, notifyFunc=notifyFunc)

    def handle_accept(self):
        """Accepts an S2S connection"""
        sock, addr = self.accept()
        conn = Connection(sock, addr, self)
        # we don't know the JID until client logs in
        self.conns[conn.id] = (None, conn)

    def handle_close(self, unconditionalClose=False):
        """Shuts down this server. If unconditionalClose is True doesn't
        attempt to close individual connections on this server.
        """
        if unconditionalClose:
            self.close()
            return

        self.close()
        for c in self.conns:
            self.conns[c][1].handle_close()

class C2SServer(Server):
    """Server that handles incoming C2S connections from local clients"""
    def __init__(self, ip, port, launcher):
        """Creates a C2S server. See Server.__doc__"""
        Server.__init__(self, ip, port, launcher)

        self.data['resources'] = {}
#        example:
#        self.data['resources']['tro@localhost'] = {
#                                                   'resource' : <Connection obj>
#                                                   }
        self.data['info']['type'] = 'c2s'

    def handle_accept(self):
        """Accepts a C2S connection"""
        sock, addr = self.accept()
        conn = ClientConnection(sock, addr, self)
        # we don't know the JID until client logs in
        self.conns[conn.id] = (None, conn)

class S2SServer(Server):
    """Server that handles incoming S2S connections from local and remote
    servers. It also is able to create outgoing S2S connections.
    """
    def __init__(self, ip, port, launcher):
        """Creates an S2S server. See Server.__doc__"""
        Server.__init__(self, ip, port, launcher)
        self.data['info']['type'] = 's2s'

        # {'domain' => [<Connection> for in, <Connection> for out]}
        #self.s2sConns = SynchronizedDict()
        self.s2sConns = {}

    def createRemoteOutConnection(self, sock):
        """Creates an outgoing connection to a remote server"""
        conn = ServerOutConnection(sock, sock.getpeername(), self)
        self.conns[conn.id] = ('localhost-out', conn)
        return conn

    def createLocalOutConnection(self, sock):
        """Creates an outgoing connection to a local server"""
        conn = LocalServerOutConnection(sock)
        self.conns[conn.id] = (conn.id, conn)
        self.s2sConns.setdefault('localhost', [None, None])[1] = conn

        return conn

    def handle_accept(self):
        """Accepts an S2S connection"""
        sock, addr = self.accept()
        if addr[0] == '127.0.0.1':
            conn = LocalServerInConnection(sock, addr, self)
        else:
            conn = ServerInConnection(sock, addr, self)
        # TODO: don't assume localhost here
        self.s2sConns.setdefault('localhost', [None, None])[0] = conn
        # we don't know the hostname until stream starts
        self.conns[conn.id] = ('localhost-in', conn)
