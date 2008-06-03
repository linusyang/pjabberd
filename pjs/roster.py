"""Models a roster"""

import logging

from pjs.elementtree.ElementTree import Element, SubElement
from pjs.db import DB, DBautocommit, commitSQLiteTransaction

class Roster:
    def __init__(self, jid):
        """Initializes the roster object, but does not fetch any
        roster-specific data from the DB. It checks if the jid
        exists in the roster and raises an exception if it doesn't.

        jid -- textual representation of a bare JID.
        """
        self.items = {}
        self.jid = jid

        con = DBautocommit()
        c = con.cursor()
        # get our own id
        c.execute("SELECT id FROM jids WHERE jid = ?", (self.jid,))
        res = c.fetchone()
        if res is None:
            raise Exception, "No record of this JID in the DB"

        self.uid = res[0]

    def addItem(self, contactId, rosterItem):
        """Adds a RosterItem for the contactId in this roster.

        contactId -- integer id of the contact in the DB.
        rosterItem -- RosterItem object.
        """
        self.items[contactId] = rosterItem

    def addGroup(self, contactId, group):
        """Adds a <group> entry for contactId in this roster.

        contactId -- integer id of the contact in the DB.
        group -- group name.
        """
        try:
            self.items[contactId].groups.append(group)
        except KeyError, e:
            logging.warning("[%s] Adding a group %s to cid %d " + \
                            "failed because the cid doesn't exist in the roster",
                            self.__class__, group, contactId)

    def getContactInfo(self, cjid, includeGroups=True):
        """Returns information about a contact with JID cjid in this user's
        roster. Returns a RosterItem if the contact exists in the roster;
        False otherwise.
        If includeGroups is True, groups are added to the RosterItem as well.
        """
        con = DBautocommit()
        c = con.cursor()

        c.execute("SELECT roster.contactid, roster.name, roster.subscription\
                   FROM roster\
                       JOIN jids ON jids.id = roster.contactid\
                   WHERE userid = ? AND jids.jid = ?", (self.uid, cjid))
        res = c.fetchone()
        if res:
            cid = res[0]
            name = res[1]
            sub = res[2]
        else:
            c.close()
            return False

        if includeGroups:
            # get the groups
            c.execute("SELECT rgs.name\
                       FROM rostergroups AS rgs\
                           JOIN rostergroupitems AS rgi ON rgi.groupid = rgs.groupid\
                       WHERE rgs.userid = ? AND rgi.contactid = ?", (self.uid, cid))
            groups = [group['name'] for group in c]

            return RosterItem(cjid, name, sub, groups, cid)
        else:

            return RosterItem(cjid, name, sub, id=cid)

    def updateContact(self, cjid, groups=None, name=None, subscriptionId=None):
        """Adds or updates a contact in this user's roster. Returns the
        contact's id in the DB.
        groups can be None, which means that all groups are to be removed
        Otherwise, groups is a list of groups the contact belongs to.
        """

        name = name or ''
        groups = groups or []

        con = DB()
        c = con.cursor()

        # check if this is an update to an existing roster entry
        c.execute("SELECT cjids.id cid \
                   FROM roster\
                   JOIN jids AS cjids ON cjids.id = roster.contactid\
                   JOIN jids AS ujids ON ujids.id = roster.userid\
                   WHERE ujids.jid = ? AND cjids.jid = ?", (self.jid, cjid))
        res = c.fetchone()
        if res:
            # this is an update
            # we update the subscription if it's given to us; o/w
            # just update the name
            cid = res[0]
            if subscriptionId:
                c.execute("UPDATE roster SET name = ?, subscription = ?\
                           WHERE contactid = ?",
                          (name, cid, subscriptionId))
            else:
                c.execute("UPDATE roster SET name = ?\
                           WHERE contactid = ?",
                          (name, cid))
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
                       (?, ?, ?, ?)",
                       (self.uid, cid, name,
                        subscriptionId or Subscription.NONE))


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
                       WHERE userid = ? AND name = ?", (self.uid, groupName))
            res = c.fetchone()
            if res:
                gid = res[0]
            else:
                # need to create the group
                res = c.execute("INSERT INTO rostergroups\
                                 (userid, name)\
                                 VALUES\
                                 (?, ?)", (self.uid, groupName))
                gid = res.lastrowid

            c.execute("INSERT INTO rostergroupitems\
                       (groupid, contactid)\
                       VALUES\
                       (?, ?)", (gid, cid))

        commitSQLiteTransaction(con, c)

        return cid

    def removeContact(self, cjid):
        """Removes the contact from this user's roster. Returns the contact's
        id in the DB.

        cjid -- bare JID or the contact as a string.
        """
        con = DB()
        c = con.cursor()

        # get the contact's id
        c.execute("SELECT jids.id\
                   FROM roster\
                   JOIN jids ON roster.contactid = jids.id\
                   WHERE roster.userid = ? AND jids.jid = ?", (self.uid, cjid))
        res = c.fetchone()
        if res:
            cid = res[0]
        else:
            logging.info("[%s] Contact %s does not exist in roster of %s",
                         self.__class__, cjid, self.jid)
            commitSQLiteTransaction(con, c)
            con.close()
            return False

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

        commitSQLiteTransaction(con, c)

        return cid

    def getSubscription(self, cid):
        """Returns the subscription id of this user's contact with id cid"""
        con = DBautocommit()
        c = con.cursor()
        c.execute("SELECT subscription FROM roster\
                   WHERE userid = ? AND contactid = ?", (self.uid, cid))
        res = c.fetchone()
        if res:
            sub = res[0]

            return sub
        else:
            raise Exception, "No such contact in roster"

    def setSubscription(self, cid, sub):
        """Sets the subscription from the perspective of this user to a
        contact with ID cid to sub, which is an id retrieved via the
        Subscription class.
        """
        con = DB()
        c = con.cursor()
        c.execute("UPDATE roster SET subscription = ?\
                   WHERE userid = ? AND contactid = ?", (sub, self.uid, cid))
        commitSQLiteTransaction(con, c)

    def getSubPrimaryName(self, cid):
        """Gets the primary name of a subscription for this user and this
        contact suitable for including in the subscription attribute of a
        roster's item element.
        """
        con = DBautocommit()
        c = con.cursor()
        c.execute("SELECT subscription FROM roster\
                       WHERE roster.userid = ? AND roster.contactid = ?", (self.uid, cid))
        res = c.fetchone()
        if res is None:
            sub = 'none'
        else:
            sub = Subscription.getPrimaryNameFromState(res[0])

        return sub

    def getPresenceSubscribers(self):
        """Returns a list of JIDs of contacts of this user who are interested
        in the user's presence info (from/both).
        """
        con = DBautocommit()
        c = con.cursor()
        c.execute("SELECT jids.jid\
                   FROM roster\
                   JOIN jids ON jids.id = roster.contactid\
                   WHERE roster.userid = ? AND\
                       roster.subscription IN (?, ?, ?)",
                       (self.uid, Subscription.FROM,
                        Subscription.FROM_PENDING_OUT, Subscription.BOTH))
        jids = []
        res = c.fetchall()
        for row in res:
            jids.append(row[0])

        return jids

    def getPresenceSubscriptions(self):
        """Returns a list of JIDs of contacts of this user to whom the user
        is subscribed (to/both).
        """
        con = DBautocommit()
        c = con.cursor()
        c.execute("SELECT jids.jid\
                   FROM roster\
                   JOIN jids ON jids.id = roster.contactid\
                   WHERE roster.userid = ? AND\
                       roster.subscription IN (?, ?, ?)",
                       (self.uid, Subscription.TO,
                        Subscription.TO_PENDING_IN, Subscription.BOTH))
        jids = []
        res = c.fetchall()
        for row in res:
            jids.append(row[0])

        return jids

    def loadRoster(self):
        """Loads the roster for this JID. Must be used before calling
        getAsTree().
        """
        con = DB()
        c = con.cursor()
        # get the contactid, name and subscriptions
        c.execute("SELECT roster.contactid, roster.name,\
                          roster.subscription,\
                          contactjids.jid cjid\
                   FROM roster\
                       JOIN jids AS userjids ON roster.userid = userjids.id\
                       JOIN jids AS contactjids ON roster.contactid = contactjids.id\
                   WHERE userjids.jid = ? AND\
                       roster.subscription != ?",
                       (self.jid, Subscription.NONE_PENDING_IN))

        self.items = {}
        for row in c:
            self.addItem(row['contactid'],
                         RosterItem(row['cjid'], row['name'], row['subscription']))

        # get the groups now for each cid
        c.execute("SELECT rgi.contactid, rgs.name\
                   FROM rostergroups AS rgs\
                       JOIN rostergroupitems AS rgi ON rgi.groupid = rgs.groupid\
                       JOIN jids ON rgs.userid = jids.id\
                   WHERE jids.jid = ?", (self.jid,))

        for row in c:
            self.addGroup(row['contactid'], row['name'])

        commitSQLiteTransaction(con, c)

    def getAsTree(self):
        """Returns the roster Element tree starting from <query>. Call
        loadRoster() before this.
        """
        query = Element('query', {'xmlns' : 'jabber:iq:roster'})
        for item in self.items:
            query.append(self.items[item].getAsTree())

        return query

    def createRosterQuery(cjid, subName, name=None, groups=None, itemArgs=None):
        """Creates and returns a <query> item for sending in an <iq> in a
        roster push.
        cjid -- jid as a str for the contact in a roster item.
        subName -- name of the subscription as a str.
        name -- name for the contact. Can be None.
        groups -- list of group names as strings.
        """
        itemArgs = itemArgs or {}
        query = Element('query', {'xmlns' : 'jabber:iq:roster'})

        d = {
             'jid' : cjid,
             'subscription' : subName,
             }
        if name:
            d['name'] = name

        d.update(itemArgs)

        item = SubElement(query, 'item', d)

        for groupName in groups:
            if groupName: # don't want empty groups
                group = Element('group')
                group.text = groupName
                item.append(group)

        return query
    createRosterQuery = staticmethod(createRosterQuery)

