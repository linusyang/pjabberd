""" XML Stream parsers """

from xml.parsers import expat
import pjs.elementtree.ElementTree as et

class IncrStreamParser:
    """Pass it unicode strings via feed() and it will buffer the input until it
    can parse a chunk. When it can, it dispatches the right event. Don't forget
    to call close() when done with the parser. If the stream isn't closed when
    close() is called, it will throw a xml.parsers.expat.ExpatError.
    """

    def __init__(self, conn=None):
        self.conn = conn
        # '}' is a ns-separator used in ET 1.3alpha. We want to duplicate its
        # behaviour here because its TreeBuilder doesn't prefix node names
        # with their namespace. Asking expat to do so will remove the xmlns
        # attrs from elements it encounters.
        self._parser = expat.ParserCreate(None, '}')
        self._parser.StartElementHandler = self.handle_start
        self._parser.EndElementHandler = self.handle_end
        self._parser.CharacterDataHandler = self.handle_text
        self._parser.buffer_text = 1 # single handle_text call per text node
        
        self._names = {} # name memo cache. from ElementTree
        
        # this is the main <stream> et.Element
        self.stream = None
        
        self.reset()
    
    def reset(self):
        """Reset the stream"""
        self.depth = 0
        self.tree = None
        self.stream = None

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
        
        self.reset()

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
            # handle <stream>, record it for XPath wrapping
            
            # if starting a new stream, reset the old one
            if self.stream: self.reset()
            self.stream = et.Element(self._fixname(tag), attrs)
            pass
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
            # handle </stream>. don't reset because we may need the data
            pass
        elif self.depth == 1:
            # handle </stanza>
            assert(self.tree)
            self.tree.end(self._fixname(tag))
            # TODO: handle errors
            self.tree = self.tree.close()
            # TODO: pass the el to the dispatcher for processing
        else:
            # depth > 1. continue to build tree
            assert(self.tree)
            self.tree.end(self._fixname(tag))

    def handle_text(self, text):
        """Handles the text node event."""
        # TODO: test on very large text node. Will expat's buffer overflow?
        
        assert(self.tree)
        
        if self.depth <= 1:
            # TODO: there can't be any text between stanzas/streams, so maybe close the stream?
            pass
        else:
            self.tree.data(text)
            
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
