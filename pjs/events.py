import pjs.handlers.base
from pjs.conf.phases import phases
from pjs.conf.handlers import handlers as h

class Message:
    def __init__(self, tree, conn, handlers, errorHandlers, currentPhase=None):
        self.tree = tree
        self.conn = conn
        self.handlers = handlers or []
        self.errorHandlers = errorHandlers or []
        self.currentPhase = currentPhase
        
        # signals to process() to stop running handlers
        self.stopChain = False
        
        # return value from the last handler. Could be an Exception object.
        self.lastRetVal = None
        
        # indicates whether the last handler threw and exception
        self.gotException = False
        
        self.handlerResumeFunc = None
        
    def process(self):
        """Runs the handlers"""
        
        # if we don't have error handlers, that's ok, but if we don't have
        # handlers, then we quit. Handlers are popped from the handlers list
        # instead of iterated on because we expect handlers to be able to add
        # other handlers onto the list.
        while 1:
            if self.stopChain:
                break
            
            try:
                handler = self.handlers.pop(0)
            except IndexError:
                break
            
            try:
                errorHandler = self.errorHandlers.pop(0)
            except IndexError:
                errorHandler = None
                
            shouldReturn = self._execLink(handler, errorHandler)
            
            if shouldReturn:
                return
                
    def resume(self):
        """Resumes the execution of handlers. This is the callback for when
        the thread is done executing. It gets called by the Connection.
        """
        if callable(self.handlerResumeFunc()):
            self.handlerResumeFunc()
        self.process()
            
    def _execLink(self, handler, errorHandler):
        """Execute a single link in the chain of handlers"""
        shouldReturn = False
        
        if self.gotException and errorHandler is not None:
            nextHandler = errorHandler
        else:
            nextHandler = handler
        
        if isinstance(nextHandler, pjs.handlers.base.Handler):
            # run in-process
            try:
                self.lastRetVal = nextHandler.handle(self.tree, self, self.lastRetVal)
                self.gotException = False
            except Exception, e:
                self.gotException = True
                self.lastRetVal = e
                
            if self.gotException and errorHandler is not None:
                # try the errorHandler in the same link now
                try:
                    self.lastRetVal = errorHandler.handle(self.tree, self, self.lastRetVal)
                    self.getException = False
                except Exception, e:
                    self.gotException = True
                    self.lastRetVal = e
                
        elif isinstance(nextHandler, pjs.handlers.base.ThreadedHandler):
            # run out of process with a callback to resume
            checkFunc, initFunc = nextHandler.handle(self.tree, self, self.lastRetVal)
            self.handlerResumeFunc = nextHandler.resume
            self.conn.watch_function(checkFunc, self.resume, initFunc)
            shouldReturn = True
        else:
            # log it
            pass
        
        return shouldReturn
    
class _Dispatcher(object):
    """Dispatches events in a phase to Messages for handling. This class
    uses the Singleton pattern.
    """
    def __init__(self):
        pass
    
    def dispatch(self, tree, conn, knownPhase=None):
        """Dispatch a Message object to process the stanza.
        
        tree -- stanza expressed as ElementTree's Element. This will be wrapped
                with the <stream> Element to allow for XPath querying
        conn -- connection that called this dispatcher
        knownPhase -- the phase that this packet is in, if known.
        """
        phaseName = 'default'
        phase = phases[phaseName]
        
        if knownPhase and phases.has_key(knownPhase):
            phase = phases[knownPhase]
            phaseName = knownPhase
        else:
            # loop through all phases to find the one who's XPath expr matches
            # the stanza
            # FIXME: this is likely to be a bottleneck
            for p in phases:
                if p.has_key('xpath') and tree.find(p['xpath']) is not None:
                    phase = phases[p]
                    phaseName = p

        # handlers get instantiated and loaded up into lists
        # TODO: watch for errors during instantiation
        # TODO: instantiate once, cache the handler and reuse
        if phase.has_key('handlers'):
            handlers = [item['handler']() for item in phase['handlers']]
            if phase.has_key('errorHandlers'):
                errorHandlers = [item['handler']() for item in phase['errorHandlers']]
            else:
                errorHandlers = []
        else:
            return
                
        msg = Message(tree, conn, handlers, errorHandlers, phaseName)
        msg.process()

_dispatcher = _Dispatcher()
def Dispatcher(): return _dispatcher