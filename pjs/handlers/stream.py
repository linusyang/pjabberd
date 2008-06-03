from pjs.handlers.base import Handler
from pjs.utils import generateId

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
            # log it
            return
        
        # TODO: version check
        
        id = generateId()
        
        msg.conn.data['stream'] = {
                                   'in-stream' : True,
                                   'type' : streamType,
                                   'id' : id
                                   }
        
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
        
        try:
            if msg.conn.data['tls']['complete']:
                # TODO: go to features-auth
                return
        except KeyError: pass
        
        try:
            if msg.conn.data['sasl']['complete']:
                msg.setNextHandler('write')
                msg.setNextHandler('features-postauth')
                return
        except KeyError: pass
        
        # TODO: go to features-init

class FeaturesAuthHandler(Handler):
    """Handler for outgoing features after channel encryption."""
    def handle(self, tree, msg, lastRetVal=None):
        res = u"<stream:features>" + \
                "<mechanisms xmlns='urn:ietf:params:xml:ns:xmpp-sasl'>" + \
                "<mechanism>PLAIN</mechanism>" + \
                "</mechanisms></stream:features>"
                
        msg.addTextOutput(res)
        
# we don't have TLS for now
FeaturesInitHandler = FeaturesAuthHandler
        
class FeaturesPostAuthHandler(Handler):
    """Handler for outgoing features after authentication."""
    def handle(self, tree, msg, lastRetVal=None):
        res = u"<stream:features><bind xmlns='urn:ietf:params:xml:ns:xmpp-bind'/>" +\
                "<session xmlns='urn:ietf:params:xml:ns:xmpp-session'/>" +\
                "</stream:features>"
                
        msg.addTextOutput(res)

class StreamEndHandler(Handler):
    """Handler for closing the stream"""

    def handle(self, tree, msg, lastRetVal=None):
        msg.conn.data['stream']['in-stream'] = False