class RosterItem:
    """Models the <item> element in a roster query"""
    def __init__(self, jid=None, name=None, subscription=None, groups=None, id=None):
        """Creates a new RosterItem.
        All attributes are optional and only the jid and subscription are
        required for meaningful use in a roster send. id is the contact's id
        in the database. Subscription is the subscription id in the DB.
        """
        self.id = id
        self.jid = jid
        self.name = name
        self.subscription = subscription # id, not name
        self.groups = groups or []

    def getAsTree(self):
        """Return the roster item as an Element tree starting from <item>"""
        item = Element('item', {
                                'jid' : self.jid,
                                'subscription' : Subscription.getPrimaryNameFromState(self.subscription)
                                })
        if self.name:
            item.set('name', self.name)
        for group in self.groups:
            SubElement(item, 'group').text = group

        return item

class Subscription(object):
    """Defines a subscription state. Provides static methods to determine the
    primary name from the stateid.
    """

    NONE = 0
    NONE_PENDING_OUT = 1
    NONE_PENDING_IN = 2
    NONE_PENDING_IN_OUT = 3
    TO = 4
    TO_PENDING_IN = 5
    FROM = 6
    FROM_PENDING_OUT = 7
    BOTH = 8

    state2primaryName = {
                         NONE : 'none',
                         NONE_PENDING_OUT : 'none',
                         NONE_PENDING_IN : 'none',
                         NONE_PENDING_IN_OUT : 'none',
                         TO : 'to',
                         TO_PENDING_IN : 'to',
                         FROM : 'from',
                         FROM_PENDING_OUT : 'from',
                         BOTH : 'both'
                         }

    def getPrimaryNameFromState(st):
        """Returns the name of a primary state (none, to, from, both) from a
        state constant.
        """
        return Subscription.state2primaryName[st]

    getPrimaryNameFromState = staticmethod(getPrimaryNameFromState)
