import socket
import threadpool
import time
import random

def go(arg):
	s = socket.socket()
	s.connect(('192.168.1.100', 44444))
	time.sleep(random.randint(0,10))
	s.send('some data\n')
	time.sleep(5)
	s.close()

requests = threadpool.makeRequests(go, [i for i in range(1,10)])
main = threadpool.ThreadPool(5)
[main.putRequest(req) for req in requests]
main.wait()
