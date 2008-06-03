import pjs.async.core as asyncore
import pjs.parsers as parsers

class Connection(asyncore.dispatcher_with_send):
    def __init__(self, sock, addr, server):
        asyncore.dispatcher_with_send.__init__(self, sock)
        self.sock = sock
        self.addr = addr
        self.server = server
        
        self.parser = parsers.borrow_parser(self)
        
    def handle_expt(self):
        # log it
        pass
    
    def handle_close(self):
        try:
            self.parser.close()
        except:
            # log it
            pass
        self.parser.reset()
        self.close()
        
    def handle_read(self):
        data = self.recv(4096)
        self.parser.feed(data)
