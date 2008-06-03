import asyncore, socket, asynchat, cStringIO, threading, pprint
from dns import resolver

""" Perform an A record lookup on whatever the client sends in.
    This is done asynchronously in a separate thread.
"""

class DNSLookup(threading.Thread):
    def __init__(self, hostname='livejournal.com'):
        threading.Thread.__init__(self)
        self.hostname = hostname;
    def run(self):
        answers = resolver.query(self.hostname, 'A')
        print 'Host:', self.hostname, '. Address:', answers.response.answer[0].items[0].address

class Handler(asynchat.async_chat):
    def __init__(self, conn, addr, server):
        asynchat.async_chat.__init__(self,conn)
        self.client_address = addr
        self.connection = conn
        self.server = server
        self.set_terminator ('\n')
        self.rfile = cStringIO.StringIO()
        self.found_terminator = self.handle_request_line
        print repr(self)
        
    def collect_incoming_data(self, data):
        self.rfile.write(data)
        
    def handle_request_line(self):
        # make the DNS call
        self.rfile.seek(0)
        self.thread = DNSLookup(self.rfile.read(1024))
        self.thread.start()
        self.rfile.truncate(0) # clear the buffer
        
    def handle_close(self):
        pprint.pprint(asyncore.socket_map)
        self.close()
        
class AsyncServer(asyncore.dispatcher):
    def __init__(self, ip, port, handler):
        self.ip = ip
        self.port = port
        self.handler = handler
        asyncore.dispatcher.__init__(self)
        self.create_socket(socket.AF_INET, socket.SOCK_STREAM)
        self.set_reuse_addr()
        self.bind((ip, port))
        self.listen(5)
    
    def handle_accept(self):
        conn, addr = self.accept()
        self.handler(conn, addr, self)

if __name__ == "__main__":
    s = AsyncServer('192.168.1.100', 44444, Handler)
    try:
        asyncore.loop()
    except:
        pprint.pprint(asyncore.socket_map)