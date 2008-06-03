import pjs.async.core as asyncore
import pjs.parsers as parsers

from tlslite.integration.TLSAsyncDispatcherMixIn import TLSAsyncDispatcherMixIn

class Connection(asyncore.dispatcher_with_send):
    def __init__(self, sock, addr, server):
        asyncore.dispatcher_with_send.__init__(self, sock)
        self.sock = sock
        self.addr = addr
        self.server = server
        
        self.parser = parsers.borrow_parser(self)
        
        # any sort of per-connection data. can be accessed by handlers.
        # right now:
        # 'stream' : {
        #              'in-stream' : True/False (False before <stream> sent and after </stream>),
        #              'type' : 'client'/'server' (ie. c2s/s2s),
        #              'id' : streamid (as str)
        #            },
        # 'sasl' : {
        #            'mech' : 'PLAIN' / 'DIGEST-MD5',
        #            'challenge' : str (last sasl challenge),
        #            'stage' : int,
        #            'complete' : True/False
        #          },
        # 'tls' : {
        #           'complete' : True/False
        #         }
        # 'user' : {
        #            'jid' : str (server-assigned jid),
        #            'resource' : str (server-assigned resource),
        #            'in-session' : True/False (True if <session> sent/accepted)
        #          },
        #
        self.data = {}
        
    def handle_expt(self):
        # log it
        pass
    
    def handle_close(self):
        try:
            self.parser.close()
        except:
            # log it
            pass
        self.parser.resetStream()
        self.close()
        
    def handle_read(self):
        data = self.recv(4096)
        self.parser.feed(data)
