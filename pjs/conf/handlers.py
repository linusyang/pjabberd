"""List of handlers and their descriptions"""

import pjs.handlers.write
import pjs.handlers.simple
import pjs.handlers.stream

# TODO: add functions to fetch handlers from the config file

handlers = {
            'write' : {
                       'handler' : pjs.handlers.write.WriteHandler,
                       'description' : 'queues data for sending to underlying connection'
                       },
            'simple-reply' : {
                              'handler' : pjs.handlers.simple.SimpleReplyHandler,
                              'description' : 'sends a simple reply (non-XMPP)'
                              },
            'stream-init' : {
                             'handler' : pjs.handlers.stream.StreamInitHandler,
                             'description' : 'initializes the stream'
                             }
            }