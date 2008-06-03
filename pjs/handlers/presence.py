import logging
import pjs.threadpool as threadpool

from pjs.handlers.base import ThreadedHandler, Handler, chainOutput, poll
from pjs.handlers.write import prepareDataForSending
from pjs.elementtree.ElementTree import Element, SubElement
from pjs.utils import FunctionCall
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
                msg.conn.server.launcher.router.route(msg, presTree, cjid)
        
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
        try:
            jid = JID(tree[0].get('to'))
        except Exception, e:
            return
        
        conns = msg.conn.server.launcher.servers[0].conns
        
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
            conns[con][1].send(prepareDataForSending(tree[0]))
    
class SubscriptionHandler(ThreadedHandler):
    """Handles subscriptions within <presence> stanzas. ie. <presence>
    elements with types.
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
            cjid = tree[0].get('to')
            type = tree[0].get('type')
            
            if not cjid:
                logging.warning('[presence] No contact jid specified in subscription query. Tree: %s', tree[0])
                # TODO: throw exception here
                return
            
            roster = Roster(jid)
            # get the RosterItem
            cinfo = roster.getContactInfo(cjid)
            if type == 'subscribe':
                # we must always route the subscribe presence so as to allow
                # the other servers to resynchronize their sub lists.
                # RFC 3921 9.2
                if not cinfo:
                    # contact doesn't exist, but according to RFC 3921
                    # section 8.2 bullet 4 we MUST create a new roster entry
                    # for it with empty name and groups.
                    roster.updateContact(cjid)
                    
                    # now refetch the contact info
                    cinfo = roster.getContactInfo(cjid)

                cid = cinfo.id
                name = cinfo.name
                subscription = cinfo.subscription
                groups = cinfo.groups
                
                # update the subscription state
                if subscription == Subscription.NONE:
                    roster.setSubscription(cid, Subscription.NONE_PENDING_OUT)
                elif subscription == Subscription.NONE_PENDING_IN:
                    roster.setSubscription(cid, Subscription.NONE_PENDING_IN_OUT)
                elif subscription == Subscription.FROM:
                    roster.setSubscription(cid, Subscription.FROM_PENDING_OUT)
                
                # send a roster push with ask
                query = Element('query', {'xmlns' : 'jabber:iq:roster'})
                d = {
                 'jid' : cjid,
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
                tree[0].set('from', jid)
                
                # route the presence
                msg.conn.server.launcher.router.route(msg, tree[0], cjid)
                
                # push the roster first, in case we have to create a new
                # s2s connection
                msg.setNextHandler('write')
                msg.setNextHandler('roster-push')
                
                return chainOutput(lastRetVal, query)
                
            elif type == 'subscribed':
                pass
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