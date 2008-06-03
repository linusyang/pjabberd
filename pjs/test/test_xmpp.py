""" Core protocol testing """

import pjs.test.init # initialize the launcher
import pjs.conf.conf
import unittest
import xmpp
import threading
import time
import pjs.conf.handlers as handlers

from pjs.db import DB, sqlite

from copy import deepcopy

# length of time to wait for each test.
# we wait for a very long time if we're debugging
import os

if 'DEBUG' in os.environ:
    WAITLEN = 99999999
else:
    WAITLEN = 2

# constants
TEST_PRESDB_NAME = 'test-presdb'
TEST_NOROSTER_NAME = 'test-noroster'

# for the asyncore thread
shutdownAsyncore = False
def checkShutdown(): return shutdownAsyncore

# we need to run asyncore in a separate thread because it blocks
class AsyncoreThread(threading.Thread):
    """Runs the asyncore main loop in a thread"""
    def __init__(self, stopfunc):
        threading.Thread.__init__(self)
        self.stopfunc = stopfunc
    def run(self):
        import pjs.async.core

        try:
            while not self.stopfunc():
                pjs.async.core.loop(timeout=1, count=2)
        except: pass

class TestThread(threading.Thread):
    """Performs some work in a thread and catches exceptions"""
    def __init__(self, func):
        threading.Thread.__init__(self)
        self.func = func
        self.exc = False
    def run(self):
        try:
            self.func()
        except Exception, e:
            self.exc = e

class MessageBot:
    """xmpppy handler that records all messages sent to it"""
    def __init__(self, cl, remotejid):
        """cl -- client instance (one that's listening for events)
        remotejid -- the JID from which we're expecting a msg
        """
        self.cl = cl
        self.cl.RegisterHandler('message', self.xmpp_message)
        self.remotejid = remotejid

        self.msgrecord = {}

    def xmpp_message(self, con, event):
        type = event.getType()
        fromjid = event.getFrom().getStripped()
        if type in ['message', 'chat', None] and fromjid == self.remotejid:
            self.msgrecord.setdefault(fromjid, [])
            self.msgrecord[fromjid].append(event.getBody())
            
class PresenceBot:
    """xmpppy handler that records all presence stanzas sent to it"""
    def __init__(self, cl, remotejid):
        """cl -- client instance (one that's listening for events)
        remotejid -- the JID from which we're expecting a msg
        """
        self.cl = cl
        self.cl.RegisterHandler('presence', self.xmpp_presence)
        self.remotejid = remotejid
        
        self.presencerecord = []
        
    def xmpp_presence(self, con, event):
        type = event.getType()
        fromjid = event.getFrom().getStripped()
        if type in ['presence', None] and fromjid == self.remotejid:
            self.presencerecord.append(fromjid)

