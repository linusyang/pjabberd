import logging
import pjs.threadpool as threadpool

from pjs.handlers.base import ThreadedHandler, Handler, chainOutput, poll
from pjs.handlers.write import prepareDataForSending
from pjs.elementtree.ElementTree import Element, SubElement
from pjs.utils import FunctionCall, tostring
from pjs.roster import Roster, Subscription
from pjs.jid import JID
from copy import deepcopy

class C2SPresenceHandler(ThreadedHandler):
    """Handles plain <presence> (without type) sent by the clients"""
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
            jid = msg.conn.data['user']['jid']
            resource = msg.conn.data['user']['resource']
            
            presTree = deepcopy(tree[0])
            presTree.set('from', '%s/%s' % (jid, resource))
            
            # lookup contacts interested in presence
            roster = Roster(jid)
            cjids = roster.getPresenceSubscribers()
            
            for cjid in cjids:
                presTree.set('to', cjid)
                msg.conn.server.launcher.router.routeToServer(msg, presTree, cjid)
        
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
    
class S2SPresenceHandler(Handler):
    """Handles plain <presence> (without type) sent by the servers"""
    def handle(self, tree, msg, lastRetVal=None):
        # we need to rewrite the "to" attribute of the <presence>
        # stanza for each resource of the user we send it to
        def rewriteTo(data, conn):
            jid = conn.data['user']['jid']
            res = conn.data['user']['resource']
            data.set('to', '%s/%s' % (jid, res))
            return data
        
        logging.debug("[%s] Routing %s", self.__class__, tostring(tree[0]))
        msg.conn.server.launcher.router.routeToClient(msg, tree[0], tree[0].get('to'), rewriteTo)
    
