""" Initializes the server for most unit tests """

import pjs.conf.conf
import logging
from pjs.pjsserver import PJSLauncher

pjs.conf.conf.launcher = PJSLauncher()

# don't show logs
logging.basicConfig(level=logging.CRITICAL)