class TestStreams(unittest.TestCase):
    """Tests the stream initiation and closing. These tests use the
    xmpppy library from http://xmpppy.sourceforge.net/.
    Each test should be run in a thread because:
      1. we want to make sure that operations complete within a reasonable
         amount of time.
      2. if there's an exception in the server, xmpppy will block for a long
         time and the tests won't complete.
    """
    def setUp(self):
        unittest.TestCase.setUp(self)

        initPresenceDB() # we just need to be able to login

        global shutdownAsyncore
        shutdownAsyncore = False

        pjs.conf.conf.launcher.run()

        self.jid = xmpp.protocol.JID('bob@localhost/test')
        self.password = 'test'
        self.cl = xmpp.Client(self.jid.getDomain(), debug=[])

        self.thread = AsyncoreThread(checkShutdown)
        self.thread.start()

        time.sleep(0.1) # give the thread some time to start

    def tearDown(self):
        unittest.TestCase.tearDown(self)

        global shutdownAsyncore
        shutdownAsyncore = True

        self.thread.join()

        pjs.conf.conf.launcher.stop()

    def testStreamInit(self):
        """Stream initiation"""
        def run():
            con = self.cl.connect(use_srv=False)
            self.assert_(con, "Connection could not be created")

        test = TestThread(run)
        test.start()
        test.join(WAITLEN)
        if test.isAlive():
            self.fail("Test took too long to execute")
        if test.exc:
            self.fail(test.exc)

    def testSASLAuth(self):
        """SASL default authentication (DIGEST-MD5)"""
        def run():
            con = self.cl.connect(use_srv=False)
            if con:
                auth = self.cl.auth(self.jid.getNode(), self.password, self.jid.getResource(), sasl=1)

                self.assert_(auth, "Could not authenticate with SASL")
            else:
                self.fail("Connection failed")

        test = TestThread(run)
        test.start()
        test.join(WAITLEN)
        if test.isAlive():
            self.fail("Test took too long to execute")
        if test.exc:
            self.fail(test.exc)

    def testSASLPLAINAuth(self):
        """SASL PLAIN authentication"""
        # save handlers and reset them later
        oldhandlers = deepcopy(handlers.handlers)

        from pjs.handlers.base import Handler, chainOutput
        from pjs.elementtree.ElementTree import Element, SubElement

        class FeaturesAuthHandler(Handler):
            """Sends out only the PLAIN features after connection"""
            def handle(self, tree, msg, lastRetVal=None):
                res = Element('stream:features')
                mechs = SubElement(res, 'mechanisms',
                                   {'xmlns' : 'urn:ietf:params:xml:ns:xmpp-sasl'})
                SubElement(mechs, 'mechanism').text = 'PLAIN'

                return chainOutput(lastRetVal, res)

        # this should be features-auth, but we only use init for now. fix later
        #handlers.replaceHandler('features-init', FeaturesAuthHandler)
        handlers.handlers['features-init']['handler'] = FeaturesAuthHandler

        def run():
            con = self.cl.connect(use_srv=False)
            if con:
                auth = self.cl.auth(self.jid.getNode(), self.password, self.jid.getResource(), sasl=1)

                self.assert_(auth, "Could not authenticate with SASL")
            else:
                self.fail("Connection failed")

        test = TestThread(run)
        test.start()
        test.join(WAITLEN)

        # restore the handlers
        handlers.handlers = oldhandlers

        if test.isAlive():
            self.fail("Test took too long to execute")
        if test.exc:
            self.fail(test.exc)

    def testNonSASLAuth(self):
        """Non-SASL auth"""
        def run():
            con = self.cl.connect(use_srv=False)
            if con:
                auth = self.cl.auth(self.jid.getNode(), self.password, self.jid.getResource(), sasl=0)

                self.assert_(auth, "Could not authenticate with SASL")
            else:
                self.fail("Connection failed")

        test = TestThread(run)
        test.start()
        test.join(WAITLEN)
        if test.isAlive():
            self.fail("Test took too long to execute")
        if test.exc:
            self.fail(test.exc)

