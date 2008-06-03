from pjs.handlers.base import Handler

class SimpleReplyHandler(Handler):
    def handle(self, tree, msg, lastRetVal=None):
        return 'Just write this out'