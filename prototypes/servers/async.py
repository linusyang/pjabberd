import asyncore, socket, asynchat, cStringIO

class Handler(asynchat.async_chat):
    def __init__(self, conn, addr, server):
        asynchat.async_chat.__init__(self,conn)
        self.client_address = addr
        self.connection = conn
        self.server = server
        self.set_terminator ('\n')
        self.rfile = cStringIO.StringIO()
        self.found_terminator = self.handle_request_line
        
    def collect_incoming_data(self, data):
        self.rfile.write(data)
        
    def handle_request_line(self):
        self.rfile.seek(0)
        a = self.rfile.read(4096)
        self.rfile.truncate(0)

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
    asyncore.loop()