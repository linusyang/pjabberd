"""Various connections that the server uses. Most important are the
Client and Server connections. There's also a local trigger connection
(see its doc for more details).

See the design doc for more information on asynchronous connections.
"""

import pjs.async.core as asyncore
import pjs.parsers
import logging
import socket

from pjs.elementtree.ElementTree import Element
from pjs.events import Dispatcher

# TODO: add TLS here through tlslite's asyncore integration.
#from tlslite.integration.TLSAsyncDispatcherMixIn import TLSAsyncDispatcherMixIn

class Connection(asyncore.dispatcher_with_send):
    """Represents a connection between two endpoints"""
    def __init__(self, sock, addr, server):
        asyncore.dispatcher_with_send.__init__(self, sock)
        self.sock = sock
        self.addr = addr
        self.server = server
        self.id = id(self) # this is referenced in msg processing queues
                           # and servers

        self.parser = pjs.parsers.borrow_parser(self)

        # per-connection data. can be accessed by handlers.
        self.data = {}
        self.data['stream'] = {
                               'in-stream' : False, # False before <stream> sent and after </stream>
                               'id' : '',
                               'closing' : False, # True if in the process of closing connection
                               }
        self.data['sasl'] = {
                             'mech' : 'DIGEST-MD5', # or PLAIN
                             'mechObj' : None, # <reference to one of SASL mech objects>
                             'complete' : False,
                             'in-progress' : False,
                             }
        self.data['iqauth'] = {
                               'mech' : 'digest', # or plain
                               'in-progress' : False,
                               'complete' : False,
                               }
        self.data['tls'] = {
                            'enabled' : False,
                            'complete' : False,
                            }

    def handle_expt(self):
        logging.warning("[%s] Socket exception occurred for %s",
                        self.__class__, self.addr)
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

        self.id = 'c%s' % id(self)

        if server.data['info']['type'] != 'c2s':
            raise Exception, "Trying to create a c2s connection with a non-c2s server"

        self.data['user'] = {
                             'jid' : '',
                             'resource' : '',
                             'in-session' : False, # True if <session> sent/accepted
                             'requestedRoster' : False, # True when sent the roster iq get
                                                        # when False, we shouldn't send it presence
                                                        # updates
                             'active' : False, # active resource is an available resource
                                               # that send an initial presence
                             'lastPresence' : None # last <presence> stanza sent by client
                             }

        logging.info("[%s] New c2s connection accepted from %s",
                     self.__class__, self.addr)

    def handle_close(self):
        # we want to be able to do stuff in handlers when the connection is
        # closed, so we dispatch into the 'stream-end' phase.

        # we set the tree to a dummy element so that the handlers could modify
        # it.
        if self.data['stream']['closing']:
            # already closing
            return
        wrapper = Element('wrapper')
        tree = Element('tag')
        wrapper.append(tree)
        Dispatcher().dispatch(wrapper, self, 'stream-end')

class ServerConnection(Connection):
    """A connection between two servers"""
    def __init__(self, sock, addr, server):
        Connection.__init__(self, sock, addr, server)

        if server.data['info']['type'] != 's2s':
            raise Exception, "Trying to create a s2s connection with a non-s2s server"

        self.data['server'] = {
                               'hostname' : '',
                               }

class ServerInConnection(ServerConnection):
    """An s2s connection to us from a remote server"""
    def __init__(self, sock, addr, server):
        ServerConnection.__init__(self, sock, addr, server)

        self.id = 'sin%s' % id(self)

        self.data['server']['direction'] = 'from'

        logging.info("New ServerInConnection created with %s", addr)

    def handle_close(self):
        hostname = self.data['server']['hostname']

        logging.debug("[%s] Closing ServerInConnection with %s",
                      self.__class__, hostname)

        if hostname:
            self.server.s2sConns[hostname][0] = None

        ServerConnection.handle_close(self)

    # FIXME: remove this
    def handle_read(self):
        data = self.recv(4096)
        self.parser.feed(data)

class ServerOutConnection(ServerConnection):
    """An s2s connection from us to a remote server"""
    def __init__(self, sock, addr, server):
        ServerConnection.__init__(self, sock, addr, server)

        self.id = 'sout%s' % id(self)

        self.data['server']['direction'] = 'to'

        # queue of messages to send to the remote server as soon as we are
        # ready (ie. completed auth, tls, db, etc.)
        self.outQueue = []

        logging.info("New ServerOutConnection created with %s", addr)

    def handle_close(self):
        hostname = self.data['server']['hostname']

        logging.debug("[%s] Closing ServerOutConnection with %s",
                      self.__class__, hostname)

        if hostname:
            self.server.s2sConns[hostname][1] = None

        ServerConnection.handle_close(self)

class LocalServerInConnection(ServerConnection):
    """Connection like ServerOutConnection, but for local S2S"""
    def __init__(self, sock, addr, server):
        ServerConnection.__init__(self, sock, addr, server)

        self.id = 'locsin%s' % id(self)

        self.data['server']['direction'] = 'from'
        self.data['server']['hostname'] = 'localhost'

        # send the <stream> to prime the parser for the ns it'll deal with,
        # but tell it not to process the xml during priming, since we don't
        # care for auth/encr on a loopback connection
        self.parser.disable()
        data = "<?xml version='1.0' ?>" +\
                "<stream:stream xmlns='jabber:server' " +\
                "xmlns:stream='http://etherx.jabber.org/streams' " +\
                "version='1.0'>"
        self.parser.feed(data)
        self.parser.depth = 1
        self.parser.stream = Element('{http://etherx.jabber.org/streams}stream',
                                     {'version' : '1.0'})
        self.parser.ns = 'jabber:server'
        self.parser.enable()

        logging.info("New LocalServerInConnection created with %s", addr)

    def handle_close(self):
        hostname = self.data['server']['hostname']

        logging.debug("[%s] Closing LocalServerConnection with %s",
                      self.__class__, hostname)

        if hostname:
            self.server.s2sConns[hostname] = (None, None)

        ServerConnection.handle_close(self)

    # FIXME: remove this
    def handle_read(self):
        data = self.recv(4096)
        self.parser.feed(data)

class LocalServerOutConnection(asyncore.dispatcher_with_send):
    """Simple server out connection for local S2S. All it does is
    forward all data sent to it to the LocalServerInConnection.
    """
    def __init__(self, sock):
        asyncore.dispatcher_with_send.__init__(self, sock)

        self.id = 'locsout%s' % id(self)

        logging.info("New LocalServerOutConnection created with %s", sock.getsockname())

    def handle_read(self):
        data = self.recv(4096)
        self.send(data)

    def handle_close(self):
        del self.server.conns[self.id]
        self.close()

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

        logging.info("[%s] New local trigger connection created",
                     self.__class__)

    def handle_expt(self):
        logging.warning("[%s] Socket exception occured for %s on local " +\
                        "trigger socket", self.__class__, self.addr)

    def handle_close(self):
        self.close()

    def handle_read(self): pass
    def handle_connect(self): pass
