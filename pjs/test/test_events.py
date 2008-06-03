import pjs.handlers.base
import pjs.events

import unittest

class SimpleHandler(pjs.handlers.base.Handler):
    def __init__(self):
        self.prop = False
    def handle(self, tree, msg, lastRetVal=None):
        self.prop ^= True
        
class SimpleHandlerWithError(pjs.handlers.base.Handler):
    def __init__(self):
        pass
    def handle(self, tree, msg, lastRetVal=None):
        raise Exception, 'raising exception as planned'
    
class ReturnTrueHandler(pjs.handlers.base.Handler):
    def __init__(self):
        pass
    def handle(self, tree, msg, lastRetVal=None):
        return True

class ReturnValueDependentHandler(pjs.handlers.base.Handler):
    def __init__(self):
        pass
    def handle(self, tree, msg, lastRetVal=None):
        if lastRetVal:
            return 'success'
        else:
            return False
        
class ExceptionTrueHandler(pjs.handlers.base.Handler):
    def __init__(self):
        pass
    def handle(self, tree, msg, lastRetVal=None):
        if isinstance(lastRetVal, Exception):
            return 'success'
        else:
            return False

class TestMessages(unittest.TestCase):
    
    def setUp(self):
        unittest.TestCase.setUp(self)
    
    def tearDown(self):
        unittest.TestCase.tearDown(self)
        
    def testSimpleInProcess(self):
        h = SimpleHandler()
        msg = pjs.events.Message(None, None, [h], None, None)
        msg.process()
        
        self.assert_(h.prop)
        
    def testSimpleWithExceptionInProcess(self):
        h = SimpleHandlerWithError()
        msg = pjs.events.Message(None, None, [h], None, None)
        msg.process()
        
        self.assert_(isinstance(msg.lastRetVal, Exception))
        
    def testSimpleWithBothInProcess(self):
        h1 = SimpleHandlerWithError()
        h2 = SimpleHandler()
        msg = pjs.events.Message(None, None, [h1], [h2], None)
        msg.process()
        
        self.assert_(h2.prop)
        
    def testChainedInProcess(self):
        h1 = SimpleHandler()
        msg = pjs.events.Message(None, None, [h1, h1], None, None)
        msg.process()
        
        self.assert_(not h1.prop)
        
    def testChainedWithExceptionInProcess(self):
        h1 = SimpleHandler()
        h2 = SimpleHandlerWithError()
        msg = pjs.events.Message(None, None, [h1, h2], None, None)
        msg.process()
        
        self.assert_(isinstance(msg.lastRetVal, Exception))
        
    def testChainedWithReturnValuePassingInProcess(self):
        h1 = ReturnTrueHandler()
        h2 = ReturnValueDependentHandler()
        msg = pjs.events.Message(None, None, [h1, h2], None, None)
        msg.process()
        
        self.assert_(msg.lastRetVal == 'success')
        
        h1 = SimpleHandler()
        msg = pjs.events.Message(None, None, [h1, h2], None, None)
        msg.process()
        
        self.assert_(not msg.lastRetVal)
        
    def testHandledExceptionInProcess(self):
        h1 = SimpleHandlerWithError()
        h2 = ExceptionTrueHandler()
        
        msg = pjs.events.Message(None, None, [h1], [h2], None)
        msg.process()
        
        self.assert_(msg.lastRetVal == 'success')
        
    def testOneMoreHandlerThanErrorInProcess(self):
        h1 = SimpleHandlerWithError()
        h2 = ExceptionTrueHandler()
        
        msg = pjs.events.Message(None, None, [h1, h2], [h2], None)
        msg.process()
        
        self.assert_(not msg.lastRetVal)
        
if __name__ == '__main__':
    unittest.main()