from pjs.utils import FunctionCall
import unittest

class TestFunctionCall(unittest.TestCase):
    """Testing the FunctionCall helper"""
    
    def setUp(self):
        unittest.TestCase.setUp(self)
    
    def tearDown(self):
        unittest.TestCase.tearDown(self)
        
    def testNoParams(self):
        """Func should be callable without exceptions"""
        def a():
            pass
        fc = FunctionCall(a)
        
        self.assert_(callable(fc.func))
        fc.func()
        
    def testParams(self):
        """Func should be callable with params"""
        def a(p1, p2, p3):
            return p1 + p2 + p3
        
        fc = FunctionCall(a, {'p1' : 'a', 'p2' : 'b', 'p3' : 'c'})
        self.assert_(fc.func(*fc.funcArgs))
        
    def testSameHashFunc(self):
        """If the function is substituted after creation, the hash shouldn't change"""
        def a(): pass
        def b(): return "asdf"
        
        fc = FunctionCall(a)
        hash1 = fc.__hash__()
        fc.func = b
        hash2 = fc.__hash__()
        
        self.assert_(hash1 == hash2)
    
    def testSameHashParams(self):
        """If the args are substituted after creation, the hash shouldn't change"""
        def a(arg1, arg2):
            return arg1+arg2
        
        fc = FunctionCall(a, {'arg1' : 1, 'arg2' : 2})
        hash1 = fc.__hash__()
        fc.funcArgs = {'arg1' : 2, 'arg2' : 'something else'}
        hash2 = fc.__hash__()
        
        self.assert_(hash1 == hash2)
        
        
if __name__ == '__main__':
    unittest.main()