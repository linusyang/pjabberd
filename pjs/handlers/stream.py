import logging

from pjs.handlers.base import Handler, chainOutput
from pjs.utils import generateId
from pjs.elementtree.ElementTree import Element, SubElement

class StreamInitHandler(Handler):
    """Handler for initializing the stream"""
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
            logging.warning("Unknown stream namespace: %s", ns)
            return lastRetVal
        
        # TODO: version check
        
        id = generateId()
        
        msg.conn.data['stream']['in-stream'] = True
        msg.conn.data['stream']['type'] = streamType
        msg.conn.data['stream']['id'] = id
        
        # no one should need to modify this, so we don't pass it along
        # to the next handler, but just add it to the socket write queue
        msg.addTextOutput(u"<?xml version='1.0'?>" + \
                "<stream:stream from='%s' id='%s' xmlns='%s' "  \
                    % (msg.conn.server.hostname, id, ns) + \
                "xmlns:stream='http://etherx.jabber.org/streams' " + \
                "version='1.0'>")
        
class StreamReInitHandler(Handler):
    """Handler for a reinitialized stream, such as after TLS/SASL. It is
    assumed that an initial stream element was already sent some time ago.
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

class FeaturesAuthHandler(Handler):
    """Handler for outgoing features after channel encryption."""
    def handle(self, tree, msg, lastRetVal=None):
        res = Element('stream:features')
        mechs = SubElement(res, 'mechanisms',
                           {'xmlns' : 'urn:ietf:params:xml:ns:xmpp-sasl'})
        SubElement(mechs, 'mechanism').text = 'DIGEST-MD5'
        SubElement(mechs, 'mechanism').text = 'PLAIN'
        
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

class StreamEndHandler(Handler):
    """Handler for closing the stream"""

    def handle(self, tree, msg, lastRetVal=None):
        msg.conn.data['stream']['in-stream'] = False