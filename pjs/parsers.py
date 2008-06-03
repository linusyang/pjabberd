""" XML Stream parsers """

from xml.parsers import expat

class IncrStreamParser:
    """Pass it unicode strings via feed() and it will buffer the input until it
    can parse a chunk. When it can, it dispatches the right event. Don't forget
    to call close() when done with the parser. If the stream isn't closed when
    close() is called, it will throw a xml.parsers.expat.ExpatError.
    """

    def __init__(self, conn=None):
        self.conn = conn
        self._parser = expat.ParserCreate()
        self._parser.StartElementHandler = self.handle_start
        self._parser.EndElementHandler = self.handle_end
        self._parser.CharacterDataHandler = self.handle_text

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

    def handle_start(self, tag, attrs):
        # some logic to bootstrap a handling phase
        # include logic for starting streams
        # build an ElementTree for all stanzas
        pass

    def handle_end(self, tag):
        pass

    def handle_text(self, text):
        pass
