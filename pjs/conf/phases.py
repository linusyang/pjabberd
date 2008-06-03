""" List of phases and their descriptions """

from pjs.conf.handlers import handlers as h

# TODO: add functions to fetch phases from the config file
# TODO: add ordering to phases, so that we can decide on conflicts

phases = {
          'default' : {
                       'description' : 'default phase for when no other matches'
                       },
          'stream-init' : {
                           'description' : 'initializes stream data',
                           'handlers' : [h['stream-init'], h['write']]
                           },
          'features' : {
                        'description' : 'stream features such as TLS and resource binding',
                        'xpath' : '{http://etherx.jabber.org/streams}features',
                        'handlers' : []
                        },
          'sasl-auth' : {
                         'description' : 'SASL\'s <auth>',
                         'xpath' : '{urn:ietf:params:xml:ns:xmpp-sasl}auth',
                         'handlers' : []
                         },
          'sasl-response' : {
                             'description' : 'SASL client\'s response to challenge',
                             'xpath' : '{urn:ietf:params:xml:ns:xmpp-sasl}response',
                             'handlers' : []
                             },
          'stream-reinit' : {
                             'description' : 'new stream where one already exists',
                             'handlers' : []
                             },
          'iq' : {
                  'description' : 'incoming IQ stanza',
                  'xpath' : '{jabber:client}iq',
                  'handlers' : []
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