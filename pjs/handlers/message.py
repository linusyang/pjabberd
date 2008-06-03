"""<message>-related handlers"""

import logging
import pjs.threadpool as threadpool

from pjs.handlers.base import ThreadedHandler, Handler, chainOutput, poll
from pjs.elementtree.ElementTree import Element, SubElement
from pjs.utils import FunctionCall, tostring
from pjs.roster import Roster, Subscription
from pjs.jid import JID
from copy import copy

class C2SMessageHandler(Handler):
    """Receives a message from a client on our server and schedules a
    server-routing handler.
    """
    def handle(self, tree, msg, lastRetVal=None):
        # check that we have the to and from fields in the message and
        # just forward
        toJID = tree.get('to')
        jid = msg.conn.data['user']['jid']
        resource = msg.conn.data['user']['resource']

        try:
            toJID = JID(toJID)
        except:
            logging.debug("[%s] 'to' attribute in message not a real JID",
                          self.__class__)
            return

        stampedTree = copy(tree)
        stampedTree.set('from', '%s/%s' % (jid, resource))

        routeData = {
                     'to' : toJID.__str__(),
                     'data' : stampedTree
                     }
        msg.setNextHandler('route-server')

        return chainOutput(lastRetVal, routeData)

class S2SMessageHandler(ThreadedHandler):
    """Handles <message>s coming in from remote servers"""
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
            cjid = tree.get('from')
            if not cjid:
                logging.debug("[%s] No 'from' attribute in <message> " + \
                              "stanza from server. Dropping: %s",
                              self.__class__, tostring(tree))
                return

            try:
                cjid = JID(cjid)
            except Exception, e:
                logging.debug("[%s] 'from' attribute in <message> not a " +\
                              "real JID: %s. Dropping: %s",
                              self.__class__, cjid, tostring(tree))
                return

            to = tree.get('to')
            if not to:
                logging.debug("[%s] No 'to' attribute in <message> stanza from server",
                              self.__class__)
                return

            try:
                to = JID(to)
            except Exception, e:
                logging.debug("[%s] 'to' attribute in <message> not a " +\
                              "real JID: %s. Dropping: %s",
                              self.__class__, to, tostring(tree))
                return

            if to.domain != msg.conn.server.hostname:
                logging.debug("[%s] <message> stanza recipient not handled " +\
                              "by this server: %s",
                              self.__class__, tostring(msg))
                return

            def makeServiceUnavailableError():
                fromJID = cjid.__str__()
                reply = Element('message', {
                                            'type' : 'error',
                                            'to' : fromJID
                                            })
                reply.append(copy(tree))
                error = Element('error', {'type' : 'cancel'})
                SubElement(error, 'service-unavailable', {
                              'xmlns' : 'urn:ietf:params:xml:ns:xmpp-stanzas'
                              })
                routeData = {
                             'to' : fromJID,
                             'data' : reply
                             }
                msg.setNextHandler('route-client')
                return chainOutput(lastRetVal, routeData)

            if to.exists():
                # user exists in the DB. check if they're online,
                # then forward to server
                conns = msg.conn.server.launcher.getC2SServer().data['resources']
                toJID = to.getBare()

                # we may need to strip the resource if it's not available
                # and send to the bare JID
                modifiedTo = to.__str__()

                if conns.has_key(toJID) and conns[toJID]:
                    # the user has one or more resources available
                    if to.resource:
                        # if sending to a specific resource,
                        # check if it's available
                        if not conns[toJID].has_key(to.resource):
                            # resource is unavailable, so send to bare JID
                            modifiedTo = toJID
                else:
                    # user is unavailable, so send an error, unless
                    # this message is an error already
                    if tree.get('type') == 'error':
                        return
                    return makeServiceUnavailableError()


                routeData = {
                             'to' : modifiedTo,
                             'data' : tree
                             }
                msg.setNextHandler('route-client')
                return chainOutput(lastRetVal, routeData)
            else:
                # user does not exist
                # reply with <service-unavailable>.

                if tree.get('type') == 'error':
                    # unless this message was an error itself
                    return

                return makeServiceUnavailableError()


        def cb(workReq, retVal):
            self.done = True
            # make sure we pass the lastRetVal along
            if retVal is None:
                self.retVal = lastRetVal
            else:
                self.retVal = retVal

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