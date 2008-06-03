from SocketServer import TCPServer, ForkingMixIn, StreamRequestHandler

class ThreadedTCPServer(ForkingMixIn, TCPServer): pass
        
class Handler(StreamRequestHandler):
    def handle(self):
        for line in self.rfile:
            a = line
        self.rfile.close()
            
if __name__ == "__main__":
    server = ThreadedTCPServer(('192.168.1.100', 44444), Handler)
    server.serve_forever()