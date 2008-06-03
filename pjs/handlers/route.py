"""Defines the routers. They're implemented as handlers that require
specific objects in lastRetVal to work correctly.
"""

import logging

from pjs.handlers.base import Handler, chainOutput
from pjs.handlers.write import prepareDataForSending
from pjs.elementtree.ElementTree import Element
from pjs.jid import JID

class ClientRouteHandler(Handler):
    """Handles routing of data to a client on this server.
    This handlers requires the following to be the last item on the
    lastRetVal list:
      {
        'data' : <data to send. whatever prepareDataForSending handles>,
        'to' : <either str or JID object>,
        'preprocessFunc' : <optional function that will be called with
                            params: data, conn. data is the data that will
                            be sent. conn is the Connection to use to send
                            the data. The return value of this function is
                            used instead of data>
      }
    """
    def handle(self, tree, msg, lastRetVal=None):
        if not isinstance(lastRetVal[-1], dict):
            logging.warning("[%s] Passed in incorrect routing structure",
                            self.__class__)
            return

        d = lastRetVal.pop()
        data = d.get('data')
        to = d.get('to')
        preprocessFunc = d.get('preprocessFunc')

        if data is None:
            logging.warning("[%s] No data to send", self.__class__)
            return

        conns = msg.conn.server.launcher.getC2SServer().conns

        try:
            to = getRoute(data, to)
        except Exception, e:
            logging.warning("[%s] %s", self.__class__, e)
            return

        try:
            jid = getJID(to)
        except Exception, e:
            logging.warning("[%s] %s" + e, self.__class__, e)
            return

        if jid.resource:
            # locate the resource of this JID
            def f(i):
                if not conns[i][0]: return False
                return conns[i][0] == jid
        else:
            # locate all active resources of this JID
            def f(i):
                jidConn = conns[i]
                if not jidConn[0]: return False
                return jidConn[0].node == jid.node and jidConn[0].domain == jid.domain

        activeJids = filter(f, conns)
        for con in activeJids:
            if callable(preprocessFunc):
                conns[con][1].send(prepareDataForSending(preprocessFunc(data, conns[con][1])))
            else:
                conns[con][1].send(prepareDataForSending(data))

class ServerRouteHandler(Handler):
    """Handles routing of data to a client on this server.
    This handlers requires lastRetVal[-1] to contain the routing data. See
    ClientRouteHandler.__doc__.
    """
    def handle(self, tree, msg, lastRetVal=None):
        if not isinstance(lastRetVal[-1], dict):
            logging.warning("[%s] Passed in incorrect routing structure",
                            self.__class__)
            return

        d = lastRetVal.pop()
        data = d.get('data')
        to = d.get('to')
        preprocessFunc = d.get('preprocessFunc')

        if data is None:
            logging.warning("[%s] No data to send", self.__class__)
            return

        s2sConns = msg.conn.server.launcher.getS2SServer().s2sConns
        if s2sConns is None:
            return False

        try:
            to = getRoute(data, to)
        except Exception, e:
            logging.warning("[%s] " + e, self.__class__)
            return

        try:
            jid = getJID(to)
        except Exception, e:
            logging.warning("[%s] " + e, self.__class__)
            return

        # do we have an existing connection to the domain?
        if jid.domain in s2sConns:
            # reuse that connection
            if callable(preprocessFunc):
                s2sConns[jid.domain][1].send(prepareDataForSending(preprocessFunc(data, s2sConns[jid.domain][1])))
            else:
                s2sConns[jid.domain][1].send(prepareDataForSending(data))
        else:
            # create a new S2S connection
            # populate the dictionary for the new s2s connection creator
            d = msg.conn.data
            newconn = d.setdefault('new-s2s-conn', {})
            newconn['connected'] = False
            newconn['hostname'] = jid.domain
            if jid.domain == msg.conn.server.launcher.hostname:
                newconn['local'] = True
            if jid.domain == msg.conn.server.hostname:
                newconn['ip'] = jid.domain
            else:
                # TODO: Domain lookup here for S2S via another handler
                pass
            newconn['queue'] = [prepareDataForSending(data)]

            msg.setNextHandler('new-s2s-conn')


def getRoute(data, to):
    """Figure out the route from the data"""
    if to: return to
    else:
        if isinstance(data, Element):
            to = data.get('to')
            if not to:
                raise Exception, "Can't extract routing information from %s" \
                                                                        % data
        else:
            raise Exception, "Can't extract routing information from %s" \
                                                                    % data
    return to

def getJID(to):
    """Convert 'to' to a JID object"""
    if isinstance(to, JID):
        return to
    else:
        try:
            jid = JID(to)
        except Exception, e:
            raise Exception, "Can't convert %s to a JID object" % to
    return jid