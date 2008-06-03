import asyncore, socket
from dns import resolver, rdatatype, rdataclass, message

class AsyncDNS(asyncore.dispatcher):
    def __init__(self):
        asyncore.dispatcher.__init__(self)
        self.r = resolver.Resolver()
        self.query = ''
        
        self.create_socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.connect((self.r.nameservers[0], self.r.port))
    
    def makeQuery(self, server):
        self.query = message.make_query('_xmpp-server._tcp.%s' % server,
                                   rdatatype.SRV, rdataclass.IN).to_wire()
        
    def writable(self):
        return (len(self.query) > 0)
    
    def handle_read(self):
        data = self.recv(4096)
        answer = message.from_wire(data)
        print answer.answer[0].to_text()
        
    def handle_write(self):
        self.send(self.query)
        self.query = ''
    def handle_accept(self): pass
    def handle_connect(self): pass
    def handle_bind(self): pass
    def handle_close(self): self.close()


if __name__ == "__main__":
    d = AsyncDNS()
    d.makeQuery('livejournal.com')
    asyncore.loop()
