import pjs.async.core as asyncore
from pjs.utils import FunctionCall

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
        
    def handle_accept(self):
        conn, addr = self.accept()
        
    def handle_close(self):
        self.close()
        
class TestWatchFunction(unittest.TestCase):
    """Testing of the function-watching feature of pjs.async.asyncore"""
    
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