class S2SSubscriptionHandler(ThreadedHandler):
    """Handles subscriptions sent from servers within <presence> stanzas.
    ie. <presence> elements with types.
    """
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
            # get the contact's jid
            fromAddr = tree[0].get('from')
            try:
                cjid = JID(fromAddr)
            except Exception, e:
                logging.warning("[%s] 'from' JID is not properly formatted. Tree: %s",
                                self.__class__, tostring(tree[0]))
                return
            
            # get the user's jid
            toAddr = tree[0].get('to')
            try:
                jid = JID(toAddr)
            except Exception, e:
                logging.warning("[%s] 'to' JID is not properly formatted. Tree: %s",
                                self.__class__, tostring(tree[0]))
                return
            
            roster = Roster(jid.getBare())
            
            doRoute = False

            cinfo = roster.getContactInfo(cjid.getBare())
            subType = tree[0].get('type')
            
            retVal = lastRetVal

            # S2S SUBSCRIBE
            if subType == 'subscribe':

                if not cinfo:
                    # contact doesn't exist, so it's a first-time add
                    # need to add the contact with subscription None + Pending In
                    roster.updateContact(cjid.getBare(), None, None, Subscription.NONE_PENDING_IN)
                    cinfo = roster.getContactInfo(cjid.getBare())
                    doRoute = True
                if cinfo.subscription in (Subscription.NONE,
                                          Subscription.NONE_PENDING_OUT,
                                          Subscription.TO):
                    # change state
                    if cinfo.subscription == Subscription.NONE:
                        roster.setSubscription(cinfo.id, Subscription.NONE_PENDING_IN)
                    elif cinfo.subscription == Subscription.NONE_PENDING_OUT:
                        roster.setSubscription(cinfo.id, Subscription.NONE_PENDING_IN_OUT)
                    elif cinfo.subscription == Subscription.TO:
                        roster.setSubscription(cinfo.id, Subscription.TO_PENDING_IN)
                        
                    doRoute = True
                elif cinfo.subscription in (Subscription.FROM,
                                            Subscription.FROM_PENDING_OUT,
                                            Subscription.BOTH):
                    # auto-reply with "subscribed" stanza
                    doRoute = False
                    out = "<presence to='%s' from='%s' type='subscribed'/>" % (cjid.getBare(), jid.getBare())
                    # prepare the data for routing
                    subscribedRouting = {
                         'to' : cjid.getBare(),
                         'data' : out,
                         }
                    retVal = chainOutput(retVal, subscribedRouting)
                    msg.setNextHandler('route-server')
                
                # ignore presence in other states
                
                if doRoute:
                    # queue the stanza for delivery
                    stanzaRouting = {
                                     'to' : jid,
                                     'data' : tree[0]
                                     }
                    retVal = chainOutput(retVal, stanzaRouting)
                    msg.setNextHandler('route-client')
                    
                return retVal

            # S2S SUBSCRIBED
            elif subType == 'subscribed':

                if cinfo:
                    subscription = cinfo.subscription
                    if cinfo.subscription in (Subscription.NONE_PENDING_OUT,
                                              Subscription.NONE_PENDING_IN_OUT,
                                              Subscription.FROM_PENDING_OUT):
                        # change state
                        if cinfo.subscription == Subscription.NONE_PENDING_OUT:
                            roster.setSubscription(cinfo.id, Subscription.TO)
                            subscription = Subscription.TO
                        elif cinfo.subscription == Subscription.NONE_PENDING_IN_OUT:
                            roster.setSubscription(cinfo.id, Subscription.TO_PENDING_IN)
                            subscription = Subscription.TO_PENDING_IN
                        elif cinfo.subscription == Subscription.FROM_PENDING_OUT:
                            roster.setSubscription(cinfo.id, Subscription.BOTH)
                            subscription = Subscription.BOTH
                        
                        # forward the subscribed presence
                        # prepare the presence data for routing
                        d = {
                             'to' : jid,
                             'data' : tree[0],
                             }
                        retVal = chainOutput(retVal, d)
                            
                        # create an updated roster item for roster push
                        query = Roster.createRosterQuery(cinfo.jid,
                                    Subscription.getPrimaryNameFromState(subscription),
                                    cinfo.name, cinfo.groups)
                        
                        routeData = {}
                        conns = msg.conn.server.launcher.getC2SServer().data['resources']
                        bareJID = jid.getBare()
                        if conns.has_key(bareJID):
                            routeData['jid'] = bareJID
                            routeData['resources'] = conns[bareJID]
                        
                        # next handlers (reverse order)
                        msg.setNextHandler('route-client')
                        msg.setNextHandler('roster-push')
                        
                        return chainOutput(retVal, (routeData, query))
                        
            # S2S UNSUBSCRIBE
            elif subType == 'unsubscribe':

                if cinfo:
                    subscription = cinfo.subscription
                    if subscription not in (Subscription.NONE,
                                            Subscription.NONE_PENDING_OUT,
                                            Subscription.TO):
                        if subscription == Subscription.NONE_PENDING_IN \
                          or subscription == Subscription.FROM:
                            roster.setSubscription(cinfo.id, Subscription.NONE)
                            subscription = Subscription.NONE
                        elif subscription == Subscription.NONE_PENDING_IN_OUT \
                          or subscription == Subscription.FROM_PENDING_OUT:
                            roster.setSubscription(cinfo.id, Subscription.NONE_PENDING_OUT)
                            subscription = Subscription.NONE_PENDING_OUT
                        elif subscription == Subscription.TO_PENDING_IN \
                          or subscription == Subscription.BOTH:
                            roster.setSubscription(cinfo.id, Subscription.TO)
                            subscription = Subscription.TO
                            
                        # these steps are really in reverse order due to handler queuing
                        
                        # send unavailable presence from all resources
                        resources = msg.conn.server.launcher.getC2SServer().data['resources']
                        bareJID = jid.getBare()
                        jidForResources = resources.has_key(bareJID) and resources[bareJID]
                        if jidForResources:
                            out = u''
                            #logging.debug("!!! jidForResources: %d", len(jidForResources))
                            for i in jidForResources:
                                out += "<presence from='%s/%s'" % (bareJID, i)
                                out += " to='%s' type='unavailable'/>" % cjid.getBare()
                            #logging.debug("!!! About to route %s", out)
                            # and route it
                            unavailableRouting = {
                                                  'to' : cjid,
                                                  'data' : out
                                                  }
                            retVal = chainOutput(retVal, unavailableRouting)
                            # 4. route the unavailable presence back to server
                            msg.setNextHandler('route-server')
                            
                        # auto-reply with "unsubscribed" stanza
                        out = "<presence to='%s' from='%s' type='unsubscribed'/>" % (cjid.getBare(), jid.getBare())
                        unsubscribedRouting = {
                                               'to' : jid.getBare(),
                                               'data' : out
                                               }
                        retVal = chainOutput(retVal, unsubscribedRouting)
                        
                        # prepare the unsubscribe presence data for routing to client
                        unsubscribeRouting = {
                             'to' : jid,
                             'data' : tree[0],
                             }
                        retVal = chainOutput(retVal, unsubscribeRouting)
                        
                        # create an updated roster item for roster push
                        # we should really create add an ask='subscribe' for
                        # the NONE_PENDING_OUT state, but the spec doesn't
                        # say anything about this, so leave it out for now.
                        query = Roster.createRosterQuery(cinfo.jid,
                                    Subscription.getPrimaryNameFromState(subscription),
                                    cinfo.name, cinfo.groups)
                        
                        # needed for S2S roster push
                        routeData = {}
                        conns = msg.conn.server.launcher.getC2SServer().data['resources']
                        bareJID = jid.getBare()
                        if conns.has_key(bareJID):
                            routeData['jid'] = bareJID
                            routeData['resources'] = conns[bareJID]
                        
                        # handlers in reverse order. actual order:
                        # 1. push the updated roster
                        # 2. route the unsubscribe presence to client
                        # 3. route the unsubscribed presence back to server
                        # 4. see above. it's optional, since no resources could
                        #    be online by this point
                        msg.setNextHandler('route-server')
                        msg.setNextHandler('route-client')
                        msg.setNextHandler('roster-push')
                        
                        return chainOutput(retVal, (routeData, query))
                        
            # S2S UNSUBSCRIBED
            elif subType == 'unsubscribed':

                if cinfo:
                    subscription = cinfo.subscription
                    if subscription not in (Subscription.NONE,
                                            Subscription.NONE_PENDING_IN,
                                            Subscription.FROM):
                        # change state
                        if subscription == Subscription.NONE_PENDING_OUT \
                          or subscription == Subscription.TO:
                            roster.setSubscription(cinfo.id, Subscription.NONE)
                            subscription = Subscription.NONE
                        elif subscription == Subscription.NONE_PENDING_IN_OUT \
                          or subscription == Subscription.TO_PENDING_IN:
                            roster.setSubscription(cinfo.id, Subscription.NONE_PENDING_IN)
                            subscription = Subscription.NONE_PENDING_IN
                        elif subscription == Subscription.FROM_PENDING_OUT \
                          or subscription == Subscription.BOTH:
                            roster.setSubscription(cinfo.id, Subscription.FROM)
                            subscription = Subscription.FROM
                        
                        # prepare the unsubscribed presence data for routing
                        d = {
                             'to' : jid,
                             'data' : tree[0],
                             }
                        retVal = chainOutput(retVal, d)
                        
                        # create an updated roster item for roster push
                        query = Roster.createRosterQuery(cinfo.jid,
                                    Subscription.getPrimaryNameFromState(subscription),
                                    cinfo.name, cinfo.groups)
                        
                        # needed for S2S roster push
                        routeData = {}
                        conns = msg.conn.server.launcher.getC2SServer().data['resources']
                        bareJID = jid.getBare()
                        if conns.has_key(bareJID):
                            routeData['jid'] = bareJID
                            routeData['resources'] = conns[bareJID]
                        
                        # handlers in reverse order
                        # actually: push roster first, then route presence
                        msg.setNextHandler('route-client')
                        msg.setNextHandler('roster-push')
                        
                        return chainOutput(retVal, (routeData, query))
            
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

