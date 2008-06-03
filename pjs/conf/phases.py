""" List of phases and their descriptions """

from pjs.conf.handlers import handlers as h

# TODO: add functions to fetch phases from the config file
# TODO: add ordering to phases, so that we can decide on conflicts


# XMPP core phases (stream, init, db, sasl, tls, etc. no stanzas like iq/message/presence)
corePhases = {
          'default' : {
                       'description' : 'default phase for when no other matches'
                       },
          'stream-init' : {
                           'description' : 'initializes stream data and sends out features',
                           'handlers' : [h['stream-init'], h['features-init'], h['write']]
                           },
          'stream-reinit' : {
                             'description' : 'new stream where one already exists',
                             'handlers' : [h['stream-reinit']]
                             },
          'stream-end' : {
                          'description' : 'stream ended by the other side',
                          'handlers' : [h['stream-end']]
                          },
          'features' : {
                        'description' : 'stream features such as TLS and resource binding',
                        'xpath' : '{http://etherx.jabber.org/streams}features',
                        'handlers' : []
                        },
          'sasl-auth' : {
                         'description' : 'SASL\'s <auth>',
                         'xpath' : '{urn:ietf:params:xml:ns:xmpp-sasl}auth',
                         'handlers' : [h['sasl-auth'], h['write']],
                         'errorHandlers' : [h['sasl-error']]
                         },
          'sasl-response' : {
                             'description' : 'SASL client\'s response to challenge',
                             'xpath' : '{urn:ietf:params:xml:ns:xmpp-sasl}response',
                             'handlers' : [h['sasl-response'], h['write']],
                             'errorHandlers' : [h['sasl-error']]
                             },
          'sasl-abort' : {
                          'description' : 'initiating entity aborts auth',
                          'xpath' : '{urn:ietf:params:xml:ns:xmpp-sasl}abort',
                          'handlers' : [],
                          'errorHandlers' : [h['sasl-error']]
                          },
          'db-result' : {
                         'description' : 'result of dialback coming from the other server',
                         'xpath' : '{jabber:server:dialback}result',
                         'handlers' : []
                         },
          'db-verify' : {
                         'description' : 'verification of the dialback key',
                         'xpath' : '{jabber:server:dialback}verify',
                         'handlers' : []
                         },
          'test' : {
                    'description' : 'test phase for simple tests',
                    'handlers' : [h['simple-reply'], h['write']]
                    }
          }

# XMPP stanzas (iq/presence/message)
stanzaPhases = {
                'default' : {
                             'description' : 'default phase for when no other matches'
                             }, 
                'iq-bind' : {
                             'description' : 'client binding a resource', 
                             'xpath' : "{jabber:client}iq[@type='set']/{urn:ietf:params:xml:ns:xmpp-bind}bind", 
                             'handlers' : [h['iq-bind'], h['write']]
                             },
                'iq-session' : {
                                'description' : 'client binding a session',
                                'xpath' : "{jabber:client}iq[@type='set']/{urn:ietf:params:xml:ns:xmpp-session}session",
                                'handlers' : [h['iq-session'], h['write']]
                                },
                'iq-disco-items' : {
                                    'description' : 'discovery',
                                    'xpath' : "{jabber:client}iq[@type='get']/{http://jabber.org/protocol/disco#items}query",
                                    'handlers' : [h['iq-not-implemented'], h['write']]
                                    },
                'iq-disco-info' : {
                                   'description' : 'server info',
                                   'xpath' : "{jabber:client}iq[@type='get']/{http://jabber.org/protocol/disco#info}query",
                                   'handlers' : [h['iq-not-implemented'], h['write']]
                                   },
                'message' : {
                             'description' : 'incoming message stanza',
                             'xpath' : '{jabber:client}message',
                             'handlers' : []
                             },
                'presence' : {
                              'description' : 'incoming presence stanza',
                              'xpath' : '{jabber:client}presence',
                              'handlers' : []
                              }
                }