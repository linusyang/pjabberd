"""Contains the basic interfaces for handlers, documentation and
helper functions.
"""

import pjs.threadpool

class Handler:
    """Generic in-process handler (cannot block)"""
    def __init__(self):
        """Will be called at server start"""
        pass

    def handle(self, tree, msg, lastRetVal=None):
        """Handle a message.

        tree -- ET's Element. Usually the stanza within the <stream> element
        msg -- reference to the Message object that's running this Handler
        lastRetVal -- the return value of the last executed Handler within the
                      chain being run by msg. This could be an Exception
                      object or None.
        """
        raise NotImplementedError, 'needs to be overridden in a subclass'

class ThreadedHandler:
    """Generic threaded handler. This handler should start a thread or ask a
    threadpool to execute a function, then return promptly. The function being
    run in the thread can block if needed, but the handler must be able to
    continue running after the thread's done.
    """
    def __init__(self):
        """Will be called at server start"""
        pass

    def handle(self, tree, msg, lastRetVal=None):
        """Handle a message.

        tree -- ET's Element. Usually the stanza within the <stream> element
        msg -- reference to the Message object that's running this Handler
        lastRetVal -- the return value of the last executed Handler within the
                      chain being run by msg. This could be an Exception
                      object or None.

        This method MUST NOT block and MUST return a tuple of two
        pjs.utils.FunctionCall objects. The first of the two FunctionCall
        objects is for the checking function and the second is for the
        initiating function. Neither function can block. The initiating
        function is called once before the checking function. The checking
        function is called periodically; when its return value is True
        self.resume() is called. The initiating function can be None.
        """
        raise NotImplementedError, 'needs to be overridden in a subclass'
    def resume(self):
        """Called when the thread has finished running. Cannot block."""
        raise NotImplementedError, 'needs to be overridden in a subclass'

def poll(threadpool):
    """Polls the threadpool. ThreadedHandler's checking functions should do
    this to make the threadpool pick up results.
    """
    try:
        threadpool.poll()
    except pjs.threadpool.NoResultsPending:
        pass

def chainOutput(lastRetVal, out):
    """Attaches out to lastRetVal and returns the result. This is used for
    chaining return values in handlers. If lastRetVal is not a list, a new list
    is created with lastRetVal being its first element.
    """
    if not isinstance(lastRetVal, list):
        if lastRetVal is not None:
            lastRetVal = [lastRetVal]
        else:
            lastRetVal = []
    lastRetVal.append(out)
    return lastRetVal