import logging

from pjs.handlers.base import Handler, chainOutput
from pjs.elementtree.ElementTree import Element, SubElement
from pjs.utils import tostring, generateId

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
                resource = generateId()
            
            msg.conn.data['user']['resource'] = resource
                
            res = Element('iq', {'type' : 'result', 'id' : id})
            bind = Element('bind', {'xmlns' : 'urn:ietf:params:xml:ns:xmpp-bind'})
            jid = Element('jid')
            jid.text = '%s/%s' % (msg.conn.data['user']['jid'], resource)
            bind.append(jid)
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