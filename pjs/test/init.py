""" Initializes the server for most unit tests """

import pjs.conf.conf
import logging
from pjs.pjsserver import PJSLauncher, populateDB as _popDB

pjs.conf.conf.launcher = PJSLauncher()

# don't show logs
logging.basicConfig(level=logging.CRITICAL)

# init the DB once
if '_initedDB' not in dir():
    _initedDB = True
    _popDB()