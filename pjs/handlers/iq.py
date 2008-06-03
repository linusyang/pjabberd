"""<iq>-related handlers"""

import logging
import pjs.threadpool as threadpool

from pjs.handlers.base import ThreadedHandler, Handler, chainOutput, poll
from pjs.roster import Roster
from pjs.elementtree.ElementTree import Element, SubElement
from pjs.utils import tostring, generateId, FunctionCall
from copy import deepcopy

def bindResource(msg, resource):
    """Records the resource binding. Returns the bare JID.
    This should only be called from the C2Sserver.
    """
    data = msg.conn.data
    server = msg.conn.server
    jid = data['user']['jid']

    # check if we have this resource already
    if server.data['resources'].has_key(jid) and \
    server.data['resources'][jid].has_key(resource):
        # create our own
        resource = resource + generateId()[:6]
    data['user']['resource'] = resource

    # record the resource in the JID object of the (JID, Connection) pair
    # this is for local delivery lookups
    server.conns[msg.conn.id][0].resource = resource

    # save the jid/resource in the server's global storage
    if not server.data['resources'].has_key(jid):
        server.data['resources'][jid] = {}
    server.data['resources'][jid][resource] = msg.conn

class IQBindHandler(Handler):
    """Handles resource binding"""
    def handle(self, tree, msg, lastRetVal=None):
        iq = tree
        id = iq.get('id')
        if id:
            bind = iq[0]
            if len(bind) > 0:
                resource = bind[0].text
            else:
                # generate an id
                resource = generateId()[:6]

            # TODO: check that we don't already have such a resource
            jid = msg.conn.data['user']['jid']
            bindResource(msg, resource)

            res = Element('iq', {'type' : 'result', 'id' : id})
            bind = Element('bind', {'xmlns' : 'urn:ietf:params:xml:ns:xmpp-bind'})
            jidEl = Element('jid')
            jidEl.text = '%s/%s' % (jid, resource)
            bind.append(jidEl)
            res.append(bind)

            return chainOutput(lastRetVal, res)
        else:
            logging.warning("[%s] No id in <iq>:\n%s", self.__class__, tostring(iq))

        return lastRetVal

class IQSessionHandler(Handler):
    """Handles session establishment"""
    def handle(self, tree, msg, lastRetVal=None):
        res = Element('iq', {
                             'from' : msg.conn.server.hostname,
                             'type' : 'result',
                             'id' : tree.get('id')
                             })

        msg.conn.data['user']['in-session'] = True

        return chainOutput(lastRetVal, res)

class IQRosterGetHandler(ThreadedHandler):
    """Responds to a roster iq get request"""
    def __init__(self):
        # this is true when the threaded handler returns
        self.done = False
        # used to pass the output to the next handler
        self.retVal = None

    def handle(self, tree, msg, lastRetVal=None):
        self.done = False

        tpool = msg.conn.server.threadpool

        msg.conn.data['user']['requestedRoster'] = True

        # the actual function executing in the thread
        def act():
            # TODO: verify that it's coming from a known user
            jid = msg.conn.data['user']['jid']
            resource = msg.conn.data['user']['resource']
            id = tree.get('id')
            if id is None:
                logging.warning('[%s] No id in roster get query. Tree: %s',
                                self.__class__, tree)
                # TODO: throw exception here
                return

            roster = Roster(jid)

            roster.loadRoster()

            res = Element('iq', {
                                 'to' : '/'.join([jid, resource]),
                                 'type' : 'result',
                                 'id' : id
                                 })

            res.append(roster.getAsTree())
            return chainOutput(lastRetVal, res)

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
        # this is passed to the next handler
        return self.retVal

class IQRosterUpdateHandler(ThreadedHandler):
    """Responds to a roster iq set request"""
    def __init__(self):
        # this is true when the threaded handler returns
        self.done = False
        # used to pass the output to the next handler
        self.retVal = None

    def handle(self, tree, msg, lastRetVal=None):
        self.done = False

        tpool = msg.conn.server.threadpool

        # the actual function executing in the thread
        def act():
            # TODO: verify that it's coming from a known user
            jid = msg.conn.data['user']['jid']
            id = tree.get('id')
            if id is None:
                logging.warning('[%s] No id in roster get query. Tree: %s',
                                self.__class__, tree)
                # TODO: throw exception here
                return

            # RFC 3921 says in section 7.4 "an item", so we only handle the
            # first <item>
            item = tree[0][0] # iq -> query -> item
            cjid = item.get('jid')
            name = item.get('name')
            if cjid is None:
                logging.warning("[%s] Client trying to add a roster item " + \
                                "without a jid. Tree: %s",
                                self.__class__, tree)
                # TODO: throw exception here
                return

            roster = Roster(jid)

            xpath = './{jabber:iq:roster}query/{jabber:iq:roster}item[@subscription="remove"]'
            if tree.find(xpath) is not None:
                # we're removing the roster item. See 3921 8.6
                out = "<presence from='%s' to='%s' type='unsubscribe'/>" \
                                                          % (jid, cjid)
                out += "<presence from='%s' to='%s' type='unsubscribed'/>" \
                                                          % (jid, cjid)
                # create unavailable presence stanzas for all resources of the user
                resources = msg.conn.server.launcher.getC2SServer().data['resources']
                jidForResources = resources.has_key(jid) and resources[jid]
                if jidForResources:
                    for i in jidForResources:
                        out += "<presence from='%s/%s'" % (jid, i)
                        out += " to='%s' type='unavailable'/>" % cjid

                # prepare routing data
                d = {
                     'to' : cjid,
                     'data' : out
                     }

                query = deepcopy(tree[0])

                retVal = chainOutput(lastRetVal, query)

                if roster.removeContact(cjid) is False:
                    # We don't even have this contact in the roster anymore.
                    # The contact is probably local (like ourselves).
                    # This happens with some clients (like pidgin/gaim) who
                    # cache the roster and don't delete some items even when
                    # they're not present in the roster the server sends out
                    # anymore. If we send the presence here it
                    # will probably arrive after roster-push (due to s2s)
                    # and will confuse the clients into thinking they still
                    # have that contact in their roster. This creates an
                    # undeletable contact. We can't do much about this.
                    # If/when the s2s component can do a shortcut delivery of
                    # stanzas to local users, while in the same phase, this
                    # problem should go away, as it will allow the roster-push
                    # to arrive after presences every time.
                    pass

                # route the presence first, then do a roster push
                msg.setNextHandler('roster-push')
                msg.setNextHandler('route-server')

                return chainOutput(retVal, d)

            # we're updating/adding the roster item

            groups = [i.text for i in list(item.findall('{jabber:iq:roster}group'))]

            cid = roster.updateContact(cjid, groups, name)

            # get the subscription status before roster push
            sub = roster.getSubPrimaryName(cid)

            # prepare the result for roster push
            query = Roster.createRosterQuery(cjid, sub, name, groups)

            msg.setNextHandler('roster-push')

            return chainOutput(lastRetVal, query)

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
        # this is passed to the next handler
        return self.retVal

