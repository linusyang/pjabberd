from pjs.handlers.base import Handler

class SimpleReplyHandler(Handler):
    def __init__(self):
        pass

    def handle(self, tree, msg, lastRetVal=None):
        return 'Just write this out'