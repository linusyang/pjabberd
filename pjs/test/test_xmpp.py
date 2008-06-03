""" Core protocol testing """

import pjs.test.init # initialize the launcher
import pjs.conf.conf
import unittest
import xmpp
import threading
import time

# for the asyncore thread
shutdownAsyncore = False
def checkShutdown(): return shutdownAsyncore

# we need to run asyncore in a separate thread because it blocks
class AsyncoreThread(threading.Thread):
    def __init__(self, stopfunc):
        threading.Thread.__init__(self)
        self.stopfunc = stopfunc
    def run(self):
        import pjs.async.core
    
        while not self.stopfunc():
            pjs.async.core.loop(timeout=1, count=2)

class TestThread(threading.Thread):
    def __init__(self, func):
        threading.Thread.__init__(self)
        self.func = func
    def run(self):
        self.func()

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
        
        global shutdownAsyncore
        shutdownAsyncore = False
        
        pjs.conf.conf.launcher.run()
        
        self.jid = xmpp.protocol.JID('tro@localhost/test')
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
        test.join(1)
        if test.isAlive():
            self.fail("Test took too long to execute")
        
    # TODO: test for PLAIN auth as well
    
    def testSASLAuth(self):
        """SASL authentication"""
        def run():
            con = self.cl.connect(use_srv=False)
            if con:
                auth = self.cl.auth(self.jid.getNode(), self.password, self.jid.getResource(), sasl=1)
                
                self.assert_(auth, "Could not authenticate with SASL")
                
        test = TestThread(run)
        test.start()
        test.join(1)
        if test.isAlive():
            self.fail("Test took too long to execute")
            
    def testNonSASLAuth(self):
        """Non-SASL auth"""
        def run():
            con = self.cl.connect(use_srv=False)
            if con:
                auth = self.cl.auth(self.jid.getNode(), self.password, self.jid.getResource(), sasl=0)
                
                self.assert_(auth, "Could not authenticate with SASL")
                
        test = TestThread(run)
        test.start()
        test.join(1)
        if test.isAlive():
            self.fail("Test took too long to execute")

if __name__ == '__main__':
    unittest.main()
