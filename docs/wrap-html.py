#!/usr/bin/python

import sys

filename = sys.argv[1]

f = open(filename, 'r')

print """<!DOCTYPE html PUBLIC "-//W3C//DTD HTML 4.0 Transitional//EN">
<html>
<head>
<link rel='stylesheet' href='css/main.css' type='text/css' />
<title>PJabberd Design Doc</title>
</head>
<body>"""

for line in f:
	print line,

print """</body></html>"""

