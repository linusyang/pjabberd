from pjs.handlers.base import Handler
from pjs.utils import generateId

class StreamInitHandler(Handler):
    """Handler for initializing the stream"""
    def __init__(self):
        pass

    def handle(self, tree, msg, lastRetVal=None):
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

class FeaturesOutHandler(Handler):
    """Handler for outgoing features. Announces the available features."""
    def __init__(self):
        pass
    
    def handle(self, tree, msg, lastRetVal=None):
        res = u''
        if lastRetVal:
            res += lastRetVal
        
        res += "<stream:features>" + \
                "<mechanisms xmlns='urn:ietf:params:xml:ns:xmpp-sasl'>" + \
                "<mechanism>PLAIN</mechanism>" + \
                "</mechanisms></stream:features>"
                
        msg.addTextOutput(res)

class StreamCloseHandler(Handler):
    """Handler for closing the stream"""
    def __init__(self):
        pass
    
    def handle(self, tree, msg, lastRetVal=None):
        msg.conn.data['stream']['in-stream'] = False