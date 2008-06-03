import pjs.handlers.base

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
                
        elif isinstance(nextHandler, pjs.handlers.base.ThreadedHandler):
            # run out of process with a callback to resume
            checkFunc, initFunc = nextHandler.handle(self.tree, self, self.lastRetVal)
            self.handlerResumeFunc = nextHandler.resume
            self.conn.watch_function(checkFunc, initFunc, self.resume)
            shouldReturn = True
        else:
            # log it
            pass
        
        return shouldReturn
    
class Dispatcher:
    pass