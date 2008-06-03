""" Complete test suite that runs all available tests """

import unittest
import pjs.test.test_parsers

suite = unittest.TestLoader().loadTestsFromModule(pjs.test.test_parsers)
unittest.TextTestRunner().run(suite)