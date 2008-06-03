"""All non-stanza-related handlers. This includes stream initiation, feature
negotiation etc. Auth is handled separately in auth.py.
"""

import logging
import socket
import pjs.threadpool as threadpool

from pjs.handlers.base import Handler, ThreadedHandler, chainOutput, poll
from pjs.handlers.write import prepareDataForSending
from pjs.utils import generateId, FunctionCall
from pjs.elementtree.ElementTree import Element, SubElement

class InStreamInitHandler(Handler):
    """Handler for initializing the stream when it was initiated by the
    remote side.
    """
    def handle(self, tree, msg, lastRetVal=None):
        # Expat removes the xmlns attributes, so we save them in the parser
        # class and check them here.
        ns = msg.conn.parser.ns

        if ns == 'jabber:client':
            streamType = 'client'
        elif ns == 'jabber:server':
            streamType = 'server'
        else:
            # TODO: send <bad-namespace-prefix/>
            logging.warning("[%s] Unknown stream namespace: %s",
                            self.__class__, ns)
            return lastRetVal

        # TODO: version check

        id = generateId()

        msg.conn.data['stream']['in-stream'] = True
        msg.conn.data['stream']['type'] = streamType
        msg.conn.data['stream']['id'] = id

        # no one should need to modify this, so we don't pass it along
        # to the next handler, but just add it to the socket write queue
        # commenting this out for now as it causes expat problems
        msg.addTextOutput(u"<?xml version='1.0'?>" + \
        #msg.addTextOutput(
                "<stream:stream from='%s' id='%s' xmlns='%s' "  \
                    % (msg.conn.server.hostname, id, ns) + \
                "xmlns:stream='http://etherx.jabber.org/streams' " + \
                "version='1.0'>")

class InStreamReInitHandler(Handler):
    """Handler for a remotely reinitialized stream, such as after TLS/SASL.
    It is assumed that an initial stream element was already sent some time
    ago.
    """
    def handle(self, tree, msg, lastRetVal=None):

        # The spec is silent on the case when a reinitialized <stream> is different
        # from the initial <stream>. In theory, there is never a need to change
        # any attributes in the new stream other than to change the ns prefix.
        # That seems like a dubious use case, so for now we just assume the stream
        # is the same as when it was first sent. This can be changed if it doesn't
        # play well with some clients.

        ns = msg.conn.parser.ns
        id = generateId()

        msg.conn.data['stream']['id'] = id

        msg.addTextOutput(u"<stream:stream from='%s' id='%s' xmlns='%s' "  \
                              % (msg.conn.server.hostname, id, ns) + \
                        "xmlns:stream='http://etherx.jabber.org/streams' " + \
                        "version='1.0'>")

        if msg.conn.data['tls']['complete']:
            # TODO: go to features-auth
            return lastRetVal

        if msg.conn.data['sasl']['complete']:
            msg.setNextHandler('write')
            msg.setNextHandler('features-postauth')
            return lastRetVal

        # TODO: go to features-init

class OutStreamInitHandler(Handler):
    """Handles the reply to our initiating s2s stream"""
    def handle(self, tree, msg, lastRetVal=None):
        # TODO: continue with features, auth, etc.
        # for now, just assume it's localhost

        # forward any queued messages for this connection
        out = prepareDataForSending(msg.conn.outQueue)
        return chainOutput(lastRetVal, out)

class FeaturesAuthHandler(Handler):
    """Handler for outgoing features after channel encryption."""
    def handle(self, tree, msg, lastRetVal=None):
        res = Element('stream:features')
        mechs = SubElement(res, 'mechanisms',
                           {'xmlns' : 'urn:ietf:params:xml:ns:xmpp-sasl'})
        SubElement(mechs, 'mechanism').text = 'DIGEST-MD5'
        SubElement(mechs, 'mechanism').text = 'PLAIN'

        # we also support the old style jabber:iq:auth
        SubElement(res, 'auth', {
                    'xmlns' : 'http://jabber.org/features/iq-auth'
                    })

        return chainOutput(lastRetVal, res)

# we don't have TLS for now
FeaturesInitHandler = FeaturesAuthHandler

class FeaturesPostAuthHandler(Handler):
    """Handler for outgoing features after authentication."""
    def handle(self, tree, msg, lastRetVal=None):
        res = Element('stream:features')
        SubElement(res, 'bind',
                   {'xmlns' : 'urn:ietf:params:xml:ns:xmpp-bind'})
        SubElement(res, 'session',
                   {'xmlns' : 'urn:ietf:params:xml:ns:xmpp-session'})

        return chainOutput(lastRetVal, res)

