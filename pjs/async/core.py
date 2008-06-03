from asyncore import *
from asyncore import _exception
import asyncore

try:
    func_map # dictionary of FunctionCall => callback
except NameError:
    func_map = {}
    
def pollWithFunctions(timeout=0.0, map=None):
    if map is None:
        map = socket_map
    if map:
        r = []; w = []; e = []
        for fd, obj in map.items():
            is_r = obj.readable()
            is_w = obj.writable()
            if is_r:
                r.append(fd)
            if is_w:
                w.append(fd)
            if is_r or is_w:
                e.append(fd)
        if [] == r == w == e:
            time.sleep(timeout)
        else:
            try:
                r, w, e = select.select(r, w, e, timeout)
            except select.error, err:
                if err[0] != EINTR:
                    raise
                else:
                    return

        for fd in r:
            obj = map.get(fd)
            if obj is None:
                continue
            read(obj)

        for fd in w:
            obj = map.get(fd)
            if obj is None:
                continue
            write(obj)

        for fd in e:
            obj = map.get(fd)
            if obj is None:
                continue
            _exception(obj)
        
    if func_map:
        funcCheck()
        
def poll2WithFunctions(timeout=0.0, map=None):
    # Use the poll() support added to the select module in Python 2.0
    if map is None:
        map = socket_map
    if timeout is not None:
        # timeout is in milliseconds
        timeout = int(timeout*1000)
    pollster = select.poll()
    if map:
        for fd, obj in map.items():
            flags = 0
            if obj.readable():
                flags |= select.POLLIN | select.POLLPRI
            if obj.writable():
                flags |= select.POLLOUT
            if flags:
                # Only check for exceptions if object was either readable
                # or writable.
                flags |= select.POLLERR | select.POLLHUP | select.POLLNVAL
                pollster.register(fd, flags)
        try:
            r = pollster.poll(timeout)
        except select.error, err:
            if err[0] != EINTR:
                raise
            r = []
        for fd, flags in r:
            obj = map.get(fd)
            if obj is None:
                continue
            readwrite(obj, flags)
            
    if func_map:
        funcCheck()
        
poll = pollWithFunctions
poll2 = poll2WithFunctions
poll3 = poll2

def funcCheck():
    """Try running all functions in the map with params. Whenever one returns
    True, call its callback func.
    """
    for f in func_map.keys():
        ret = False
        cb = func_map[f]
        
        try:
            ret = f.func(*f.funcArgs)
        except Exception, e:
            cb(e)
        
        if ret:
            cb()
            del func_map[f]

class dispatcherWithFunctions(asyncore.dispatcher):
    def __init__(self, sock=None, map=None):
        asyncore.dispatcher.__init__(self, sock, map)
        
    ### ======================= ###
    ### Function watching stuff ###
    ### ======================= ###
    def watch_function(self, checkFunc, cb, initFunc=None):
        """Start watching function checkFunc.func for return value of True.
        This executes initFunc.func once before running checkFunc (if provided).
        When checkFunc.func returns True, cb is called. checkFunc and
        initFunc are pjs.utils.FunctionCall objects, so that they are
        hashable in func_map.
        
        If an exception is raised when calling initFunc.func or checkFunc.func,
        cb will be passed the exception as a parameter, so it should be of the
        form: def cb(exception=None)
        """
        assert(hasattr(checkFunc, 'func') and callable(cb))

        if (initFunc):
            assert(hasattr(initFunc, 'func'))
            try:
                initFunc.func(*initFunc.funcArgs)
            except Exception, e:
                cb(e)
                return
        
        func_map[checkFunc] = cb

dispatcher = dispatcherWithFunctions

class dispatcher_with_sendWithFunctions(asyncore.dispatcher_with_send):
    def __init__(self, sock=None, map=None):
        asyncore.dispatcher_with_send.__init__(self, sock, map)
    
    ### ======================= ###
    ### Function watching stuff ###
    ### ======================= ###
    def watch_function(self, checkFunc, cb, initFunc=None):
        """Start watching function checkFunc.func for return value of True.
        This executes initFunc.func once before running checkFunc (if provided).
        When checkFunc.func returns True, cb is called. checkFunc and
        initFunc are pjs.utils.FunctionCall objects, so that they are
        hashable in func_map.
        
        If an exception is raised when calling initFunc.func or checkFunc.func,
        cb will be passed the exception as a parameter, so it should be of the
        form: def cb(exception=None)
        """
        assert(hasattr(checkFunc, 'func') and callable(cb))

        if (initFunc):
            assert(hasattr(initFunc, 'func'))
            try:
                initFunc.func(*initFunc.funcArgs)
            except Exception, e:
                cb(e)
                return
        
        func_map[checkFunc] = cb
        
dispatcher_with_send = dispatcher_with_sendWithFunctions