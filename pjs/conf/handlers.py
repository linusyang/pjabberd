"""List of handlers and their descriptions. This is modifiable at run-time.
See phases.py for where these handlers are actually used.

See the design doc for information about chained handlers.
"""

# TODO needs to be thread-safe, so maybe introduce functions for retrieving
# the handlers that do some locking.

import pjs.handlers.write
import pjs.handlers.simple
import pjs.handlers.stream
import pjs.handlers.iq
import pjs.handlers.auth
import pjs.handlers.presence
import pjs.handlers.message
import pjs.handlers.route

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
            'in-stream-init' : {
                             'handler' : pjs.handlers.stream.InStreamInitHandler,
                             'description' : 'initializes the stream'
                             },
            'out-stream-init' : {
                                 'handler' : pjs.handlers.stream.OutStreamInitHandler,
                                 'description' : 'handles reply to our s2s stream'
                                 },
            'in-stream-reinit' : {
                               'handler' : pjs.handlers.stream.InStreamReInitHandler,
                               'description' : 'reinitializes the stream'
                               },
            'stream-end' : {
                            'handler' : pjs.handlers.stream.StreamEndHandler,
                            'description' : 'reacts to the stream being ended by the other side'
                            },
            'cleanup-conn' : {
                              'handler' : pjs.handlers.stream.CleanUpConnHandler,
                              'description' : 'cleans up the connection when closed'
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
                           'handler' : pjs.handlers.auth.SASLAuthHandler,
                           'description' : 'incoming SASL auth handler'
                           },
            'sasl-response' : {
                               'handler' : pjs.handlers.auth.SASLResponseHandler,
                               'description' : 'incoming SASL challenge response handler'
                               },
            'sasl-error' : {
                            'handler' : pjs.handlers.auth.SASLErrorHandler,
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
            'iq-auth-get' : {
                             'handler' : pjs.handlers.auth.IQAuthGetHandler,
                             'description' : 'responds to the iq auth get query'
                             },
            'iq-auth-set' : {
                             'handler' : pjs.handlers.auth.IQAuthSetHandler,
                             'description' : 'responds to the iq auth set query'
                             },
            'c2s-message' : {
                             'handler' : pjs.handlers.message.C2SMessageHandler,
                             'description' : '<message> from client'
                             },
            's2s-message' : {
                             'handler' : pjs.handlers.message.S2SMessageHandler,
                             'description' : '<message> from server'
                             },
            'c2s-presence' : {
                              'handler' : pjs.handlers.presence.C2SPresenceHandler,
                              'description' : 'handles plain presence from clients'
                              },
            's2s-presence' : {
                              'handler' : pjs.handlers.presence.S2SPresenceHandler,
                              'description' : 'handles plain presence from servers'
                              },
            'c2s-subscription' : {
                                  'handler' : pjs.handlers.presence.C2SSubscriptionHandler,
                                  'description' : 'subscriptions from clients'
                                  },
            's2s-subscription' : {
                                  'handler' : pjs.handlers.presence.S2SSubscriptionHandler,
                                  'description' : 'subscriptions from servers'
                                  },
            's2s-probe' : {
                           'handler' : pjs.handlers.presence.S2SProbeHandler,
                           'description' : 'handles <presence type="probe"/> from other servers'
                           },
            'new-s2s-conn' : {
                              'handler' : pjs.handlers.stream.NewS2SConnHandler,
                              'description' : 'creates a new S2S connection and sends initial stream'
                              },
            'route-server' : {
                              'handler' : pjs.handlers.route.ServerRouteHandler,
                              'description' : 'routes data to a server'
                              },
            'route-client': {
                             'handler' : pjs.handlers.route.ClientRouteHandler,
                             'description' : 'routes data to a client on this server'
                             }
            }