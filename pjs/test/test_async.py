import pjs.test.init # init the launcher
import pjs.async.core as asyncore
from pjs.utils import FunctionCall
from pjs.connection import Connection

import unittest
import socket

class ServerHelper(asyncore.dispatcher):
    """Starts a dummy server that listens on port 44444"""
    def __init__(self):
        asyncore.dispatcher.__init__(self)
        
        self.create_socket(socket.AF_INET, socket.SOCK_STREAM)
        self.set_reuse_addr()
        self.bind(('', 44444))
        self.listen(5)
        
        self.conns = {}
        
    def handle_accept(self):
        sock, addr = self.accept()
        conn = Connection(sock, addr, self)
        # we don't know the JID until client logs in
        self.conns[conn.id] = (None, conn)
        
    def handle_close(self):
        self.close()
        
class TestWatchFunction(unittest.TestCase):
    """Testing of the function-watching feature of pjs.async.core"""
    
    def setUp(self):
        unittest.TestCase.setUp(self)
        self.server = ServerHelper() # restart the server
        self.passed = False
    
    def tearDown(self):
        unittest.TestCase.tearDown(self)
        self.server.handle_close() # close the listening connection
        
    def testSimple(self):
        """Simple callback and simple check function with no params"""
        def cb(e=None):
            self.passed = True and e is None
        def check():
            return True
        
        checkFunc = FunctionCall(check)
        self.server.watch_function(checkFunc, cb)
        
        asyncore.poll()
        
        self.assert_(self.passed)
        
    def testCheckParam(self):
        """Check function has one parameter"""
        def cb(e=None):
            self.passed = self.passed and e is None
        def check(param1):
            if param1:
                self.passed = True
            return True
        
        checkFunc = FunctionCall(check, {'param1' : 'non-empty string'})
        self.server.watch_function(checkFunc, cb)
        
        asyncore.poll()
        
        self.assert_(self.passed)
        
    def testCheckParams(self):
        """Check function has more than one parameters"""
        def cb(e=None):
            self.passed = self.passed and e is None
        def check(param1, param2):
            if param1 and param2:
                self.passed = True
            return True
        
        checkFunc = FunctionCall(check, {'param1' : 'non-empty string', 'param2' : 'asdfasdf'})
        self.server.watch_function(checkFunc, cb)
        
        asyncore.poll()
        
        self.assert_(self.passed)
        
    def testInitFunc(self):
        """Simple init function"""
        def cb(e=None):
            self.passed = self.passed and e is None
        def check(param1, param2):
            return True
        def init():
            self.passed = True
        
        checkFunc = FunctionCall(check, {'param1' : 'non-empty string', 'param2' : 'asdfasdf'})
        initFunc = FunctionCall(init)
        
        self.server.watch_function(checkFunc, cb, initFunc)
        
        asyncore.poll()
        
        self.assert_(self.passed)
        
    def testInitFuncWithParams(self):
        """Init function with two parameters"""
        def cb(e=None):
            self.passed = self.passed and e is None
        def check(param1, param2):
            return True
        def init(a, b):
            self.passed = a and b
            
        checkFunc = FunctionCall(check, {'param1' : 'non-empty string', 'param2' : 'asdfasdf'})
        initFunc = FunctionCall(init, {'a' : 'str', 'b' : 'str'})
        
        self.server.watch_function(checkFunc, cb, initFunc)
        
        asyncore.poll()
        
        self.assert_(self.passed)
        
if __name__ == '__main__':
    unittest.main()