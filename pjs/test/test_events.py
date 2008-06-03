import pjs.test.init # init the launcher
import pjs.handlers.base
import pjs.events
import pjs.connection
import pjs.threadpool
from pjs.utils import FunctionCall
from pjs.test.test_async import ServerHelper

import unittest
import socket
import time

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

class TestMessagesInProcess(unittest.TestCase):
    """Simple in-process message tests"""
    class FakeConn:
        def __init__(self):
            self.id = 5

    def setUp(self):
        unittest.TestCase.setUp(self)
        self.conn = TestMessagesInProcess.FakeConn()

    def tearDown(self):
        unittest.TestCase.tearDown(self)
        pjs.queues.resultQ.empty()

    def testSimpleInProcess(self):
        h = SimpleHandler()
        msg = pjs.events.Message(None, self.conn, [h], None, None)
        msg.process()

        self.assert_(h.prop)

    def testSimpleWithExceptionInProcess(self):
        h = SimpleHandlerWithError()
        msg = pjs.events.Message(None, self.conn, [h], None, None)
        msg.process()

        self.assert_(isinstance(msg._lastRetVal, Exception))

    def testSimpleWithBothInProcess(self):
        h1 = SimpleHandlerWithError()
        h2 = SimpleHandler()
        msg = pjs.events.Message(None, self.conn, [h1], [h2], None)
        msg.process()

        self.assert_(h2.prop)

    def testChainedInProcess(self):
        h1 = SimpleHandler()
        msg = pjs.events.Message(None, self.conn, [h1, h1], None, None)
        msg.process()

        self.assert_(not h1.prop)

    def testChainedWithExceptionInProcess(self):
        h1 = SimpleHandler()
        h2 = SimpleHandlerWithError()
        msg = pjs.events.Message(None, self.conn, [h1, h2], None, None)
        msg.process()

        self.assert_(isinstance(msg._lastRetVal, Exception))

    def testChainedWithReturnValuePassingInProcess(self):
        h1 = ReturnTrueHandler()
        h2 = ReturnValueDependentHandler()
        msg = pjs.events.Message(None, self.conn, [h1, h2], None, None)
        msg.process()

        self.assert_(msg._lastRetVal == 'success')

        h1 = SimpleHandler()
        msg = pjs.events.Message(None, self.conn, [h1, h2], None, None)
        msg.process()

        self.assert_(not msg._lastRetVal)

    def testHandledExceptionInProcess(self):
        h1 = SimpleHandlerWithError()
        h2 = ExceptionTrueHandler()

        msg = pjs.events.Message(None, self.conn, [h1], [h2], None)
        msg.process()

        self.assert_(msg._lastRetVal == 'success')

    def testOneMoreHandlerThanErrorInProcess(self):
        h1 = SimpleHandlerWithError()
        h2 = ExceptionTrueHandler()

        msg = pjs.events.Message(None, self.conn, [h1, h2], [h2], None)
        msg.process()

        self.assert_(not msg._lastRetVal)





class SimpleThreadedHandler(pjs.handlers.base.ThreadedHandler):
    def __init__(self, threadpool):
        self.passed = False
        self.threadpool = threadpool
    def handle(self, tree, msg, lastRetVal=None):
        def sleep(arg):
            """This is the actual function executing in the thread"""
            # time.sleep(10) # this also worked but slows down tests
            return 'success'
        def cb(workReq, retVal):
            """Asyncore calls this back when checkFunc returns true"""
            self.passed = retVal
        req = pjs.threadpool.makeRequests(sleep, [([0], None)], cb)

        def checkFunc():
            """Asyncore will run this regularly and call cb when true"""
            return self.passed

        def initFunc():
            """Asyncore will execute this function before checkFunc"""
            [self.threadpool.putRequest(r) for r in req]

        return FunctionCall(checkFunc), FunctionCall(initFunc)

    def resume(self):
        pass

class TestMessageInThread(unittest.TestCase):
    """Simple threaded-handler test"""
    def setUp(self):
        unittest.TestCase.setUp(self)
        self.server = ServerHelper()
        self.sock = socket.socket()
        self.sock.connect(('', 44444))
        self.conn = pjs.connection.Connection(self.sock, None, self.server)
        self.server.conns[self.conn.id] = ()
        self.threadpool = pjs.threadpool.ThreadPool(1)

    def tearDown(self):
        unittest.TestCase.tearDown(self)
        self.conn.handle_close()
        self.server.handle_close()
        self.threadpool.dismissWorkers(1)
        del self.threadpool

    def testSimpleHandler(self):
        h = SimpleThreadedHandler(self.threadpool)

        msg = pjs.events.Message(None, self.conn, [h], None, None)
        msg.process()

        self.threadpool.wait()
        time.sleep(0.5)

        self.assert_(h.passed)

if __name__ == '__main__':
    unittest.main()