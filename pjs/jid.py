import re
from pjs.db import DBautocommit
import logging

class JID:
    """Models a JID"""

    # TODO: fix this to do stringprep and abide by the size limits in
    # RFC 3920 section 3.1.
    jidre = re.compile(r'((\w*)@)?([\w.]+)(/(.+))?', re.I)
    
    def __init__(self, jid, use_id=False):
        """Tries to create a JID out of 'jid'. Raises an exception if the JID
        is malformed.
        """
        if use_id:
            jid_number = jid
            res = None
            try:
                c = DBautocommit().cursor()
                c.execute("SELECT jid FROM jids WHERE id = %d" %
                          (jid_number))
                res = c.fetchone()
            except:
                logging.debug('JID: init from number failed')
            if res and len(res) > 0:
                jid = res[0]
            else:
                jid = ''
        m = JID.jidre.match(jid)
        if not m:
            raise Exception, '[JID] %s is not a proper JID' % jid
    
        self.node = m.group(2)
        self.domain = m.group(3)
        self.resource = m.group(5)
        
    def getBare(self):
        return '%s@%s' % (self.node, self.domain)

    def getNumId(self):
        """Returns this JID's database numeric ID"""
        res = None
        try:
            c = DBautocommit().cursor()
            c.execute("SELECT id FROM jids WHERE jid = ?",
                      (self.getBare(),))
            res = c.fetchone()
        except:
            logging.debug('JID: get numeric ID failed')
        if res and len(res) > 0:
            return res[0]
        else:
            return -1
    
    def exists(self):
        """Returns True if this JID exists in the DB"""
        res = None
        try:
            c = DBautocommit().cursor()
            c.execute("SELECT jid FROM jids WHERE jid = ? AND password != ''",
                      (self.getBare(),))
            res = c.fetchone()
        except:
            logging.debug('JID: check existence failed')
        if res:
            return True
        else:
            return False
        
    def __cmp__(self, other):
        assert isinstance(other, JID)
        if self.node == other.node and self.domain == other.domain\
            and self.resource == other.resource:
            return 0
        else:
            return -1
        
    def __str__(self):
        out = self.domain
        if self.node:
            out = self.node + '@' + out
        if self.resource:
            out = out + '/' + self.resource
        return out