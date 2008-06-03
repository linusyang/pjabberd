from pjs.handlers.base import Handler
from pjs.elementtree.ElementTree import Element, SubElement
from pjs.utils import tostring

class IQNotImplementedHandler(Handler):
    """Handler that replies to unknown iq stanzas"""
    def handle(self, tree, msg, lastRetVal=None):
        if len(tree) > 0:
            # get the original iq msg
            origIQ = tree[0]
        else:
            # log it
            return
        
        id = origIQ.get('id')
        if id:
            res = Element('iq', {
                                 'type' : 'error',
                                 'id' : id
                                })
            res.append(origIQ)
            
            err = Element('error', {'type' : 'cancel'})
            SubElement(err, 'feature-not-implemented',
                       {'xmlns' : 'urn:ietf:params:xml:ns:xmpp-stanzas'})
            
            res.append(err)
            
            return tostring(res)
        else:
            # log it?
            pass