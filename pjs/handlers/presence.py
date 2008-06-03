import logging
import pjs.threadpool as threadpool
import pjs.conf.conf

from pjs.handlers.base import ThreadedHandler, Handler, chainOutput, poll
from pjs.elementtree.ElementTree import Element, SubElement
from pjs.utils import FunctionCall
from pjs.roster import Roster, Subscription

class PresenceHandler(ThreadedHandler):
    """Handles plain <presence> (without type)"""
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
            pass
        
        def cb(workReq, retVal):
            pass
        
        def checkFunc():
            return True
        
        return FunctionCall(checkFunc), None
    
    def resume(self):
        return self.retVal
    
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
                    
                msg.setNextHandler('roster-push')
                
                # stamp presence with 'from' JID (3921-8.2)
                tree.set('from', jid)
                
                # route the presence
                pjs.conf.conf.router.route(tree, cjid)
                
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