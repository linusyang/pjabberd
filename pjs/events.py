"""Chained handlers and Dispatchers"""

import pjs.handlers.base
import pjs.conf.conf
import logging

from pjs.conf.phases import corePhases, c2sStanzaPhases, s2sStanzaPhases
from pjs.conf.handlers import handlers as h
from pjs.utils import compact_traceback

from pjs.queues import _runningMessages, _processingQ, resultQ

class Message:
    """Defines message processing. This represents a "processing job" and
    not an xmpp message. See the design doc for information on chained handlers
    and the general execution model.
    """
    def __init__(self, tree, conn, handlers, errorHandlers, currentPhase=None):
        """Creates but doesn't run a new processing job.

        tree -- an Element object containing the message.
        conn -- Connection object.
        handlers -- list of initialized handler objects.
        errorHandlers -- list of initialized error handler objects.
        currentPhase -- the name of the currently executing phase
        """
        self.tree = tree
        self.conn = conn
        self.handlers = handlers or []
        self.errorHandlers = errorHandlers or []
        self.currentPhase = currentPhase

        # Signals to process() to stop running handlers. Handlers can signal
        # this directly.
        self.stopChain = False

        # Currently executing pair of (handler, errorHandler)
        # This is saved in order to properly handle exceptions thrown in
        # handlers.
        self._runningHandlers = (None, None)
        # Indicates whether we're executing the last handler in a pair. This is
        # necessary, because we need to decide when to clear
        # self.runningHandlers to proceed to the next pair.
        # Setting this to True is basically skipping the remaining handler in
        # pair and proceeding to the next set.
        self.lastInPair = False

        # Return value from the last handler. Could be an Exception object.
        self._lastRetVal = None

        # Indicates whether the last handler threw and exception
        self._gotException = False

        # Called by this object to notify the waiting handler that it can
        # continue.
        self._handlerResumeFunc = None

        # For handlers to append to. the write handler will process this.
        # Use addTextOutput() instead of appending to this directly.
        self.outputBuffer = u''

    def addTextOutput(self, data):
        """Handlers can use this to buffer unicode text for output.
        This will be sent by the write handler.
        """
        self.outputBuffer += unicode(data)

    def process(self):
        """Runs the handlers.

        Puts the contents of self.outputBuffer onto Dispatcher's resultQ.
        """

        # If we don't have error handlers, that's ok, but if we don't have
        # handlers, then we quit. Handlers are popped from the handlers list
        # instead of iterated on because we expect handlers to be able to add
        # other handlers onto the list.
        while 1:
            if self.stopChain:
                break

            if self._runningHandlers != (None, None):
                handler, errorHandler = self._runningHandlers
            else:
                try:
                    handler = self.handlers.pop(0)
                except IndexError:
                    break

                try:
                    errorHandler = self.errorHandlers.pop(0)
                except IndexError:
                    errorHandler = None

                self._runningHandlers = (handler, errorHandler)
                self.lastInPair = False

            shouldReturn = self._execLink()

            if shouldReturn:
                return

        # this signals to the dispatcher that the next message for this
        # connection can now be processed
        resultQ.put((self.conn.id, self.outputBuffer or None))

    def resume(self):
        """Resumes the execution of handlers. This is the callback for when
        the thread is done executing. It gets called by the Connection.
        """
        if callable(self._handlerResumeFunc):
            self._lastRetVal = self._handlerResumeFunc()
        if isinstance(self._lastRetVal, Exception):
            self._gotException = True
        else:
            self._gotException = False
            self.lastInPair = True
        self._updateRunningHandlers()
        self.process()

    def _updateRunningHandlers(self):
        """Resets running handlers to None if executing the last handler"""
        if self.lastInPair:
            self._runningHandlers = (None, None)

    def _execHandler(self, handler):
        """Run a handler in-process"""
        try:
            ret = handler.handle(self.tree, self, self._lastRetVal)

            # keep the lastRetVal if the handler didn't return anything
            if ret is not None:
                self._lastRetVal = ret
            self._gotException = False
        except Exception, e:
            nil, t, v, tbinfo = compact_traceback()
            logging.debug("Exception in in-process handler: %s: %s -- %s", t,v,tbinfo)
            self._gotException = True
            self._lastRetVal = e

    def _execThreadedHandler(self, handler):
        """Run a handler out of process with a callback to resume"""
        checkFunc, initFunc = handler.handle(self.tree, self, self._lastRetVal)
        self._handlerResumeFunc = handler.resume
        self.conn.watch_function(checkFunc, self.resume, initFunc)

    def _execLink(self):
        """Execute a single link in the chain of handlers"""

        handler, errorHandler = self._runningHandlers

        if self._gotException:
            self.lastInPair = True
            if errorHandler is not None:
                # executing the error handler
                if isinstance(errorHandler, pjs.handlers.base.Handler):
                    self._execHandler(errorHandler)
                elif isinstance(errorHandler, pjs.handlers.base.ThreadedHandler):
                    self._execThreadedHandler(errorHandler)
                    return True
                else:
                    logging.warning("[%s] Unknown error handler type (%s) for %s",
                                    self.__class__, type(errorHandler),
                                    errorHandler)
            else:
                logging.warning("[%s] No error handler assigned for %s. " +\
                                "Last exception: %s",
                                self.__class__, handler, self._lastRetVal)

            self._updateRunningHandlers()
        else:
            # executing the normal handler
            self.lastInPair = False
            if isinstance(handler, pjs.handlers.base.Handler):
                self._execHandler(handler)
                if not self._gotException: # if no exception, we're done with this pair
                    self.lastInPair = True
                    self._updateRunningHandlers()
            elif isinstance(handler, pjs.handlers.base.ThreadedHandler):
                self._execThreadedHandler(handler)
                return True
            else:
                logging.warning("[%s] Unknown handler type (%s) for %s",
                                self.__class__, type(handler), handler)

        return False

    def setNextHandler(self, handlerName, errorHandlerName=None):
        """Schedules 'handlerName' as the next handler to execute. Optionally,
        also schedules 'errorHandlerName' as the next error handler.
        """
        handler = Dispatcher().getHandlerFunc(handlerName)
        if handler:
            self.handlers.insert(0, handler())
            if errorHandlerName:
                eHandler = Dispatcher().getHandlerFunc(errorHandlerName)
                if eHandler:
                    self.errorHandlers.insert(0, eHandler())

    def setLastHandler(self, handlerName, errorHandlerName=None):
        """Schedules 'handlerName' as the last handler to execute. Optionally,
        also schedules 'errorHandlerName' as the last error handler.
        """
        handler = Dispatcher().getHandlerFunc(handlerName)
        if handler:
            self.handlers.append(handler())
            if errorHandlerName:
                eHandler = Dispatcher().getHandlerFunc(errorHandlerName)
                if eHandler:
                    self.errorHandlers.append(eHandler())

