"""XMPP SASL and iq auth stuff"""
# Some parts are borrowed from twisted. See TWISTED-LICENSE for details on its
# license.

import pjs.auth_mechanisms as mechs
import pjs.threadpool as threadpool
import logging

from pjs.handlers.base import Handler, ThreadedHandler, poll, chainOutput
from pjs.auth_mechanisms import SASLError, IQAuthError
from pjs.handlers.iq import bindResource
from pjs.utils import FunctionCall
from pjs.elementtree.ElementTree import Element, SubElement

iqAuthEl = Element('iq', {'type' : 'result'})
iqAuthQueryEl = SubElement(iqAuthEl, 'query', {
                           'xmlns' : 'jabber:iq:auth'
                           })
SubElement(iqAuthQueryEl, 'username')
SubElement(iqAuthQueryEl, 'digest')
SubElement(iqAuthQueryEl, 'resource')

def checkPolicyViolation(msg):
    """Checks if a SASL auth is being or has been attempted"""
    data = msg.conn.data['sasl']
    if data['in-progress'] or data['complete'] or data['mechObj']:
        # policy violation!
        se = Element('stream:error')
        SubElement(se, 'policy-violation', {
                            'xmlns' : 'urn:ietf:params:xml:ns:xmpp-streams'
                            })
        return se

def makeNotAcceptable(id):
    """Creates the not-acceptable iq error stanza"""
    d = {'type' : 'error'}
    if id:
        d['id'] = id
    iq = Element('iq', d)
    error = SubElement(iq, 'error', {
                                     'code' : '406',
                                     'type' : 'modify'
                                     })
    SubElement(error, 'not-acceptable', {
                                'xmlns' : 'urn:ietf:params:xml:ns:xmpp-stanzas'
                                        })
    return iq

def makeNotAuthorized(id):
    """Creates the not-authorized iq error stanza"""
    d = {'type' : 'error'}
    if id:
        d['id'] = id
    iq = Element('iq', d)
    error = SubElement(iq, 'error', {
                                     'code' : '401',
                                     'type' : 'cancel'
                                     })
    
    SubElement(error, 'not-authorized', {
                               'xmlns' : 'urn:ietf:params:xml:ns:xmpp-stanzas'
                               })
    return iq

def makeConflict(id):
    """Creates the conflict iq error stanza"""
    d = {'type' : 'error'}
    if id:
        d['id'] = id
    iq = Element('iq', d)
    error = SubElement(iq, 'error', {
                                     'code' : '409',
                                     'type' : 'cancel'
                                     })
    SubElement(error, 'conflict', {
                               'xmlns' : 'urn:ietf:params:xml:ns:xmpp-stanzas'
                               })
    return iq

def makeSuccess(id):
    """Creates the auth successful iq stanza"""
    d = {'type' : 'result'}
    if id:
        d['id'] = id
    iq = Element('iq', d)
    return iq

class SASLAuthHandler(ThreadedHandler):
    """Handles SASL's <auth> element sent from the other side"""
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
            data = msg.conn.data
            data['sasl']['in-progress'] = True
            mech = tree.get('mechanism')
            
            if mech == 'PLAIN':
                data['sasl']['mech'] = 'PLAIN'
                authtext64 = tree.text
                plain = mechs.SASLPlain(msg)
                data['sasl']['mechObj'] = plain
                return chainOutput(lastRetVal, plain.handle(authtext64))
            elif mech == 'DIGEST-MD5':
                data['sasl']['mech'] = 'DIGEST-MD5'
                digest = mechs.SASLDigestMD5(msg)
                data['sasl']['mechObj'] = digest
                return chainOutput(lastRetVal, digest.handle())
            else:
                logging.warning("[%s] Mechanism %s not implemented",
                                self.__class__, mech)
            
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
        
class SASLResponseHandler(ThreadedHandler):
    """Handles SASL's <response> element sent from the other side"""
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
            mech = msg.conn.data['sasl']['mechObj']
            if not mech:
                # TODO: close connection
                logging.warning("[%s] Mech object doesn't exist in connection data for %s",
                                self.__class__, msg.conn.addr)
                logging.debug("[%s] %s", self.__class__, msg.conn.data)
                return
    
            text = tree.text
            if text:
                return chainOutput(lastRetVal, mech.handle(text.strip()))
            else:
                return chainOutput(lastRetVal, mech.handle(tree))
                
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

class IQAuthGetHandler(Handler):
    """Handles the old-style iq auth get request sent from the client"""
    def handle(self, tree, msg, lastRetVal=None):
        id = tree.get('id')
        if not id:
            logging.debug("[%s] No id specified in iq-auth get request",
                          self.__class__)
            
        # check for policy violation
        violation = checkPolicyViolation(msg)
        if violation is not None:
            msg.setLastHandler('close-stream')
            return chainOutput(lastRetVal, violation)
        else:
            msg.conn.data['iqauth']['in-progress'] = True
            if id:
                iqAuthEl.set('id', id)
            return chainOutput(lastRetVal, iqAuthEl)
        
class IQAuthSetHandler(ThreadedHandler):
    """Handles the old-style iq auth set sent from the client"""
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
            data = msg.conn.data
            # check for policy violation
            violation = checkPolicyViolation(msg)
            if violation is not None:
                msg.setLastHandler('close-stream')
                return chainOutput(lastRetVal, violation)
            
            id = tree.get('id')
            if not id:
                logging.debug("[%s] No id specified in iq-auth set request",
                              self.__class__)
            
            data['iqauth']['in-progress'] = True
            
            username = tree[0].find('{jabber:iq:auth}username')
            if username is not None:
                username = username.text
            resource = tree[0].find('{jabber:iq:auth}resource')
            if resource is not None:
                resource = resource.text
            
            if username is None or resource is None:
                iq = makeNotAcceptable(id)
                return chainOutput(lastRetVal, iq)
            
            digest = tree[0].find('{jabber:iq:auth}digest')
            if digest is not None:
                digest = digest.text
            password = tree[0].find('{jabber:iq:auth}password')
            if password is not None:
                password = password.text
            
            if digest:
                data['iqauth']['mech'] = 'digest'
                auth = mechs.IQAuthDigest(msg)
                try:
                    auth.handle(username, digest)
                except IQAuthError:
                    return chainOutput(lastRetVal, makeNotAuthorized(id))
            elif password:
                data['iqauth']['mech'] = 'plain'
                plain = mechs.IQAuthPlain(msg)
                try:
                    plain.handle(username, password)
                except IQAuthError:
                    return chainOutput(lastRetVal, makeNotAuthorized(id))
            else:
                iq = makeNotAcceptable(id)
                return chainOutput(lastRetVal, iq)
            
            # do the resource binding
            # TODO: check that we don't already have such a resource
            bindResource(msg, resource)
            
            data['iqauth']['complete'] = True
            
            return chainOutput(lastRetVal, makeSuccess(id))
                
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
        
class SASLErrorHandler(Handler):
    def handle(self, tree, msg, lastRetVal=None):
        if isinstance(lastRetVal, SASLError):
            el = Element('failure', {'xmlns' : 'urn:ietf:params:xml:ns:xmpp-sasl'})
            el.append(lastRetVal.errorElement())
            
            return chainOutput(lastRetVal, el)
        else:
            logging.warning("[%s] SASLErrorHandler was passed a non-SASL " +\
                            "exception. Exception: %s",
                            self.__class__, lastRetVal)
            raise Exception, "can't handle a non-SASL error"
