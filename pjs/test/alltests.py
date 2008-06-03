""" Complete test suite that runs all available tests """

import unittest
import pjs.test.test_parsers
import pjs.test.test_utils
import pjs.test.test_async
import pjs.test.test_events
import pjs.test.test_xmpp

fromModule = unittest.TestLoader().loadTestsFromModule

suite = fromModule(pjs.test.test_parsers)
suite.addTests(fromModule(pjs.test.test_utils))
suite.addTests(fromModule(pjs.test.test_async))
suite.addTests(fromModule(pjs.test.test_events))

# this doesn't work, because unittest does not import the helper classes
# run test_xmpp directly instead
# suite.addTests(fromModule(pjs.test.test_xmpp))

unittest.TextTestRunner().run(suite)

import os

os.system('python ' + pjs.test.test_xmpp.__file__)
