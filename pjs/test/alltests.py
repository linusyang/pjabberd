""" Complete test suite that runs all available tests """

import unittest
import pjs.test.test_parsers
import pjs.test.test_utils
import pjs.test.test_async

fromModule = unittest.TestLoader().loadTestsFromModule

suite = fromModule(pjs.test.test_parsers)
suite.addTests(fromModule(pjs.test.test_utils))
suite.addTests(fromModule(pjs.test.test_async))

unittest.TextTestRunner().run(suite)