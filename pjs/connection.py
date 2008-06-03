import pjs.async.core as asyncore
import pjs.parsers as parsers
import logging
import socket

from pjs.elementtree.ElementTree import Element
#from tlslite.integration.TLSAsyncDispatcherMixIn import TLSAsyncDispatcherMixIn

class Connection(asyncore.dispatcher_with_send):
    """Represents a connection between two endpoints"""
    def __init__(self, sock, addr, server):
        asyncore.dispatcher_with_send.__init__(self, sock)
        self.sock = sock
        self.addr = addr
        self.server = server
        self.id = id(self)
        
        self.parser = parsers.borrow_parser(self)
        
        # per-connection data. can be accessed by handlers.
        self.data = {}
        self.data['stream'] = {
                               'in-stream' : False, # False before <stream> sent and after </stream>
                               'id' : '',
                               }
        self.data['sasl'] = {
                             'mech' : 'DIGEST-MD5', # or PLAIN
                             'mechObj' : None, # <reference to one of SASL mech objects>
                             'complete' : False,
                             }
        self.data['tls'] = {
                            'enabled' : False,
                            'complete' : False,
                            }
        
    def handle_expt(self):
        logging.warning("Socket exception occurred for %s", self.addr)
        self.handle_close()
    
    def handle_close(self):
        del self.server.conns[self.id]
        
        try:
            self.parser.close()
        except:
            pass
        self.parser.resetStream()
        self.close()
        
    def handle_read(self):
        data = self.recv(4096)
        self.parser.feed(data)
        
class ClientConnection(Connection):
    """A connection between a client and a server (us) initiated by
    the client.
    """
    def __init__(self, sock, addr, server):
        Connection.__init__(self, sock, addr, server)
        
        if server.data['info']['type'] != 'c2s':
            raise Exception, "Trying to create a c2s connection with a non-c2s server"
        
        self.data['user'] = {
                             'jid' : '',
                             'resource' : '',
                             'in-session' : False, # True if <session> sent/accepted
                             'requestedRoster' : False, # True when sent the roster iq get
                                                        # when False, we shouldn't send it presence
                                                        # updates
                             }
        
        logging.info("New c2s connection accepted from %s", self.addr)
        
    def handle_close(self):
        # this resource is no longer connected
        jid = self.data['user']['jid']
        resource = self.data['user']['resource']
        del self.server.data['resources'][jid][resource]
        
        Connection.handle_close(self)

class ServerConnection(Connection):
    """A connection between two servers"""
    def __init__(self, sock, addr, server):
        Connection.__init__(self, sock, addr, server)
        
        if server.data['info']['type'] != 's2s':
            raise Exception, "Trying to create a s2s connection with a non-s2s server"
        
        self.data['server'] = {
                               'hostname' : '',
                               }
        
        logging.info("New s2s connection accepted from %s", self.addr)
        
class ServerInConnection(ServerConnection):
    """An s2s connection to us from a remote server"""
    def __init__(self, sock, addr, server):
        ServerConnection.__init__(self, sock, addr, server)
        
        self.data['server']['direction'] = 'from'
        
    def handle_close(self):
        hostname = self.data['server']['hostname']
        if hostname:
            self.server.s2sConns[hostname][0] = None
        
        Connection.handle_close(self)
        
class ServerOutConnection(ServerConnection):
    """An s2s connection from us to a remote server"""
    def __init__(self, sock, addr, server):
        ServerConnection.__init__(self, sock, addr, server)
        
        self.data['server']['direction'] = 'to'
        
        # queue of messages to send to the remote server as soon as we are
        # ready (ie. completed auth, tls, db, etc.)
        self.outQueue = []
        
    def handle_close(self):
        hostname = self.data['server']['hostname']
        if hostname:
            self.server.s2sConns[hostname][1] = None
        
        Connection.handle_close(self)

class LocalTriggerConnection(asyncore.dispatcher_with_send):
    """This creates a local connection back to our server.
    
    This should never be used to send any real data. This is used by the
    threadpool code to trigger a wake-up to asyncore, which could go to sleep
    for as long as 30 seconds when there is no data on the wire, which is a
    problem when we have threads finishing work in the pools. The callbacks
    need to be executed from the main thread with threadpool.poll() in order
    to proceed with message handling, but this can't happen when asyncore is
    asleep. So, each WorkThread sends a single space on this connection, which
    causes asyncore to wake up and process the event, thereby triggering
    function watching (which usually includes a threadpool.poll() call).
    """
    def __init__(self, ip, port):
        asyncore.dispatcher_with_send.__init__(self)
        
        self.create_socket(socket.AF_INET, socket.SOCK_STREAM)
        self.connect((ip, port))
        
        logging.info("New local trigger connection created")
        
    def handle_expt(self):
        logging.warning("Socket exception occured for %s on local trigger socket", self.addr)
    
    def handle_close(self):
        del self.server.conns[self.id]
        self.close()
        
    def handle_read(self): pass
    def handle_connect(self): pass