class TestPresenceRoster(unittest.TestCase):
    """Tests sending of presence using xmpppy. See note in TestStreams about
    why these tests run in threads.
    """
    def setUp(self):
        unittest.TestCase.setUp(self)

        initPresenceDB()

        global shutdownAsyncore
        shutdownAsyncore = False

        pjs.conf.conf.launcher.run()

        self.jid = xmpp.protocol.JID('alice@localhost/test')
        self.password = 'test'
        self.cl = xmpp.Client(self.jid.getDomain(), debug=[])
        self.jid2 = xmpp.protocol.JID('bob@localhost/bob')
        self.password2 = 'test'
        self.cl2 = xmpp.Client(self.jid2.getDomain(), debug=[])

        self.thread = AsyncoreThread(checkShutdown)
        self.thread.start()

        time.sleep(0.1) # give the thread some time to start

    def tearDown(self):
        unittest.TestCase.tearDown(self)

        global shutdownAsyncore
        shutdownAsyncore = True

        self.thread.join()

        pjs.conf.conf.launcher.stop()
        
        deletePresenceDB()

    def testRosterGet(self):
        """Initial presence with roster get"""
        def run():
            con = self.cl.connect(use_srv=False)
            if con:
                auth = self.cl.auth(self.jid.getNode(), self.password, self.jid.getResource(), sasl=1)
                if auth:
                    self.cl.sendInitPresence()
                    time.sleep(0.1)
                    self.cl.Dispatcher.Process()
                    self.assert_(self.cl.Roster._data.has_key(self.jid2.getStripped()))
                else:
                    self.fail("Authentication failed")
            else:
                self.fail("Connection failed")

        test = TestThread(run)
        test.start()
        test.join(WAITLEN)
        if test.isAlive():
            self.fail("Test took too long to execute")
        if test.exc:
            self.fail(test.exc)

    # FIXME: This test doesn't work yet, because xmpppy doesn't seem to add the
    # announced resource to its roster list even though it receives the presence
    def testPresence(self):
        """Online initial presence"""
        def run():
            con = self.cl.connect(use_srv=False)
            con2 = self.cl2.connect(use_srv=False)
            if con and con2:
                auth = self.cl.auth(self.jid.getNode(), self.password, self.jid.getResource(), sasl=1)
                auth2 = self.cl2.auth(self.jid2.getNode(), self.password2, self.jid2.getResource(), sasl=1)
                if auth and auth2:
                    bot = PresenceBot(self.cl2, self.jid.getStripped())
                    self.cl.sendInitPresence()
                    time.sleep(0.5)
                    self.cl.Dispatcher.Process()
                    self.cl2.sendInitPresence()
                    time.sleep(0.5)
                    self.cl2.Dispatcher.Process()
                    self.assert_(self.jid.getStripped() in bot.presencerecord)
                else:
                    self.fail("Authentication failed")
            else:
                self.fail("Connections failed")

        test = TestThread(run)
        test.start()
        test.join(WAITLEN)
        if test.isAlive():
            self.fail("Test took too long to execute")
        if test.exc:
            self.fail(test.exc)

    def testMessage(self):
        """Simple single message"""
        def run():
            con = self.cl.connect(use_srv=False)
            con2 = self.cl2.connect(use_srv=False)
            if con and con2:
                auth = self.cl.auth(self.jid.getNode(), self.password, self.jid.getResource(), sasl=1)
                auth2 = self.cl2.auth(self.jid2.getNode(), self.password2, self.jid2.getResource(), sasl=1)
                if auth and auth2:
                    self.cl.sendInitPresence()
                    time.sleep(0.2)
                    self.cl.Dispatcher.Process()
                    self.cl2.sendInitPresence()
                    time.sleep(0.2)
                    self.cl2.Dispatcher.Process()

                    bot = MessageBot(self.cl, self.jid2.getStripped())
                    self.cl2.send(xmpp.protocol.Message(self.jid, "test\n"))
                    time.sleep(0.2)
                    self.cl.Dispatcher.Process(1)
                    self.assert_(bot.msgrecord.has_key(self.jid2.getStripped()))
                else:
                    self.fail("Authentication failed")
            else:
                self.fail("Connections failed")

        test = TestThread(run)
        test.start()
        test.join(WAITLEN)
        if test.isAlive():
            self.fail("Test took too long to execute")
        if test.exc:
            self.fail(test.exc)

