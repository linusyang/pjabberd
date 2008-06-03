import logging

from pjs.elementtree.ElementTree import Element, SubElement

class Roster:
    def __init__(self):
        self.items = {}
        
    def addItem(self, contactId, rosterItem):
        """Adds a RosterItem for the contactId in this roster"""
        self.items[contactId] = rosterItem
        
    def addGroup(self, contactId, group):
        """Adds a <group> entry for contactId in this roster"""
        try:
            self.items[contactId].groups.append(group)
        except KeyError, e:
            logging.warning("[roster] Adding a group %s to cid %d " + \
                            "failed because the cid doesn't exist in the roster",
                            group, contactId)
    def getAsTree(self):
        """Returns the roster Element tree starting from <query>"""
        query = Element('query', {'xmlns' : 'jabber:iq:roster'})
        for item in self.items:
            query.append(self.items[item].getAsTree())
            
        return query

class RosterItem:
    """Models the <item> element in a roster"""
    def __init__(self, jid=None, name=None, subscription=None, groups=None):
        self.jid = jid
        self.name = name
        self.subscription = subscription
        self.groups = groups or []
        
    def getAsTree(self):
        item = Element('item', {
                                'jid' : self.jid,
                                'subscription' : self.subscription
                                })
        if self.name:
            item.set('name', self.name)
        for group in self.groups:
            SubElement(item, 'group').text = group
            
        return item