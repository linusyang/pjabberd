import unittest
import copy
import xml.parsers.expat
import pjs.conf.handlers as handlers
import pjs.test.init # it initializes the launcher
import pjs.conf.conf
from pjs.parsers import IncrStreamParser
from pjs.handlers.base import Handler
from pjs.elementtree.ElementTree import Element

streamStart = """<stream:stream xmlns='jabber:client' \
            xmlns:stream='http://etherx.jabber.org/streams' \
            id='c2s_345' from='localhost' version='1.0'>"""
streamEnd = '</stream:stream>'

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

class TestDumbParser(unittest.TestCase):
    """Only test the partial XML parsing, not its handling"""
    
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
        
class TestParser(unittest.TestCase):
    """Test tree-building of the incremental parser"""

    def setUp(self):
        unittest.TestCase.setUp(self)
        self.p = IncrStreamParser()
        
        pjs.conf.conf.launcher.run()
        
        self.oldhandlers = copy.deepcopy(handlers.handlers)
        
    def tearDown(self):
        unittest.TestCase.tearDown(self)
        
        try:
            self.p.close()
        except xml.parsers.expat.ExpatError:
            pass
        
        handlers.handlers = self.oldhandlers
        
        pjs.conf.conf.launcher.stop()
        
    def testOpenStream(self):
        """Depth should increase at stream element"""
        self.p.feed(streamStart)
        self.assert_(self.p.depth == 1)
        self.assert_(self.p.tree is None)
        
    def testOpenCloseStream(self):
        """Testing depth and initialization of tree"""
        self.p.feed(streamStart)
        self.p.feed(streamEnd)
        self.assert_(self.p.depth == 0)
        self.assert_(self.p.tree is None)
        
    def testSimpleStanza(self):
        """Single-level empty stanza"""
        self.p.feed(streamStart)
        
        self.p.feed('<stream:features>')
        self.assert_(self.p.depth == 2)
        self.assert_(self.p.tree is not None)
        
        self.p.feed('</stream:features>')
        
        # copying for our own use
        self.assert_(self.p.tree.tag == '{http://etherx.jabber.org/streams}features')
        self.assert_(self.p.depth == 1)
        
    def testDeepStanza(self):
        """Multi-level stanza"""
        self.p.feed(streamStart)
        
        self.p.feed("""<iq type='result' id='bind_2'>\
                      <bind xmlns='urn:ietf:params:xml:ns:xmpp-bind'>\
                        <jid>somenode@example.com/someresource""")
        self.assert_(self.p.depth == 4)
        
        self.p.feed("</jid></bind></iq>")
        self.assert_(self.p.depth == 1)
        self.assert_(self.p.tree.tag == '{jabber:client}iq')
        self.assert_(self.p.tree[0].tag == '{urn:ietf:params:xml:ns:xmpp-bind}bind')
        self.assert_(self.p.tree[0][0].text == u'somenode@example.com/someresource')

    def testNamespacedXPath(self):
        """Should be able to refer to elements using namespaces in XPath"""
        self.p.feed(streamStart)
        self.p.feed('<stream:features></stream:features>')
        
        stream = Element('dummy')
        stream.insert(0, self.p.tree)
        
        self.assert_(stream.find('{http://etherx.jabber.org/streams}features') is not None)
        
if __name__ == '__main__':
    unittest.main()