class TestSubscriptions(unittest.TestCase):
    """Tests subscriptions using xmpppy"""
    def setUp(self):
        unittest.TestCase.setUp(self)

        initNoRosterItemsDB()

        global shutdownAsyncore
        shutdownAsyncore = False

        pjs.conf.conf.launcher.run()

        self.jid = xmpp.protocol.JID('alice@localhost/test')
        self.password = 'test'
        self.cl = xmpp.Client(self.jid.getDomain(), debug=[])
        self.jid2 = xmpp.protocol.JID('bob@localhost/bob')
        self.password2 = 'test'
        self.cl2 = xmpp.Client(self.jid2.getDomain(), debug=[])

        self.thread = AsyncoreThread(checkShutdown)
        self.thread.start()

        time.sleep(0.1) # give the thread some time to start

    def tearDown(self):
        unittest.TestCase.tearDown(self)

        global shutdownAsyncore
        shutdownAsyncore = True

        self.thread.join()

        pjs.conf.conf.launcher.stop()
        
        deleteNoRosterItemsDB()
        
    def testAdd(self):
        """Tests positive path of subscriptions"""
        def run():
            con = self.cl.connect(use_srv=False)
            con2 = self.cl2.connect(use_srv=False)
            if con and con2:
                auth = self.cl.auth(self.jid.getNode(), self.password, self.jid.getResource(), sasl=1)
                auth2 = self.cl2.auth(self.jid2.getNode(), self.password2, self.jid2.getResource(), sasl=1)
                if auth and auth2:
                    self.cl.sendInitPresence()
                    time.sleep(0.1)
                    self.cl.Dispatcher.Process()
                    self.cl2.sendInitPresence()
                    time.sleep(0.1)
                    self.cl2.Dispatcher.Process()
                    self.cl.Roster.Subscribe(self.jid2.getStripped())
                    self.cl.Roster.setItem(self.jid2.getStripped())
                    time.sleep(0.2)
                    self.cl.Dispatcher.Process()
                    self.cl2.Dispatcher.Process()
                    self.cl2.Roster.Authorize(self.jid.getStripped())
                    time.sleep(0.2)
                    self.cl.Dispatcher.Process()
                    self.cl2.Dispatcher.Process()
                    self.assert_(self.cl.Roster.getSubscription(self.jid2.getStripped()) == 'to')
                else:
                    self.fail("Authentication failed")
            else:
                self.fail("Connections failed")

        test = TestThread(run)
        test.start()
        test.join(WAITLEN)
        if test.isAlive():
            self.fail("Test took too long to execute")
        if test.exc:
            self.fail(test.exc)
            
    def testAddBoth(self):
        """Tests positive path of subscriptions for both parties"""
        def run():
            con = self.cl.connect(use_srv=False)
            con2 = self.cl2.connect(use_srv=False)
            if con and con2:
                auth = self.cl.auth(self.jid.getNode(), self.password, self.jid.getResource(), sasl=1)
                auth2 = self.cl2.auth(self.jid2.getNode(), self.password2, self.jid2.getResource(), sasl=1)
                if auth and auth2:
                    self.cl.sendInitPresence()
                    time.sleep(0.1)
                    self.cl.Dispatcher.Process()
                    self.cl2.sendInitPresence()
                    time.sleep(0.1)
                    self.cl2.Dispatcher.Process()
                    self.cl.Roster.Subscribe(self.jid2.getStripped())
                    self.cl.Roster.setItem(self.jid2.getStripped())
                    time.sleep(0.1)
                    self.cl.Dispatcher.Process()
                    self.cl2.Dispatcher.Process()
                    self.cl2.Roster.Authorize(self.jid.getStripped())
                    time.sleep(0.1)
                    self.cl.Dispatcher.Process()
                    self.cl2.Dispatcher.Process()
                    self.assert_(self.cl.Roster.getSubscription(self.jid2.getStripped()) == 'to')
                    
                    self.cl2.Roster.Subscribe(self.jid.getStripped())
                    self.cl2.Roster.setItem(self.jid.getStripped())
                    time.sleep(0.2)
                    self.cl.Dispatcher.Process()
                    self.cl2.Dispatcher.Process()
                    self.cl.Roster.Authorize(self.jid2.getStripped())
                    time.sleep(0.2)
                    self.cl.Dispatcher.Process()
                    self.cl2.Dispatcher.Process()
                    #self.cl2.Roster.Authorize(self.jid.getStripped())
                    self.assert_(self.cl.Roster.getSubscription(self.jid2.getStripped()) == 'both')
                else:
                    self.fail("Authentication failed")
            else:
                self.fail("Connections failed")

        test = TestThread(run)
        test.start()
        test.join(WAITLEN*2)
        if test.isAlive():
            self.fail("Test took too long to execute")
        if test.exc:
            self.fail(test.exc)

