from pjs.handlers.base import Handler

class WriteHandler(Handler):
    def __init__(self):
        pass
    
    def handle(self, tree, msg, lastRetVal=None):
        if lastRetVal:
            msg.conn.send(lastRetVal)
