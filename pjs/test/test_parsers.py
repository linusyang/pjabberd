import unittest
import xml.parsers.expat
from pjs.parsers import IncrStreamParser

class TestParsers(unittest.TestCase):
    
    def setUp(self):
        unittest.TestCase.setUp(self)
        self.p = DumbParser()
        
    def tearDown(self):
        unittest.TestCase.tearDown(self)
        
        try:
            self.p.close() 
        except:
            pass
    
    def testSingleEmptyElement(self):
        self.p.feed('<stream></stream>')
        self.failUnless(self.p.startCalled, "Start element event not sent")
        self.failUnless(self.p.endCalled, "End element event not sent")
        self.p.close()
        
    def testSingleComplexElement(self):
        self.p.feed("<stream:stream \
           to='example.com' \
           xmlns='jabber:client' \
           xmlns:stream='http://etherx.jabber.org/streams' \
           version='1.0'></stream:stream>")
        self.failUnless(self.p.startCalled, "Start element event not sent")
        self.failUnless(self.p.endCalled, "End element event not sent")
        self.p.close()
    
    def testPartialElement(self):
        self.p.feed('<s')
        self.p.feed('t')
        self.p.feed('ream')
        self.p.feed('>')
        self.failUnless(self.p.startCalled, "Start element event not sent")
        
    def testText(self):
        self.p.feed('<something>asdfasdfasdf</something>')
        self.failUnless(self.p.textCalled, 'Text element event not sent')
        
    def testParseError(self):
        self.p.feed('<stream:stream')
        self.failUnlessRaises(xml.parsers.expat.ExpatError, self.p.close)
        
class DumbParser(IncrStreamParser):
    """We don't want to handle anything, just parse.
    Still, we record when the start/end/text events have occurred.
    """
    def __init__(self):
        IncrStreamParser.__init__(self)
        self.startCalled = False
        self.endCalled = False
        self.textCalled = False
    def handle_start(self, tag, attrs):
        self.startCalled = True
    def handle_end(self, tag):
        self.endCalled = True
    def handle_text(self, text):
        self.textCalled = True
        
if __name__ == '__main__':
    unittest.main()