class RosterPushHandler(ThreadedHandler):
    """Uses the last return value from the previous handler to push a roster
    change to all connected resources of the user. This handler needs to be
    scheduled from another handler and passed an Element tree of the updated
    roster to send with <query> as the initial element.
    This works for both S2S and C2S servers. For S2S, pass in a tuple, where
    the first element is the routeData and the second is the <query> Element.
    routeData should have this
      routeData['jid'] -- jid of the user to whom the roster push is addressed
      routeData['resources'] -- ref to the resource=>Connection
                                dictionary from the c2s server for the user
    """
    def __init__(self):
        # this is true when the threaded handler returns
        self.done = False
        # used to pass the output to the next handler
        self.retVal = None

    def handle(self, tree, msg, lastRetVal=None):
        self.done = False

        tpool = msg.conn.server.threadpool

        def act():
            # we have to be passed a tree to work
            # or a tuple with routingData and a tree
            if not isinstance(lastRetVal, list):
                logging.warning('[%s] lastRetVal is not a list', self.__class__)
                return
            if isinstance(lastRetVal[-1], Element):
                if lastRetVal[-1].tag.find('query') == -1:
                    logging.warning('[%s] Got a non-query Element last return value' +\
                                '. Last return value: %s',
                                self.__class__, lastRetVal)
            elif isinstance(lastRetVal[-1], tuple):
                if not isinstance(lastRetVal[-1][0], dict) \
                or not isinstance(lastRetVal[-1][1], Element):
                    logging.warning('[%s] Got a non-query Element last return value' +\
                                '. Last return value: %s',
                                self.__class__, lastRetVal)
                    return
            else:
                logging.warning('[%s] Roster push needs either a <query> Element ' +\
                                'as the last item in lastRetVal or a tuple ' + \
                                'with (routeData, query Element)', self.__class__)
                return

            # this is the roster <query> that we'll send
            # it could be a tuple if we got routing data as well
            query = lastRetVal.pop(-1)
            routeData = None

            # did we get routing data (from S2S)
            if isinstance(query, tuple):
                routeData = query[0]
                query = query[1]

            if routeData:
                jid = routeData['jid']
                resources = routeData['resources']
            else:
                jid = msg.conn.data['user']['jid']
                resource = msg.conn.data['user']['resource']
                resources = msg.conn.server.data['resources'][jid]

            for res, con in resources.items():
                # don't send the roster to clients that didn't request it
                if con.data['user']['requestedRoster']:
                    iq = Element('iq', {
                                        'to' : '%s/%s' % (jid, res),
                                        'type' : 'set',
                                        'id' : generateId()[:10]
                                        })
                    iq.append(query)

                    # TODO: remove this. debug.
                    logging.debug("Sending " + tostring(iq))
                    con.send(tostring(iq))

            if tree.tag == '{jabber:client}iq' and tree.get('id'):
                # send an ack to client if this is in reply to a roster get/set
                id = tree.get('id')
                d = {
                     'to' : '%s/%s' % (jid, resource),
                     'type' : 'result',
                     'id' : id
                     }
                iq = Element('iq', d)
                return chainOutput(lastRetVal, iq)

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
        # this is passed to the next handler
        return self.retVal

class IQNotImplementedHandler(Handler):
    """Handler that replies to unknown iq stanzas"""
    def handle(self, tree, msg, lastRetVal=None):
        if len(tree) > 0:
            # get the original iq msg
            origIQ = tree
        else:
            logging.warning("[%s] Original <iq> missing:\n%s",
                            self.__class__, tostring(tree))
            return

        id = origIQ.get('id')
        if id:
            res = Element('iq', {
                                 'type' : 'error',
                                 'id' : id
                                })
            res.append(origIQ)

            err = Element('error', {'type' : 'cancel'})
            SubElement(err, 'service-unavailable',
                       {'xmlns' : 'urn:ietf:params:xml:ns:xmpp-stanzas'})

            res.append(err)

            return chainOutput(lastRetVal, res)
        else:
            logging.warning("[%s] No id in <iq>:\n%s",
                            self.__class__, tostring(origIQ))

        return lastRetVal