class C2SSubscriptionHandler(ThreadedHandler):
    """Handles subscriptions sent from clients within <presence> stanzas.
    ie. <presence> elements with types.
    """
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
            # TODO: verify that it's coming from a known user
            jid = msg.conn.data['user']['jid']
            cjid = JID(tree[0].get('to'))
            type = tree[0].get('type')
            
            if not cjid:
                logging.warning('[%s] No contact jid specified in subscription ' +\
                                'query. Tree: %s', self.__class__, tree[0])
                # TODO: throw exception here
                return
            
            roster = Roster(jid)
            # get the RosterItem
            cinfo = roster.getContactInfo(cjid.getBare())
            
            retVal = lastRetVal

            # C2S SUBSCRIBE
            if type == 'subscribe':

                # we must always route the subscribe presence so as to allow
                # the other servers to resynchronize their sub lists.
                # RFC 3921 9.2
                if not cinfo:
                    # contact doesn't exist, but according to RFC 3921
                    # section 8.2 bullet 4 we MUST create a new roster entry
                    # for it with empty name and groups.
                    roster.updateContact(cjid.getBare())
                    
                    # now refetch the contact info
                    cinfo = roster.getContactInfo(cjid.getBare())

                cid = cinfo.id
                name = cinfo.name
                subscription = cinfo.subscription
                groups = cinfo.groups
                
                # update the subscription state
                if subscription == Subscription.NONE:
                    roster.setSubscription(cid, Subscription.NONE_PENDING_OUT)
                    subscription = Subscription.NONE_PENDING_OUT
                elif subscription == Subscription.NONE_PENDING_IN:
                    roster.setSubscription(cid, Subscription.NONE_PENDING_IN_OUT)
                    subscription = Subscription.NONE_PENDING_IN_OUT
                elif subscription == Subscription.FROM:
                    roster.setSubscription(cid, Subscription.FROM_PENDING_OUT)
                    subscription = Subscription.FROM_PENDING_OUT
                
                # send a roster push with ask
                query = Roster.createRosterQuery(cjid.getBare(),
                            Subscription.getPrimaryNameFromState(subscription),
                            name, groups, {'ask' : 'subscribe'})

                # stamp presence with 'from' JID
                treeCopy = deepcopy(tree[0])
                treeCopy.set('from', jid)
                
                # prepare the presence data for routing
                d = {
                     'to' : cjid,
                     'data' : treeCopy,
                     }
                retVal = chainOutput(retVal, d)
                
                # sequence of events in reverse order
                # push the roster first, in case we have to create a new
                # s2s connection
                msg.setNextHandler('route-server')
                msg.setNextHandler('roster-push')
                
                return chainOutput(retVal, query)

            # C2S SUBSCRIBED
            elif type == 'subscribed':

                if not cinfo:
                    logging.warning("[%s] 'subscribed' presence received for " +\
                                    "non-existent contact %s", self.__class__, cjid)
                else:
                    subscription = cinfo.subscription
                    if cinfo.subscription in (Subscription.NONE_PENDING_IN,
                                              Subscription.NONE_PENDING_IN_OUT,
                                              Subscription.TO_PENDING_IN):
                        # update state and deliver
                        if cinfo.subscription == Subscription.NONE_PENDING_IN:
                            roster.setSubscription(cinfo.id, Subscription.FROM)
                            subscription = Subscription.FROM
                        elif cinfo.subscription == Subscription.NONE_PENDING_IN_OUT:
                            roster.setSubscription(cinfo.id, Subscription.FROM_PENDING_OUT)
                            subscription = Subscription.FROM_PENDING_OUT
                        elif cinfo.subscription == Subscription.TO_PENDING_IN:
                            roster.setSubscription(cinfo.id, Subscription.BOTH)
                            subscription = Subscription.BOTH
                            
                        # roster stanza
                        query = Roster.createRosterQuery(cjid.getBare(),
                                    Subscription.getPrimaryNameFromState(subscription),
                                    cinfo.name, cinfo.groups)
                            
                        # stamp presence with 'from'
                        treeCopy = deepcopy(tree[0])
                        treeCopy.set('from', jid)
                        
                        toRoute = tostring(treeCopy)
                        
                        # create available presence stanzas for all resources of the user
                        resources = msg.conn.server.launcher.getC2SServer().data['resources']
                        jidForResources = resources.has_key(jid) and resources[jid]
                        if jidForResources:
                            out = u''
                            logging.debug("!!! jidForResources: %d", len(jidForResources))
                            for i in jidForResources:
                                out += "<presence from='%s/%s'" % (jid, i)
                                out += " to='%s'/>" % cjid.getBare()
                            logging.debug("!!! About to route %s", out)
                            # and queue for routing
                            toRoute += out
                        
                        # prepare the presence data for routing
                        d = {
                             'to' : cjid,
                             'data' : toRoute,
                             }
                        retVal = chainOutput(retVal, d)
                        
                        # next handlers in reverse order
                        msg.setNextHandler('route-server')
                        msg.setNextHandler('roster-push')
                        
                        return chainOutput(retVal, query)

            # C2S UNSUBSCRIBE
            elif type == 'unsubscribe':

                # we must always route the unsubscribe presence so as to allow
                # the other servers to resynchronize their sub lists.
                # RFC 3921 9.2
                if not cinfo:
                    # we don't have this contact in our roster, but route the
                    # presence anyway
                    # stamp presence with 'from'
                    treeCopy = deepcopy(tree[0])
                    treeCopy.set('from', jid)
                    
                    # prepare the presence data for routing
                    d = {
                         'to' : cjid,
                         'data' : treeCopy,
                         }
                    msg.setNextHandler('route-server')
                    
                    return chainOutput(retVal, d)
                else:
                    subscription = cinfo.subscription
                    if subscription == Subscription.BOTH: # mutual
                        roster.setSubscription(cinfo.id, Subscription.FROM)
                        subscription = Subscription.FROM
                    elif subscription in (Subscription.NONE_PENDING_OUT, # one way
                                          Subscription.NONE_PENDING_IN_OUT,
                                          Subscription.TO,
                                          Subscription.TO_PENDING_IN):
                        if subscription == Subscription.NONE_PENDING_OUT \
                          or subscription == Subscription.TO:
                            roster.setSubscription(cinfo.id, Subscription.NONE)
                            subscription = Subscription.NONE
                        elif subscription == Subscription.NONE_PENDING_IN_OUT \
                          or subscription == Subscription.TO_PENDING_IN:
                            roster.setSubscription(cinfo.id, Subscription.NONE_PENDING_IN)
                            subscription = Subscription.NONE_PENDING_IN
                        
                    # roster stanza
                    query = Roster.createRosterQuery(cjid.getBare(),
                                Subscription.getPrimaryNameFromState(subscription),
                                cinfo.name, cinfo.groups)
                    
                    # stamp presence with 'from'
                    treeCopy = deepcopy(tree[0])
                    treeCopy.set('from', jid)
                    
                    # prepare the presence data for routing
                    d = {
                         'to' : cjid,
                         'data' : treeCopy,
                         }
                    retVal = chainOutput(retVal, d)
                    
                    # schedules handlers in reverse order
                    msg.setNextHandler('route-server')
                    msg.setNextHandler('roster-push')
                    
                    return chainOutput(retVal, query)

            # C2S UNSUBSCRIBED
            elif type == 'unsubscribed':

                if not cinfo:
                    logging.warning("[%s] 'unsubscribed' presence received for " +\
                                    "non-existent contact %s", self.__class__, cjid)
                else:
                    subscription = cinfo.subscription
                    if subscription not in (Subscription.NONE,
                                            Subscription.NONE_PENDING_OUT,
                                            Subscription.TO):
                        if subscription == Subscription.NONE_PENDING_IN \
                          or subscription == Subscription.FROM:
                            roster.setSubscription(cinfo.id, Subscription.NONE)
                            subscription = Subscription.NONE
                        elif subscription == Subscription.NONE_PENDING_IN_OUT \
                          or subscription == Subscription.FROM_PENDING_OUT:
                            roster.setSubscription(cinfo.id, Subscription.NONE_PENDING_OUT)
                            subscription = Subscription.NONE
                        elif subscription == Subscription.TO_PENDING_IN \
                          or subscription == Subscription.BOTH:
                            roster.setSubscription(cinfo.id, Subscription.TO)
                            subscription = Subscription.TO
                            
                        # roster query
                        if subscription == Subscription.NONE_PENDING_OUT:
                            itemArgs = {'ask' : 'subscribe'}
                        else:
                            itemArgs = {}
                        query = roster.createRosterQuery(cjid.getBare(),
                                        Subscription.getPrimaryNameFromState(subscription),
                                        cinfo.name, cinfo.groups, itemArgs)
                    
                        # stamp presence with 'from'
                        treeCopy = deepcopy(tree[0])
                        treeCopy.set('from', jid)
                        
                        toRoute = tostring(treeCopy)
                        
                        # create unavailable presence stanzas for all resources of the user
                        resources = msg.conn.server.launcher.getC2SServer().data['resources']
                        jidForResources = resources.has_key(jid) and resources[jid]
                        if jidForResources:
                            out = u''
                            #logging.debug("!!! jidForResources: %d", len(jidForResources))
                            for i in jidForResources:
                                out += "<presence from='%s/%s'" % (jid, i)
                                out += " to='%s' type='unavailable'/>" % cjid.getBare()
                            #logging.debug("!!! About to route %s", out)
                            # and add to output
                            toRoute += out
                        
                        # prepare the presence data for routing
                        d = {
                             'to' : cjid,
                             'data' : toRoute,
                             }
                        retVal = chainOutput(retVal, d)
                        
                        # handlers in reverse order
                        msg.setNextHandler('route-server')
                        msg.setNextHandler('roster-push')
                        
                        return chainOutput(retVal, query)
        
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