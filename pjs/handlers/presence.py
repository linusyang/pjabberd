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
        # just forward it for now
        msg.conn.server.launcher.router.routeToClient(msg, tree[0], tree[0].get('to'))
    
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
                    # TODO: auto-reply with "subscribed" stanza
                    pass
                # ignore presence in other states
            elif subType == 'subscribed':
                pass
            elif subType == 'unsubscribe':
                pass
            elif subType == 'unsubscribed':
                pass
            
            if doRoute:
                # deliver the stanza
                msg.conn.server.launcher.router.routeToClient(msg, tree[0], jid)
            
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
                logging.warning('[presence] No contact jid specified in subscription query. Tree: %s', tree[0])
                # TODO: throw exception here
                return
            
            roster = Roster(jid)
            # get the RosterItem
            cinfo = roster.getContactInfo(cjid.getBare())
            
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
                query = Element('query', {'xmlns' : 'jabber:iq:roster'})
                d = {
                 'jid' : cjid.getBare(),
                 'subscription' : Subscription.getPrimaryNameFromState(subscription),
                 'ask' : 'subscribe'
                 }
                if name:
                    d['name'] = name
                    
                item = SubElement(query, 'item', d)
                
                for groupName in groups:
                    group = Element('group')
                    group.text = groupName
                    item.append(group)
                    
                # stamp presence with 'from' JID (3921-8.2)
                treeCopy = deepcopy(tree[0])
                treeCopy.set('from', jid)
                
                # route the presence
                msg.conn.server.launcher.router.routeToServer(msg, treeCopy, cjid)
                
                # push the roster first, in case we have to create a new
                # s2s connection
                msg.setNextHandler('write')
                msg.setNextHandler('roster-push')
                
                return chainOutput(lastRetVal, query)
                
            elif type == 'subscribed':
                if not cinfo:
                    logging.warning("'subscribed' presence received for " +\
                                    "non-existant contact")
                else:
                    subscription = cinfo.subscription
                    if cinfo.subscription in (Subscription.NONE_PENDING_IN,
                                              Subscription.NONE_PENDING_IN_OUT,
                                              Subscription.TO_PENDING_IN):
                        # update state and deliver
                        if cinfo.subscription == Subscription.NONE_PENDING_IN:
                            roster.setSubscription(cinfo.id, Subscription.FROM)
                            subscription = Subscription.FROM
                        elif cinfo.subscription == Subscription.FROM_PENDING_OUT:
                            roster.setSubscription(cinfo.id, Subscription.FROM_PENDING_OUT)
                            subscription = Subscription.FROM_PENDING_OUT
                        elif cinfo.subscription == Subscription.TO_PENDING_IN:
                            roster.setSubscription(cinfo.id, Subscription.BOTH)
                            subscription = Subscription.BOTH
                            
                        # roster stanza
                        query = Element('query' , {'xmlns' : 'jabber:iq:roster'})
                        d = {
                             'jid' : cjid.getBare(),
                             'subscription' : Subscription.getPrimaryNameFromState(subscription)
                             }
                        if cinfo.name:
                            d['name'] = cinfo.name
                            
                        item = SubElement(query, 'item', d)
                        
                        groups = cinfo.groups
                        for groupName in groups:
                            group = Element('group')
                            group.text = groupName
                            item.append(group)
                            
                        # stamp presence with 'from'
                        treeCopy = deepcopy(tree[0])
                        treeCopy.set('from', jid)
                        
                        # route the presence
                        msg.conn.server.launcher.router.routeToServer(msg, treeCopy, cjid)
                        
                        # create available presence stanzas for all resources of the user
                        resources = msg.conn.server.launcher.getC2SServer().data['resources']
                        jidForResources = resources.has_key(jid) and resources[jid]
                        if jidForResources:
                            out = u''
                            for i in jidForResources:
                                out += "<presence from='%s/%s'" % (jid, i)
                                out += " to='%s'/>" % cjid.getBare()
                            # and route it
                            msg.conn.server.launcher.router.routeToServer(msg, out, cjid)
                        
                        # queue the roster push
                        msg.setNextHandler('write')
                        msg.setNextHandler('roster-push')
                        
                        return chainOutput(lastRetVal, query)
                    
            elif type == 'unsubscribe':
                pass
            elif type == 'unsubscribed':
                pass
        
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