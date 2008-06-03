"""Useful functions that can (and should) be used by handlers"""

from threading import RLock
from random import random

try:
    # python >= 2.5
    from hashlib import sha1
except ImportError:
    from sha import new as sha1

import time, os, re, sys

standardNSre = re.compile(r'^{jabber:(client|server)}', re.UNICODE)
customNSre = re.compile(r'^{(.*?)}(.*)')

# This is used in pjs.async.core.
class FunctionCall:
    """Creates a simple object that represents the information required for a
    function call. Its main feature is that it is hashable, so it can be used
    as a key in a dictionary. The properties shouldn't be altered, but if
    they are, the hash doesn't change.

    This should be used by ThreadedHandlers to return initiating and checking
    functions from their handle() methods.
    """
    def __init__(self, func, funcArgs={}):
        assert(callable(func))
        assert(type(funcArgs) == type({}))

        self.func = func
        self.funcArgs = funcArgs

        # build the value to hash on by concatinating string representations
        # of the parameters.
        self.hash = func.__str__()
        for k, v in funcArgs.items():
            self.hash += k.__repr__() + v.__repr__()

        self.hash = hash(self.hash)

    def __hash__(self):
        return self.hash


def generateId():
    """Generates a unique id for anything"""
    return sha1(str((random(), time.gmtime(), os.getpid()))).hexdigest()

def tostring(tree):
    """Converts ET's Element into an XML string. It assumes the default
    namespace is jabber:client or jabber:server and strips those out.
    For other elements it attaches the xmlns attribute to their ns-clear tags.
    This is a workaround for ET's broken tostring(), which returns crazy stuff
    like:
    <ns0:a xmlns:ns0="asdf"><ns0:b>asdfasdf</ns0:b></ns0:a>
    """
    def processTree(tree):
        res, tag = decurl(tree.tag)
        res = u'<' + res
        for k,v in tree.items():
            res += " %s='%s'" % (k,v)
        if len(tree) > 0 or tree.text:
            res += '>'
            if tree.text:
                res += tree.text
            for i in tree:
                res += processTree(i)
                if i.tail:
                    res += i.tail
            res += '</%s>' % tag
        else:
            res += '/>'

        return res

    res = u''
    res += processTree(tree)
    return res

def decurl(tagName):
    """Returns the "tag xmls='ns'" and 'tag' tuple. This is for parsing out
    the tag name and the namespace out of ElementTree's Elements.
    """
    res = standardNSre.sub('', tagName)
    res = customNSre.sub(r"\2 xmlns='\1'", res)
    end = res.find(' ')
    if end == -1:
        tag = res
    else:
        tag = res[:end]
    return res, tag

def compact_traceback():
    """Used in asyncore and threadpool. Can be called in an except clause
    to get the stack trace for the exception.
    Returns ((file, function, line), type, value, stack-as-a-string)
    """
    t, v, tb = sys.exc_info()
    tbinfo = []
    assert tb # Must have a traceback
    while tb:
        tbinfo.append((
            tb.tb_frame.f_code.co_filename,
            tb.tb_frame.f_code.co_name,
            str(tb.tb_lineno)
            ))
        tb = tb.tb_next

    # just to be safe
    del tb

    file, function, line = tbinfo[-1]
    info = ' '.join(['[%s|%s|%s]' % x for x in tbinfo])
    return (file, function, line), t, v, info

class PrioritizedDict(dict):
    """A dictionary that has order during iteration based on a 'priority'
    key of every key/value pair. The higher the priority value the earlier
    the pair will come in an iteration.

    Example: d = {'a' : {'name' : 'A'}, 'b' : {'name' : 'B', 'priority' : 1}}
    When iterated over, the 'b' pair with priority 1 will come first, since the
    default priority is 0.
    """
    def __init__(self, d=None):
        self.priolist = []
        if d is not None:
            dict.__init__(self, d)
            self.reprioritize()
        else:
            dict.__init__(self)
    def reprioritize(self):
        self.priolist = dict.keys(self)
        self.priolist.sort(cmp=self.compare)
    def compare(self, x, y):
        return dict.get(self, y).get('priority', 0) - dict.get(self, x).get('priority', 0)
    def __iter__(self):
        for i in self.priolist:
            yield i
    def __setitem__(self, key, value):
        dict.__setitem__(self, key, value)
        self.reprioritize()
    def __delitem__(self, key):
        dict.__delitem__(self, key)
        self.reprioritize()
    iterkeys = __iter__

#dd = {
#      'a' : { 'name' : 'a', 'priority' : 1},
#      'b' : { 'name' : 'b', 'priority' : 2},
#      'c' : { 'name' : 'c',}
#      }
#d = PrioritizedDict()
#d['a'] = { 'name' : 'a', 'priority' : 1}
#d['b'] = { 'name' : 'b', 'priority' : 2}
#d['c'] = { 'name' : 'c',}
#
#for i in d:
#    print d[i]

# this is not used anywhere right now
class SynchronizedDict(dict):
    """A dictionary that only allows one thread to access or modify it
    at a time.
    """
    def __init__(self, d=None):
        self.lock = RLock()
        self.lock.acquire()
        try:
            if d is not None:
                dict.__init__(self, d)
            else:
                dict.__init__(self)
        finally:
            self.lock.release()

    def __getitem__(self, key):
        self.lock.acquire()
        try:
            return dict.__getitem__(self, key)
        finally:
            self.lock.release()

    def __setitem__(self, key, value):
        self.lock.acquire()
        try:
            dict.__setitem__(self, key, value)
        finally:
            self.lock.release()

    def __delitem__(self, key):
        self.lock.acquire()
        try:
            dict.__delitem__(self, key)
        finally:
            self.lock.release()

    def __len__(self):
        self.lock.acquire()
        try:
            return dict.__len__(self)
        finally:
            self.lock.release()

    def __iter__(self):
        self.lock.acquire()
        try:
            for k in dict.keys(self):
                yield k
        finally:
            self.lock.release()

    def __contains__(self, item):
        self.lock.acquire()
        try:
            return dict.__contains__(self, item)
        finally:
            self.lock.release()