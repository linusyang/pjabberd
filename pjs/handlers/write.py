from pjs.handlers.base import Handler

#TODO: do we need a handler for arbitrary binary data?

class WriteHandler(Handler):
    def handle(self, tree, msg, lastRetVal=None):
        """Attaches the lastRetVal to the message's buffer and sent it
        all out. This only works with unicode strings for now.
        """
        out = msg.outputBuffer
        if lastRetVal and not isinstance(lastRetVal, Exception):
            out += unicode(lastRetVal)
        msg.conn.send(out)
