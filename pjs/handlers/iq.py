import logging
import pjs.threadpool as threadpool

from pjs.handlers.base import ThreadedHandler, Handler, chainOutput, poll
from pjs.roster import Roster, RosterItem
from pjs.elementtree.ElementTree import Element, SubElement
from pjs.utils import tostring, generateId, FunctionCall
from pjs.db import DB
from copy import deepcopy

class IQBindHandler(Handler):
    """Handles resource binding"""
    def handle(self, tree, msg, lastRetVal=None):
        iq = tree[0]
        id = iq.get('id')
        if id:
            bind = iq[0]
            if len(bind) > 0:
                # accept id
                # TODO: check if id is available
                resource = bind[0].text
            else:
                # generate an id
                resource = generateId()[:6]
            
            # TODO: check that we don't already have such a resource
            
            msg.conn.data['user']['resource'] = resource
            
            # record the resource in the JID object of the (JID, Connection) pair
            # this is for local delivery lookups
            msg.conn.server.conns[msg.conn.id][0].resource = resource
            
            jid = msg.conn.data['user']['jid']
            
            # save the jid/resource in the server's global storage
            msg.conn.server.data['resources'][jid] = {
                                                      resource : msg.conn
                                                      }
                
            res = Element('iq', {'type' : 'result', 'id' : id})
            bind = Element('bind', {'xmlns' : 'urn:ietf:params:xml:ns:xmpp-bind'})
            jidEl = Element('jid')
            jidEl.text = '%s/%s' % (jid, resource)
            bind.append(jidEl)
            res.append(bind)
            
            return chainOutput(lastRetVal, res)
        else:
            logging.warning("No id in <iq>:\n%s", tostring(iq))
            
        return lastRetVal
        
class IQSessionHandler(Handler):
    """Handles session establishment"""
    def handle(self, tree, msg, lastRetVal=None):
        res = Element('iq', {
                             'from' : msg.conn.server.hostname,
                             'type' : 'result',
                             'id' : tree[0].get('id')
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
            id = tree[0].get('id')
            if id is None:
                logging.warning('[roster] No id in roster get query. Tree: %s', tree[0])
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
            id = tree[0].get('id')
            if id is None:
                logging.warning('[roster] No id in roster get query. Tree: %s', tree[0])
                # TODO: throw exception here
                return
            
            # RFC 3921 says in section 7.4 "an item", so we only handle the
            # first <item>
            item = tree[0][0][0] # iq -> query -> item
            cjid = item.get('jid')
            name = item.get('name')
            if cjid is None:
                logging.warning("[roster] Client trying to add a roster item " + \
                                "without a jid. Tree: %s", tree[0])
                # TODO: throw exception here
                return

            roster = Roster(jid)
            
            xpath = './{jabber:iq:roster}query/{jabber:iq:roster}item[@subscription="remove"]'
            if tree[0].find(xpath) is not None:
                # we're removing the roster item
                roster.removeContact(cjid)
                query = deepcopy(tree[0][0])
                msg.setNextHandler('roster-push')
                return chainOutput(lastRetVal, query)
            
            # we're updating/adding the roster item
            
            groups = list(item.findall('{jabber:iq:roster}group'))
            
            cid = roster.updateContact(cjid, groups, name)
            
            # get the subscription status before roster push
            sub = roster.getSubPrimaryName(cid)
                
            # prepare the result for roster push
            query = Element('query', {'xmlns' : 'jabber:iq:roster'})
            
            d = {
                 'jid' : cjid,
                 'subscription' : sub,
                 }
            if name:
                d['name'] = name
                
            item = SubElement(query, 'item', d)
            
            for groupName in groups:
                group = Element('group')
                group.text = groupName.text
                item.append(group)
                
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
            if not isinstance(lastRetVal, list) \
                or not isinstance(lastRetVal[-1], Element) \
                or lastRetVal[-1].tag.find('query') == -1:
                logging.warning('[%s] Got a non-query Element last return value' +\
                                '. Last return value: %s',
                                self.__class__, lastRetVal)
                return
            
            id = tree[0].get('id')
            if not id:
                logging.warning('[%s] No id in roster get query. Tree: %s',
                                self.__class__, tree[0])
                return
            
            jid = msg.conn.data['user']['jid']
            resource = msg.conn.data['user']['resource']
            
            # replace the <query> in lastRetVal with an ack to client
            query = lastRetVal.pop(-1)
            
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
                    
                    con.send(tostring(iq))
                
            # send an ack to client
            iq = Element('iq', {
                                'to' : '%s/%s' % (jid, resource),
                                'type' : 'result',
                                'id' : id
                                })
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
            origIQ = tree[0]
        else:
            logging.warning("Original <iq> missing:\n%s", tostring(tree))
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
            logging.warning("No id in <iq>:\n%s", tostring(origIQ))
        
        return lastRetVal