import pjs.async.core as async
#import asyncore as async
from pjs.utils import FunctionCall
import socket

class Server(async.dispatcher):
    def __init__(self):
        async.dispatcher.__init__(self)
        
        self.create_socket(socket.AF_INET, socket.SOCK_STREAM)
        self.set_reuse_addr()
        self.bind(('', 44444))
        self.listen(5)
        
    def handle_accept(self):
        conn, addr = self.accept()
        
        Handler(conn)
    
    def handle_close(self):
        self.close()
        
class Handler(async.dispatcher):
    def __init__(self, sock):
        async.dispatcher.__init__(self, sock)
    
    def handle_read(self):
        def cb(exception=None):
            print 'called back', exception
            
        def check(asdf):
            print asdf
            return True

        checkFunc = FunctionCall(check, {'asdf' : 'test string'})
        self.watch_function(checkFunc, cb)
        print self.recv(4096)
        
    def handle_write(self): pass
        
    def handle_close(self):
        self.close()
        

if __name__ == "__main__":
    s = Server()
    async.loop()
    