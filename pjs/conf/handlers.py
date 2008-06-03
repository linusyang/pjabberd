"""List of handlers and their descriptions"""

import pjs.handlers.write
import pjs.handlers.simple
import pjs.handlers.stream
import pjs.handlers.iq
import pjs.handlers.sasl
import pjs.handlers.presence

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
                             },
            'stream-reinit' : {
                               'handler' : pjs.handlers.stream.StreamReInitHandler,
                               'description' : 'reinitializes the stream'
                               },
            'stream-end' : {
                            'handler' : pjs.handlers.stream.StreamEndHandler,
                            'description' : 'cleans up when the stream is ended by the other side'
                            },
            'features-init' : {
                               'handler' : pjs.handlers.stream.FeaturesInitHandler,
                               'description' : 'sends out initial features'
                               },
            'features-auth' : {
                              'handler' : pjs.handlers.stream.FeaturesAuthHandler,
                              'description' : 'sends out the auth features'
                              },
            'features-postauth' : {
                                   'handler' : pjs.handlers.stream.FeaturesPostAuthHandler,
                                   'description' : 'sends out the post-auth features'
                                   },
            'iq-not-implemented' : {
                                    'handler' : pjs.handlers.iq.IQNotImplementedHandler,
                                    'description' : 'returns a iq-not-implemented error'
                                    },
            'sasl-auth' : {
                           'handler' : pjs.handlers.sasl.SASLAuthHandler,
                           'description' : 'incoming SASL auth handler'
                           },
            'sasl-response' : {
                               'handler' : pjs.handlers.sasl.SASLResponseHandler,
                               'description' : 'incoming SASL challenge response handler'
                               },
            'sasl-error' : {
                            'handler' : pjs.handlers.sasl.SASLErrorHandler,
                            'description' : 'handles SASLErrors and responds with '+\
                                            'appropriate failure element'
                            },
            'iq-bind' : {
                         'handler' : pjs.handlers.iq.IQBindHandler,
                         'description' : 'handles resource binding'
                         },
            'iq-session' : {
                          'handler' : pjs.handlers.iq.IQSessionHandler,
                          'description' : 'handles session binding'
                          },
            'iq-roster-get' : {
                               'handler' : pjs.handlers.iq.IQRosterGetHandler,
                               'description' : 'handles roster get requests'
                               },
            'iq-roster-update' : {
                                  'handler' : pjs.handlers.iq.IQRosterUpdateHandler,
                                  'description' : 'handles roster add/update requests'
                                  },
            'roster-push' : {
                             'handler' : pjs.handlers.iq.RosterPushHandler,
                             'description' : 'uses the last return value to push ' +\
                                             'the roster change to all connected resources'
                             },
            'subscription' : {
                              'handler' : pjs.handlers.presence.SubscriptionHandler,
                              'description' : 'takes care of subscriptions'
                              }
            }