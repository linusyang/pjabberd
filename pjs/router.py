import logging

from pjs.elementtree.ElementTree import Element
from pjs.handlers.write import prepareDataForSending
from pjs.jid import JID
from threading import RLock

class Router:
    """Handles routing of outgoing messages"""
    
    def __init__(self, launcher):
        """Initialize the router with a pointer to the server"""
        self.launcher = launcher
        self.hostname = launcher.hostname
        self.c2sserver = launcher.getC2SServer()
        self.s2sserver = launcher.getS2SServer()
        self.s2sConns = self.s2sserver.s2sConns
        
        self.lock = RLock()
        
    def setS2SConnMap(self, connMap):
        """This is the connection map that will be used to lookup domains
        during routing. This should be an S2S connection map of the form:
        {'hostname' : (Connection object in, Connection object out)}
        
        Not used right now, but may be in the future.
        """
        self.s2sConns = connMap

    def routeToClient(self, msg, data, to=None, preprocessFunc=None):
        """Routes 'data' to its recipient (client). 'To' should be either a
        string JID or a JID object. If 'to' is not specified, the relevant
        information is extracted from 'data'. If that fails, the method
        returns False.
        msg: Message object. Needed to look up client conns.
        """
        self.lock.acquire()
        conns = self.c2sserver.conns
        
        to = self.getRoute(data, to)
        if not to:
            self.lock.release()
            return False
        
        jid = self.getJID(to)
        if not jid:
            self.lock.release()
            return False
        
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
        logging.debug("activeJids: %s", activeJids)
        for con in activeJids:
            if callable(preprocessFunc):
                conns[con][1].send(prepareDataForSending(preprocessFunc(data, conns[con][1])))
            else:
                conns[con][1].send(prepareDataForSending(data))
                
        self.lock.release()
    
    def routeToServer(self, msg, data, to=None):
        """Routes 'data' to its recipient. 'To' should be either a string JID
        or a JID object. If 'to' is not specified, the relevant information is
        extracted from 'data'. If that fails, the method returns False.
        msg: Message object. Needed in case we need to create a new S2S
            connection.
        """
        # TODO: implement S2S
        # for now, just route to ourselves
        
        self.lock.acquire()
        
        if self.s2sConns is None:
            self.lock.release()
            return False
        
        to = self.getRoute(data, to)
        if not to:
            self.lock.release()
            return False
        
        jid = self.getJID(to)
        if not jid:
            self.lock.release()
            return False

        # do we have an existing connection to the domain?
        if jid.domain in self.s2sConns:
            # reuse that connection
            self.s2sConns[jid.domain][1].send(prepareDataForSending(data))
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
        
        self.lock.release()
        return True
    
    def getRoute(self, data, to):
        """Figure out the route from the data"""
        if to: return to
        else:
            if isinstance(data, Element):
                to = data.get('to')
                if not to:
                    return False
            else:
                # can't extract routing information
                logging.warning("[%s] Can't extract routing information from %s",
                                self.__class__, data)
                return False
            
        return to

    def getJID(self, to):
        """Convert 'to' to a JID object"""
        if isinstance(to, JID):
            jid = to
        else:
            try:
                jid = JID(to)
            except Exception, e:
                logging.warning("[%s] " + e, self.__class__)
                return False
        return jid