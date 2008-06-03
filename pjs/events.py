import pjs.handlers.base
import pjs.conf.conf
import logging
import socket

from pjs.conf.phases import corePhases, c2sStanzaPhases, s2sStanzaPhases
from pjs.conf.handlers import handlers as h
from pjs.handlers.write import prepareDataForSending
from Queue import Queue, Empty

class Message:
    def __init__(self, tree, conn, handlers, errorHandlers, currentPhase=None):
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
        
        Puts the contents of self.outputBuffer onto Dispatcher's resultQ
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
            self._lastRetVal = handler.handle(self.tree, self, self._lastRetVal)
            self._gotException = False
        except Exception, e:
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
                    logging.warning("Unknown error handler type (%s) for %s",
                                    type(errorHandler), errorHandler)
            else:
                logging.warning("No error handler assigned for %s", handler)
                
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
                logging.warning("Unknown handler type (%s) for %s",
                                type(handler), handler)
                
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

# Variables that the dispatchers share

# Currently executing Messages for connection ids. Used to make sure
# that we don't process Messages out of order.
# connID => Message
_runningMessages = {}

# The queue of messages waiting to be processed. A message is queued if
# there is another message for the same connection currently being
# processed.
# [(connId, Message), ...]
_processingQ = []

# When messages finish running, they leave the result on this queue.
# out should be a string.
# [(connId, out), ...]
resultQ = Queue()

def _runMessages():
    """Runs all queued Messages that don't have an existing Message
    being processed for the same connection id.
    """
    for connId, msg in _processingQ:
        if connId not in _runningMessages:
            _runningMessages[connId] = msg
            msg.process()

activeServers = pjs.conf.conf.launcher.servers
            
def pickupResults():
    """Picks up any available results on the result queue and calls
    runMessages() to continue processing the queue.
    """
    while 1:
        try:
            connId, out = resultQ.get_nowait()
            for server in activeServers:
                if connId in server.conns:
                    conn = server.conns[connId][1]
                    # FIXME: this should be prevented
                    try:
                        conn.send(prepareDataForSending(out))
                    except socket.error, e:
                        logging.warning("[pickupResults] Socket error: %s", e)
                    break
            else:
                # message left on the queue for a connection that's no longer
                # there, so we log it and move on
                logging.warning("[events] Connection id %d has no corresponding" +\
                                " Connection object. Dropping result from queue.", connId)
            del _runningMessages[connId]
        except Empty:
            break
        
    _runMessages()
    
class _Dispatcher(object):
    """Dispatches events in a phase to Messages for handling. This class
    uses the Singleton pattern.
    """
    def __init__(self):
        # which phase list do we scan?
        self.phasesList = corePhases
    
    def dispatch(self, tree, conn, knownPhase=None):
        """Dispatch a Message object to process the stanza.
        
        tree -- stanza expressed as ElementTree's Element. This will be wrapped
                with the <stream> Element to allow for XPath querying
        conn -- connection that called this dispatcher
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
                
        msg = Message(tree, conn, handlers, errorHandlers, phaseName)
        
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