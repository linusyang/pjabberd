"""XMPP SASL stuff"""
# Some parts are borrowed from twisted. See TWISTED-LICENSE for details on its
# license.

import pjs.sasl_mechanisms as mechs
import pjs.threadpool as threadpool
import logging

from pjs.handlers.base import *
from pjs.sasl_mechanisms import SASLError
from pjs.utils import generateId, FunctionCall
from pjs.elementtree.ElementTree import Element, tostring

class SASLAuthHandler(ThreadedHandler):
    def __init__(self):
        self.done = False
    def handle(self, tree, msg, lastRetVal=None):
        """Handles SASL's <auth> element sent from the other side"""
        
        # this is true when the threaded handler returns
        self.done = False
        
        tpool = msg.conn.server.threadpool
        
        # the actual function executing in the thread
        def act(tree, msg):
            mech = tree[0].get('mechanism')
            
            if not msg.conn.data.has_key('sasl'):
                msg.conn.data['sasl'] = {
                                         'mech' : '',
                                         'challenge' : '',
                                         'stage' : 0,
                                         'complete' : False
                                         }
            
            if mech == 'PLAIN':
                msg.conn.data['sasl']['mech'] = 'PLAIN'
                authtext64 = tree[0].text
                plain = mechs.Plain(msg)
                msg.conn.data['sasl']['mechObj'] = plain
                plain.handle(authtext64)
            elif mech == 'DIGEST-MD5':
                msg.conn.data['sasl']['mech'] = 'DIGEST-MD5'
                digest = mechs.DigestMD5(msg)
                msg.conn.data['sasl']['mechObj'] = digest
                digest.handle(msg)
            else:
                logging.warning("Mechanism %s not implemented", mech)
            
        def cb(workReq, retVal):
            self.done = True
            
        req = threadpool.makeRequests(act,
                                 [(None, {'tree' : tree, 'msg' : msg})],
                                 cb)
        
        def checkFunc():
            # need to poll manually or the callback's never called from the pool
            poll(tpool)
            return self.done
        
        def initFunc():
            tpool.putRequest(req[0])
        
        return FunctionCall(checkFunc), FunctionCall(initFunc)
        
    def resume(self): pass
        
class SASLResponseHandler(ThreadedHandler):
    """Handles SASL's <response> element sent from the other side"""
    def __init__(self):
        self.done = False
        
    def handle(self, tree, msg, lastRetVal=None):
        # this is true when the threaded handler returns
        self.done = False
        
        tpool = msg.conn.server.threadpool
        
        # the actual function executing in the thread
        def act(tree, msg):
            try:
                mech = msg.conn.data['sasl']['mechObj']
            except KeyError:
                # TODO: close connection
                logging.warning("Mech object doesn't exist in connection data for %s",
                                msg.conn.addr)
                logging.debug("%s", msg.conn.data)
                return
    
            text = tree[0].text
            if text:
                mech.handle(msg, text.strip())
            else:
                mech.handle(msg, tree)
                
        def cb(workReq, retVal):
            self.done = True
            
        req = threadpool.makeRequests(act,
                                 [(None, {'tree' : tree, 'msg' : msg})],
                                 cb)
        
        def checkFunc():
            # need to poll manually or the callback's never called from the pool
            poll(tpool)
            return self.done
        
        def initFunc():
            tpool.putRequest(req[0])
        
        return FunctionCall(checkFunc), FunctionCall(initFunc)
    
    def resume(self): pass
        
        
class SASLErrorHandler(Handler):
    def handle(self, tree, msg, lastRetVal=None):
        if isinstance(lastRetVal, SASLError):
            el = Element('failure', {'xmlns' : 'urn:ietf:params:xml:ns:xmpp-sasl'})
            el.append(lastRetVal.errorElement())
            
            msg.addTextOutput(tostring(el))
        else:
            logging.warning("SASLErrorHandler was passed a non-SASL exception")
            raise Exception, "can't handle a non-SASL error"
