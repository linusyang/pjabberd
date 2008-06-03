"""Not really used anywhere. Just an example of the simplest handler."""

from pjs.handlers.base import Handler

class SimpleReplyHandler(Handler):
    def handle(self, tree, msg, lastRetVal=None):
        return 'Just write this out'