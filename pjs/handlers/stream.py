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
        
        return "<?xml version='1.0'?>" + \
                "<stream:stream from='%s' id='%s' xmlns='%s' "  \
                    % (msg.conn.server.hostname, id, ns) + \
                "xmlns:stream='http://etherx.jabber.org/streams' " + \
                "version='1.0'>"
        
class StreamCloseHandler(Handler):
    """Handler for closing the stream"""
    def __init__(self):
        pass
    
    def handle(self, tree, msg, lastRetVal=None):
        msg.conn.data['stream']['in-stream'] = False