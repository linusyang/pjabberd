"""XML Stream parsers"""

import pjs.elementtree.ElementTree as et
import re
import logging

from xml.parsers import expat
from pjs.events import Dispatcher, C2SStanzaDispatcher, S2SStanzaDispatcher
from copy import deepcopy

# some quirks mode constants
QUIRK_MISSING_NEW_STREAM = 'missing-new-stream'

def borrow_parser(conn):
    """Borrow a parser from a pool of parsers"""
    # TODO: implement the pool. For now just return a new parser
    logging.debug("Creating a new parser for %s", conn.id)
    return IncrStreamParser(conn)

class IncrStreamParser:
    """Pass it unicode strings via feed() and it will buffer the input until it
    can parse a chunk. When it can, it dispatches the right event. Don't forget
    to call close() when done with the parser. If the stream isn't closed when
    close() is called, it will throw a xml.parsers.expat.ExpatError.
    """

    c2sStanzaRe = re.compile(r'{jabber:client}(iq|message|presence)\b', re.U | re.I)
    s2sStanzaRe = re.compile(r'{jabber:server}(iq|message|presence)\b', re.U | re.I)

    def __init__(self, conn=None):
        self.conn = conn
        self._parser = None

        self._exception = None # set this on quirky input

        self.resetParser()
        self.resetStream()

    def resetStream(self):
        """Reset the stream, tree, etc. Everything but the parser."""
        self.depth = 0
        self.tree = None
        self.stream = None # this is the main <stream> et.Element
        # name memo cache. from ElementTree
        self._names = {} # clear because this parser may be reused for another
                         # stream if it's picked up from a pool later
        # ns of the stream: jabber:client / jabber:server
        self.ns = None
        self._exception = None

    def resetParser(self):
        """Reset the parser and the tree."""
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
        self._exception = None

    def disable(self):
        """Turns off all handlers for this parser, so data will be parsed,
        but not processed in any way. This is useful for faking input into
        the parser, so that its namespace expectations are primed for real
        input. This is used for local S2S connections.
        """
        assert self._parser

        self._parser.StartElementHandler = None
        self._parser.EndElementHandler = None
        self._parser.CharacterDataHandler = None
        self._parser.StartNamespaceDeclHandler = None

    def enable(self):
        """Use after disable() to reenable the processing of the
        XML events.
        """
        assert self._parser

        self._parser.StartElementHandler = self.handle_start
        self._parser.EndElementHandler = self.handle_end
        self._parser.CharacterDataHandler = self.handle_text
        self._parser.StartNamespaceDeclHandler = self.handle_ns

    def feed(self, data):
        """Read a chunk of data to parse. The complete XML in the chunk will
        be parsed and the appropriate events dispatched. The incomplete XML
        will be buffered.
        """
#        if data != ' ':
#            logging.debug("[%s] For connection %s parser got: %s",
#                          self.__class__, self.conn.id, data)

        try:
            self._parser.Parse(data, 0)
        except Exception, e:
            logging.warning("[%s] Parser died with %s",
                            self.__class__, e)
            # TODO: complain about invalid XML and close connection

        if self._exception:
            # the parser found quirky input
            cause = self._exception.cause
            if cause:
                if cause == QUIRK_MISSING_NEW_STREAM:
                    # some non-compliant clients (ahem Kopete) don't reset
                    # the stream after auth, which we assume should happen
                    # implicitly as stated in the spec (3920 #6.2).
                    # we fake that we're in stream.
                    self._exception = None
                    self.resetParser()
                    self.disable()
                    newdata = "<?xml version='1.0' ?>" +\
                            "<stream:stream xmlns='jabber:client' " +\
                            "xmlns:stream='http://etherx.jabber.org/streams' " +\
                            "version='1.0'>"
                    self.feed(newdata)
                    self.depth = 1
                    self.stream = et.Element('{http://etherx.jabber.org/streams}stream',
                                            {'version' : '1.0'})
                    self.ns = 'jabber:client'
                    self.enable()

                    # pretend we got session, since we won't
                    self.conn.data['user']['in-session'] = True
            else:
                logging.debug("[%s] Parser got quirky input and doesn't " +\
                              "know how to proceed. Ignoring data: %s",
                              self.__class__, data)
                self._exception = None
                return

            self._exception = None
            # retry parsing
            self.feed(data)

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

        if self.depth == 1 and tag.find('stream') == -1:
            self._exception = QuirksModeException(QUIRK_MISSING_NEW_STREAM)
            return

        if self.depth == 1:
            # if starting a new stream, don't reset the old one, because
            # we don't want to deal with changed namespaces or attributes
            # for now.
            if self.stream is not None:
                # wrap here because the Dispatcher will do tree[0]
                wrapperEl = et.Element('wrapper')
                wrapperEl.append(self.stream)
                Dispatcher().dispatch(wrapperEl, self.conn, 'in-stream-reinit')
                return

            # handle <stream>, record it for XPath wrapping
            self.stream = et.Element(self._fixname(tag), attrs)

            # wrap here because the Dispatcher will do tree[0]
            wrapperEl = et.Element('wrapper')
            wrapperEl.append(self.stream)
            if 'id' in attrs:
                # s2s connection
                Dispatcher().dispatch(wrapperEl, self.conn, 'out-stream-init')
            else:
                Dispatcher().dispatch(wrapperEl, self.conn, 'in-stream-init')
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
        if self._exception:
            return
        self.depth -= 1

        assert(self.depth >= 0)

        if self.depth == 0: # stream closed
            wrapperEl = et.Element('wrapper')
            dummyEl = et.Element('tag')
            wrapperEl.append(dummyEl)
            Dispatcher().dispatch(wrapperEl, self.conn, 'stream-end')
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

        if self._exception:
            return

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

class QuirksModeException(Exception):
    """Indicates that the other side sent unexpected input but we
    can handle it anyway.
    """
    def __init__(self, cause=None):
        Exception.__init__(self)
        self.cause = cause