class NewS2SConnHandler(ThreadedHandler):
    """Creates a new outgoing s2s connection. Gets its data from
    the conn.data dict with key 'new-s2s-conn'.

    This is threaded because socket.connect will block.
    """
    def __init__(self):
        # this is true when the threaded handler returns
        self.done = False
        # used to pass the output to the next handler
        self.retVal = None

    def handle(self, tree, msg, lastRetVal=None):
        self.done = False
        self.retVal = lastRetVal
        tpool = msg.conn.server.threadpool

        def act():
            d = msg.conn.data
            if 'new-s2s-conn' not in d or \
                'hostname' not in d['new-s2s-conn'] or \
                'ip' not in d['new-s2s-conn']:
                logging.warning("[%s] Invoked without necessary data in connection",
                                self.__class__)
                return

            local = False
            if d['new-s2s-conn'].get('local'):
                local = True

            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.connect((d['new-s2s-conn']['ip'],
                          d['new-s2s-conn'].setdefault('port', 5269)))

            serv = msg.conn.server.launcher.getS2SServer()
            if not serv:
                logging.warning("[%s] Can't find an S2SServer in launcher",
                                self.__class__)
                return

            if local:
                conn = serv.createLocalOutConnection(sock)
                # if we're connecting to ourselves, we don't need the <stream>.
                # instead just send out the outQueue
                data = d['new-s2s-conn'].get('queue')
                if data is not None:
                    conn.send(prepareDataForSending(data))
            else:
                sOutConn = serv.createRemoteOutConnection(sock)

                # copy over any queued messages to send once fully connected
                sOutConn.outQueue.extend(d['new-s2s-conn'].setdefault('queue', []))

                # register the connection with the S2S server
                serverConns = serv.s2sConns.setdefault(d['new-s2s-conn']['hostname'], [None, None])
                serverConns[1] = sOutConn

                # send the initial stream
                # commenting this out for now as it causes expat problems
                sOutConn.send("<?xml version='1.0' ?>")
                sOutConn.send("<stream:stream xmlns='jabber:server' " +\
                              "xmlns:stream='http://etherx.jabber.org/streams' " +\
                              "to='%s' " % d['new-s2s-conn']['hostname'] + \
                              "version='1.0'>")

        def cb(workReq, retVal):
            self.done = True
            # we don't return anything, but make sure we pass the
            # lastRetVal along
            self.retVal = lastRetVal

        req = threadpool.makeRequests(act, None, cb)

        def checkFunc():
            # need to poll manually or the callback's never called from the pool
            poll(tpool)
            return self.done

        def initFunc():
            tpool.putRequest(req[0])

        return FunctionCall(checkFunc), FunctionCall(initFunc)

    def resume(self):
        return self.retVal

class StreamEndHandler(Handler):
    """Handles the other side closing the stream. For clients, this sends out
    the unavailable presence if the client was an active resource. For that
    case, the handler has to be able to modify the tree, so it has to be passed
    an existing Element as the tree, which it will alter and pass onto the
    presence handler.
    """
    def handle(self, tree, msg, lastRetVal=None):
        data = msg.conn.data
        closing = data['stream']['closing']
        if closing:
            # already closing the connection
            msg.stopChain = True
            return
        else:
            data['stream']['closing'] = True

        data['stream']['in-stream'] = False

        if data.has_key('user'):
            # closing stream for the client
            jid = data['user']['jid']
            resource = data['user']['resource']

            if data['user']['active']:
                # if the user has ever sent out the available presence, they're
                # an active resource. for these, we want to broadcast their
                # unavailable presence (3921 #5.1.5)

                assert isinstance(tree, Element)

                # we need to rewrite the tree to contain a faked unavailable
                # presence stanza
                tree.tag = 'presence'
                tree.set('type', 'unavailable')

                msg.setNextHandler('c2s-presence')

class CleanUpConnHandler(Handler):
    """This cleans up all connection data and closes the connection"""
    def handle(self, tree, msg, lastRetVal=None):
        conn = msg.conn
        data = msg.conn.data

        if data.has_key('user'):
            jid = data['user']['jid']
            resource = data['user']['resource']

            # the connection could've been closed before binding
            if jid and resource:
                del msg.conn.server.data['resources'][jid][resource]

        del conn.server.conns[conn.id]

        try:
            conn.parser.close()
        except:
            pass
        conn.parser.resetStream()

        logging.debug("[%s] Closing ClientConnection with %s",
                      self.__class__, jid)

        conn.close()
