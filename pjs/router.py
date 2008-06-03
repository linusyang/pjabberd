import logging
import pjs.conf.conf

from pjs.elementtree.ElementTree import Element
from pjs.handlers.write import prepareDataForSending
from pjs.jid import JID

class Router:
    """Handles routing of outgoing messages"""
    
    def __init__(self, hostname):
        """Initialize the router with a pointer to the server"""
        self.hostname = hostname
    
    def route(self, msg, to=None):
        """Routes 'msg' to its recipient. 'To' should be a bare JID. If 'to'
        is not specified, the relevant information is extracted from 'msg'.
        If that fails, the method returns False.
        """
        # TODO: implement S2S
        # for now, just route to ourselves
        if not to:
            if isinstance(msg, Element):
                to = msg.get('to')
                if not to:
                    return False
            else:
                # can't extract routing information
                return False
            
        try:
            jid = JID(to)
        except Exception, e:
            logging.warning(e)
            return False
        
        if jid.domain == self.hostname:
            conns = pjs.conf.conf.server.conns
            if jid.resource:
                # locate the resource of this JID
                def f(i):
                    return conns[i][0] == jid
            else:
                # locate all active resources of this JID
                def f(i):
                    jidConn = conns[i]
                    if not jidConn[0]: return False
                    return jidConn[0].node == jid.node and jidConn[0].domain == jid.domain
                
            activeJids = filter(f, conns)
            for con in activeJids:
                con[1].send(prepareDataForSending(msg))
        else:
            # TODO: implement S2S
            pass