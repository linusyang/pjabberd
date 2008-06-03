from random import random
try:
    # python >= 2.5
    from hashlib import sha1
except ImportError:
    from sha import new as sha1
    
import time, os, re

standardNSre = re.compile(r'^{jabber:(client|server)}', re.UNICODE)
customNSre = re.compile(r'^{(.*?)}(.*)')

# This is used in pjs.async.asyncore.
class FunctionCall:
    """Creates a simple object that represents the information required for a
    function call. Its main feature is that it is hashable, so it can be used
    as a key in a dictionary. The properties shouldn't be altered, but if
    they are, the hash doesn't change.
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
            self.hash += k.__str__() + v.__str__()
            
        self.hash = hash(self.hash)
        
    def __hash__(self):
        return self.hash
    

def generateId():
    return sha1(str((random(), time.gmtime(), os.getpid()))).hexdigest()

def tostring(tree):
    def processTree(tree):
        res, tag = decurl(tree.tag)
        res = u'<' + res
        for k,v in tree.items():
            res += " %s='%s'" % (k,v)
        if len(tree) > 0:
            res += '>'
            for i in tree:
                res += processTree(i)
            res += '</%s>' % tag
        else:
            res += '/>'
            
        return res
        
    res = u''
    res += processTree(tree)
    return res

def decurl(tagName):
    res = standardNSre.sub('', tagName)
    res = customNSre.sub(r"\2 xmlns='\1'", res)
    end = res.find(' ')
    if end == -1:
        tag = res
    else:
        tag = res[:end]
    return res, tag