def deletePresenceDB():
    import os
    os.remove(TEST_PRESDB_NAME)
def initPresenceDB():
    con = DB(TEST_PRESDB_NAME)
    c = con.cursor()
    try:
        c.execute("CREATE TABLE jids (id INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,\
                                        jid TEXT NOT NULL,\
                                        password TEXT NOT NULL,\
                                        UNIQUE(jid))")
        c.execute("CREATE TABLE roster (userid INTEGER REFERENCES jids NOT NULL,\
                                        contactid INTEGER REFERENCES jids NOT NULL,\
                                        name TEXT,\
                                        subscription INTEGER DEFAULT 0,\
                                        PRIMARY KEY (userid, contactid)\
                                        )")
        c.execute("CREATE TABLE rostergroups (groupid INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,\
                                              userid INTEGER REFERENCES jids NOT NULL,\
                                              name TEXT NOT NULL,\
                                              UNIQUE(userid, name)\
                                              )")
        c.execute("CREATE TABLE rostergroupitems\
                    (groupid INTEGER REFERENCES rostergroup NOT NULL,\
                     contactid INTEGER REFERENCES jids NOT NULL,\
                     PRIMARY KEY (groupid, contactid))")
        c.execute("INSERT INTO jids (jid, password) VALUES ('bob@localhost', 'test')")
        c.execute("INSERT INTO jids (jid, password) VALUES ('alice@localhost', 'test')")
        c.execute("INSERT INTO roster (userid, contactid, subscription) VALUES (1, 2, 8)")
        c.execute("INSERT INTO roster (userid, contactid, subscription) VALUES (2, 1, 8)")
        con.commit()
    except sqlite.OperationalError, e:
        if e.message.find('already exists') >= 0: pass
        else: raise
    c.close()
    
def deleteNoRosterItemsDB():
    import os
    os.remove(TEST_NOROSTER_NAME)
def initNoRosterItemsDB():
    con = DB(TEST_NOROSTER_NAME)
    c = con.cursor()
    try:
        c.execute("CREATE TABLE jids (id INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,\
                                        jid TEXT NOT NULL,\
                                        password TEXT NOT NULL,\
                                        UNIQUE(jid))")
        c.execute("CREATE TABLE roster (userid INTEGER REFERENCES jids NOT NULL,\
                                        contactid INTEGER REFERENCES jids NOT NULL,\
                                        name TEXT,\
                                        subscription INTEGER DEFAULT 0,\
                                        PRIMARY KEY (userid, contactid)\
                                        )")
        c.execute("CREATE TABLE rostergroups (groupid INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,\
                                              userid INTEGER REFERENCES jids NOT NULL,\
                                              name TEXT NOT NULL,\
                                              UNIQUE(userid, name)\
                                              )")
        c.execute("CREATE TABLE rostergroupitems\
                    (groupid INTEGER REFERENCES rostergroup NOT NULL,\
                     contactid INTEGER REFERENCES jids NOT NULL,\
                     PRIMARY KEY (groupid, contactid))")
        c.execute("INSERT INTO jids (jid, password) VALUES ('bob@localhost', 'test')")
        c.execute("INSERT INTO jids (jid, password) VALUES ('alice@localhost', 'test')")
        con.commit()
    except sqlite.OperationalError, e:
        if e.message.find('already exists') >= 0: pass
        else: raise
    c.close()

if __name__ == '__main__':
    unittest.main()