class _Dispatcher(object):
    """Dispatches events in a phase to Messages for handling. This class
    uses the Singleton pattern.
    """
    def __init__(self):
        # which phase list do we scan?
        self.phasesList = corePhases

    def dispatch(self, tree, conn, knownPhase=None):
        """Dispatch a Message object to process the stanza.

        tree -- stanza expressed as ElementTree's Element. Tree should be a
                wrapper containing the real tree. This is so that XPath matches
                could be done on the contents of the wrapper.
        conn -- connection that called this dispatcher.
        knownPhase -- the phase that this packet is in, if known.
        """
        phaseName = 'default'
        phase = self.phasesList[phaseName]

        if knownPhase and knownPhase in self.phasesList:
            phase = self.phasesList[knownPhase]
            phaseName = knownPhase
        else:
            # loop through all phases to find the one who's XPath expr matches
            # the stanza
            # FIXME: this is likely to be a bottleneck
            for p in self.phasesList:
                if 'xpath' in self.phasesList[p] and tree.find(self.phasesList[p]['xpath']) is not None:
                    phase = self.phasesList[p]
                    phaseName = p
                    break

        # handlers get instantiated and loaded up into lists
        # TODO: watch for errors during instantiation
        # TODO: instantiate once, cache the handler and reuse
        if 'handlers' in phase:
            handlers = [item['handler']() for item in phase['handlers']]
            if 'errorHandlers' in phase:
                errorHandlers = [item['handler']() for item in phase['errorHandlers']]
            else:
                errorHandlers = []
        else:
            return

        if not conn:
            logging.warning("[%s] Not dispatching a message without a connection",
                                self.__class__,)
            return

        # we pass in tree[0] because tree is a wrapper element for XPath matches
        msg = Message(tree[0], conn, handlers, errorHandlers, phaseName)

        if conn.id in _runningMessages:
            # already have a message being processed for this connection
            # so queue this one
            _processingQ.append((conn.id, msg))
        else:
            # record it and run it
            _runningMessages[conn.id] = msg
            msg.process()

    def getHandlerFunc(self, handlerName):
        """Gets a reference to the handler function"""
        if handlerName in h:
            return h[handlerName]['handler']
        else: return None

_dispatcher = _Dispatcher()
def Dispatcher(): return _dispatcher

class _C2SStanzaDispatcher(_Dispatcher):
    """C2S Stanza-specific dispatcher"""

    def __init__(self):
        self.phasesList = c2sStanzaPhases

_c2sStanzaDispatcher = _C2SStanzaDispatcher()
def C2SStanzaDispatcher(): return _c2sStanzaDispatcher

class _S2SStanzaDispatcher(_Dispatcher):
    """S2S Stanza-specific dispatcher"""

    def __init__(self):
        self.phasesList = s2sStanzaPhases

_s2sStanzaDispatcher = _S2SStanzaDispatcher()
def S2SStanzaDispatcher(): return _s2sStanzaDispatcher