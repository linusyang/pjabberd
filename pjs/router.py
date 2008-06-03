import logging
import socket

from pjs.elementtree.ElementTree import Element
from pjs.handlers.write import prepareDataForSending
from pjs.jid import JID

class Router:
    """Handles routing of outgoing messages"""
    
    def __init__(self, launcher):
        """Initialize the router with a pointer to the server"""
        self.launcher = launcher
        self.hostname = launcher.hostname
        self.conns = None
        
    def setConnMap(self, map):
        """This is the connection map that will be used to lookup domains
        during routing. This should be an S2S connection map of the form:
        {'hostname' : (Connection object in, Connection object out)}
        """
        self.conns = map
    
    def route(self, msg, data, to=None):
        """Routes 'data' to its recipient. 'To' should be a bare JID. If 'to'
        is not specified, the relevant information is extracted from 'data'.
        If that fails, the method returns False.
        msg: Message object. Needed in case we need to create a new S2S
            connection.
        """
        # TODO: implement S2S
        # for now, just route to ourselves
        
        if self.conns is None:
            return False
        
        if not to:
            if isinstance(data, Element):
                to = data.get('to')
                if not to:
                    return False
            else:
                # can't extract routing information
                logging.warning("Can't extract routing information from %s", data)
                return False
            
        try:
            jid = JID(to)
        except Exception, e:
            logging.warning(e)
            return False

        # do we have an existing connection to the domain?
        if jid.domain in self.conns:
            # reuse that connection
            self.conns[jid.domain][1].send(prepareDataForSending(data))
        else:
            # create a new S2S connection
            # populate the dictionary for the new s2s connection creator
            d = msg.conn.data
            newconn = d.setdefault('new-s2s-conn', {})
            newconn['connected'] = False
            newconn['hostname'] = jid.domain
            if jid.domain == self.hostname:
                newconn['ip'] = jid.domain
            else:
                # TODO: Domain lookup here for S2S via another handler
                pass
            newconn['queue'] = [prepareDataForSending(data)]
            
            msg.setNextHandler('new-s2s-conn')
        
        return True