import socket
import threadpool

def go(arg):
	for i in range(1,10):
		s = socket.socket()
		s.connect(('192.168.1.100', 44444))
		s.send('some data\n')
		s.close()

requests = threadpool.makeRequests(go, [i for i in range(1,1000)])
main = threadpool.ThreadPool(20)
[main.putRequest(req) for req in requests]
main.wait()
