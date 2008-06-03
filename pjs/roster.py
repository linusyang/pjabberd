import logging

from pjs.elementtree.ElementTree import Element, SubElement
from pjs.db import DB

class Roster:
    def __init__(self, jid):
        self.items = {}
        self.jid = jid
        
        c = DB().cursor()
        # get our own id
        c.execute("SELECT id FROM jids WHERE jid = ?", (self.jid,))
        res = c.fetchone()
        if res is None:
            raise Exception, "No record of this JID in the DB"
        
        self.uid = res[0]
        
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
    
    def updateContact(self, cjid, groups, name=None):
        """Adds or updates a contact in this user's roster. Returns the
        contact's id in the DB.
        """
        c = DB().cursor()
        
        # check if this is an update to an existing roster entry
        c.execute("SELECT cjids.id cid \
                   FROM roster\
                   JOIN jids AS cjids ON cjids.id = roster.contactid\
                   JOIN jids AS ujids ON ujids.id = roster.userid\
                   WHERE ujids.jid = ? AND cjids.jid = ?", (self.jid, cjid))
        res = c.fetchone()
        if res:
            # this is an update
            # we don't update the subscription as it's the job of <presence>
            cid = res[0]
            c.execute("UPDATE roster SET name = ? WHERE contactid = ?",
                      (name or '', cid))
        else:
            # this is a new roster entry
            
            # check if the contact JID already exists in our DB
            c.execute("SELECT id FROM jids WHERE jid = ?", (cjid,))
            res = c.fetchone()
            if res:
                cid = res[0]
            else:
                # create new JID entry
                res = c.execute("INSERT INTO jids\
                                 (jid, password)\
                                 VALUES\
                                 (?, '')", (cjid,))
                cid = res.lastrowid
                
            c.execute("INSERT INTO roster\
                       (userid, contactid, name, subscription)\
                       VALUES\
                       (?, ?, ?, ?)", (self.uid, cid, name or '', 0))
                
                
        # UPDATE GROUPS
        # remove all group mappings for this contact and recreate
        # them, since it's easier than figuring out what changed
        c.execute("DELETE FROM rostergroupitems\
                   WHERE contactid = ? AND groupid IN\
                   (SELECT groupid FROM rostergroups WHERE\
                       userid = ?)", (cid, self.uid))
        for groupName in groups:
            # get the group id
            c.execute("SELECT groupid\
                       FROM rostergroups\
                       WHERE userid = ? AND name = ?", (self.uid, groupName.text))
            res = c.fetchone()
            if res:
                gid = res[0]
            else:
                # need to create the group
                res = c.execute("INSERT INTO rostergroups\
                                 (userid, name)\
                                 VALUES\
                                 (?, ?)", (self.uid, groupName.text))
                gid = res.lastrowid
            
            c.execute("INSERT INTO rostergroupitems\
                       (groupid, contactid)\
                       VALUES\
                       (?, ?)", (gid, cid))
        c.close()
            
        return cid
    
    def removeContact(self, cjid):
        """Removes the contact from this user's roster. Returns the contact's
        id in the DB.
        """
        c = DB().cursor()
        
        # get the contact's id
        c.execute("SELECT jids.id\
                   FROM roster\
                   JOIN jids ON roster.contactid = jids.id\
                   WHERE roster.userid = ? AND jids.jid = ?", (self.uid, cjid))
        res = c.fetchone()
        if res:
            cid = res[0]
        else:
            raise Exception, "No such contact in user's roster"
        
        # delete the contact from all groups it's in for this user
        c.execute("DELETE FROM rostergroupitems\
                   WHERE rostergroupitems.groupid IN (\
                       SELECT rgs.groupid FROM rostergroups AS rgs\
                       JOIN rostergroupitems AS rgi ON rgi.groupid = rgs.groupid\
                       WHERE rgs.userid = ?\
                    ) AND rostergroupitems.contactid = ?", (self.uid, cid))
        
        # now delete the roster entry
        c.execute("DELETE FROM roster\
                   WHERE userid = ? AND contactid = ?", (self.uid, cid))
        
        return cid
        
    
    def getSubPrimaryName(self, cid):
        """Gets the primary name of a subscription for this user and this
        contact suitable for including in the subscription attribute of a
        roster's item element.
        """
        c = DB().cursor()
        c.execute("SELECT primaryname FROM substates\
                       JOIN roster on roster.subscription = substates.stateid\
                       WHERE roster.userid = ? AND roster.contactid = ?", (self.uid, cid))
        res = c.fetchone()
        if res is None:
            sub = 'none'
        else:
            sub = res[0]
            
        c.close()
        
        return sub
    
    def loadRoster(self):
        """Loads the roster for this JID"""
        c = DB().cursor()
        # get the contactid, name and subscriptions
        c.execute("SELECT roster.contactid, roster.name,\
                          substates.primaryName subscription,\
                          contactjids.jid cjid\
                   FROM roster\
                       JOIN jids AS userjids ON roster.userid = userjids.id\
                       JOIN jids AS contactjids ON roster.contactid = contactjids.id\
                       JOIN substates ON substates.stateid = roster.subscription\
                   WHERE userjids.jid = ?", (self.jid,))
        
        for row in c:
            self.addItem(row['contactid'], RosterItem(row['cjid'], row['name'], row['subscription']))
        
        # get the groups now for each cid
        c.execute("SELECT rgi.contactid, rgs.name\
                   FROM rostergroups AS rgs\
                       JOIN rostergroupitems AS rgi ON rgi.groupid = rgs.groupid\
                       JOIN jids ON rgs.userid = jids.id\
                   WHERE jids.jid = ?", (self.jid,))
        
        for row in c:
            self.addGroup(row['contactid'], row['name'])
            
        c.close()
    
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
        """Return the roster item as an Element tree starting from <item>"""
        item = Element('item', {
                                'jid' : self.jid,
                                'subscription' : self.subscription
                                })
        if self.name:
            item.set('name', self.name)
        for group in self.groups:
            SubElement(item, 'group').text = group
            
        return item
