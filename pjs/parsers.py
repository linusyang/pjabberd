""" XML Stream parsers """

from xml.parsers import expat
from pjs.events import Dispatcher, C2SStanzaDispatcher, S2SStanzaDispatcher
from copy import deepcopy
import pjs.elementtree.ElementTree as et
import re

def borrow_parser(conn):
    """Borrow a parser from a pool of parsers"""
    # TODO: implement the pool. For now just return a new parser
    return IncrStreamParser(conn)

class IncrStreamParser:
    """Pass it unicode strings via feed() and it will buffer the input until it
    can parse a chunk. When it can, it dispatches the right event. Don't forget
    to call close() when done with the parser. If the stream isn't closed when
    close() is called, it will throw a xml.parsers.expat.ExpatError.
    """
    
    c2sStanzaRe = re.compile(r'{jabber:client}\b(iq|message|presence)\b', re.U | re.I)
    s2sStanzaRe = re.compile(r'{jabber:server}\b(iq|message|presence)\b', re.U | re.I)

    def __init__(self, conn=None):
        self.conn = conn
        self._parser = None
        
        self.resetParser()
        self.resetStream()
    
    def resetStream(self):
        """Reset the stream"""
        self.depth = 0
        self.tree = None
        self.stream = None # this is the main <stream> et.Element
        # name memo cache. from ElementTree
        self._names = {} # clear because this parser may be reused for another
                         # stream if it's picked up from a pool later
        # ns of the stream: jabber:client / jabber:server
        self.ns = None
                         
    def resetParser(self):
        """Reset the parser"""
        # '}' is a ns-separator used in ET 1.3alpha. We want to duplicate its
        # behaviour here because its TreeBuilder doesn't prefix node names
        # with their namespace. Asking expat to do so will remove the xmlns
        # attrs from elements it encounters.
        if self._parser:
            del self._parser # get rid of circular references
        self._parser = expat.ParserCreate(None, '}')
        self._parser.StartElementHandler = self.handle_start
        self._parser.EndElementHandler = self.handle_end
        self._parser.CharacterDataHandler = self.handle_text
        self._parser.StartNamespaceDeclHandler = self.handle_ns
        self._parser.buffer_text = 1 # single handle_text call per text node
        self._parser.returns_unicode = 1 # handler funcs get unicode from expat
        
        # need to reset parts of the stream as well to ensure correct parsing
        self.depth = 0
        self.tree = None

    def feed(self, data):
        """Read a chunk of data to parse. The complete XML in the chunk will
        be parsed and the appropriate events dispatched. The incomplete XML
        will be buffered.
        """
        self._parser.Parse(data, 0)

    def close(self):
        """CLose the stream of XML data"""
        self._parser.Parse("", 1) # end of data
        del self._parser # get rid of circular references
        
        self.resetStream()

    def handle_start(self, tag, attrs):
        """Handles the opening-tag event. It is fired whenever the closing
        bracket of an opening XML element is encountered (ie. '>' in "<stream>").
        """
        # some logic to bootstrap a handling phase
        # include logic for starting streams
        # build an ElementTree for all stanzas
        
        self.depth += 1
        
        assert(self.depth >= 1)
        
        if self.depth == 1:
            # if starting a new stream, don't reset the old one, because
            # we don't want to deal with changed namespaces or attributes
            # for now.
            if self.stream is not None:
                Dispatcher().dispatch(self.stream, self.conn, 'stream-reinit')
                return
            
            # handle <stream>, record it for XPath wrapping
            self.stream = et.Element(self._fixname(tag), attrs)
            Dispatcher().dispatch(self.stream, self.conn, 'stream-init')
        elif self.depth == 2:
            # handle stanzas, build tree
            self.tree = et.TreeBuilder()
            self.tree.start(self._fixname(tag), attrs)
        else:
            # depth > 2. continue to build tree
            assert(self.tree)
            self.tree.start(self._fixname(tag), attrs)

    def handle_end(self, tag):
        """Handles the closing-tag event. It is fired whenever the closing
        bracket of a closing XML element is encountered (ie. '>' in "</stream>").
        """
        self.depth -= 1
        
        assert(self.depth >= 0)
        
        if self.depth == 0:
            Dispatcher().dispatch(self.tree, self.conn, 'stream-end')
            self.resetStream()
            self.resetParser()
        elif self.depth == 1:
            # handle </stanza>
            assert(self.tree)
            self.tree.end(self._fixname(tag))
            # TODO: handle errors
            self.tree = self.tree.close()
            
            # pass the el to the dispatcher for processing having wrapped it
            # in the <stream> element first
            tree = deepcopy(self.stream)
            tree.append(self.tree)
            if IncrStreamParser.c2sStanzaRe.search(self.tree.tag):
                C2SStanzaDispatcher().dispatch(tree, self.conn)
            elif IncrStreamParser.s2sStanzaRe.search(self.tree.tag):
                S2SStanzaDispatcher().dispatch(tree, self.conn)
            else:
                Dispatcher().dispatch(tree, self.conn)
        else:
            # depth > 1. continue to build tree
            assert(self.tree)
            self.tree.end(self._fixname(tag))

    def handle_text(self, text):
        """Handles the text node event. Whitespace is ignored between stream
        and stanza elements, but not inside the stanzas.
        """
        # TODO: test on very large text node. Will expat's buffer overflow?
        
        if self.depth <= 1 and not text.strip():
            return
        
        if self.depth <= 1:
            # TODO: there can't be any text between stanzas/streams, so maybe close the stream?
            pass
        else:
            self.tree.data(text)
            
    def handle_ns(self, prefix, uri):
        if not self.ns:
            if uri == 'jabber:client':
                self.ns = 'jabber:client'
            elif uri == 'jabber:server':
                self.ns = 'jabber:server'
            
    def _fixname(self, key):
        """Formats the node name according to ElementTree's convention of
        {ns}tag.
        """
        # expand qname. from ElementTree.py
        try:
            name = self._names[key]
        except KeyError:
            name = key
            if "}" in name:
                name = "{" + name
            self._names[key] = name
        return name
