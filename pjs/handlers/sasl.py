"""XMPP SASL stuff"""
# Some parts are borrowed from twisted. See TWISTED-LICENSE for details on its
# license.

from pjs.handlers.base import Handler
from pjs.db import db
from pjs.elementtree.ElementTree import Element
import pjs.sasl_mechanisms as mechs
import re

try:
    # Python >= 2.4
    from base64 import b64decode, b64encode
except ImportError:
    import base64

    def b64encode(s):
        return "".join(base64.encodestring(s).split("\n"))

    b64decode = base64.decodestring
    
base64Pattern = re.compile("^[0-9A-Za-z+/]*[0-9A-Za-z+/=]{,2}$")

def fromBase64(s):
    """
    Decode base64 encoded string.

    This helper performs regular decoding of a base64 encoded string, but also
    rejects any characters that are not in the base64 alphabet and padding
    occurring elsewhere from the last or last two characters, as specified in
    section 14.9 of RFC 3920. This safeguards against various attack vectors
    among which the creation of a covert channel that "leaks" information.
    """

    if base64Pattern.match(s) is None:
        raise

    return b64decode(s) # could raise an exception if cannot decode

class SASLAuthHandler(Handler):
    def __init__(self):
        pass
    
    def handle(self, tree, msg, lastRetVal=None):
        mech = tree[0].get('mechanism', 'PLAIN')
        
        if not msg.conn.data.has_key('sasl'):
            msg.conn.data['sasl'] = {
                                     'mech' : '',
                                     'challenge' : '',
                                     'stage' : 0,
                                     'complete' : False
                                     }
        
        if mech == 'PLAIN':
            msg.conn.data['sasl']['mech'] = 'PlAIN'
            authtext64 = tree[0].text
            authtext = ''
            if authtext64:
                try:
                    authtext = fromBase64(authtext64)
                except:
                    # TODO: raise exception or chain an error-handler
                    pass
                
                auth = authtext.split('\x00')
                
                if len(auth) != 3:
                    # TODO: raise exception or chain an error handler
                    pass
                
                c = db.cursor()
                c.execute("SELECT * FROM users WHERE \
                    username = ? AND password = ?", (auth[1], auth[2]))
                res = c.fetchall()
                if len(res) == 0:
                    # TODO: denied. raise exception or chain an error handler
                    pass
                else:
                    msg.addTextOutput(u"<success xmlns='urn:ietf:params:xml:ns:xmpp-sasl'/>")
        elif mech == 'DIGEST-MD5':
            msg.conn.data['sasl']['mech'] = 'DIGEST-MD5'
        else:
            # log it
            return
        
        