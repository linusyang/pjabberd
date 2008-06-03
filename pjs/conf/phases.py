""" List of phases and their descriptions """

# TODO: add functions to fetch phases from the config file

phases = {
          'stream-init' : {
                           'description' : 'initializes stream data'
                           },
          'features' : {
                        'description' : 'stream features such as TLS and resource binding',
                        'xpath' : '{http://etherx.jabber.org/streams}features'
                        },
          'sasl-auth' : {
                         'description' : 'SASL\'s <auth>',
                         'xpath' : '{urn:ietf:params:xml:ns:xmpp-sasl}auth'
                         },
          'sasl-response' : {
                             'description' : 'SASL client\'s response to challenge',
                             'xpath' : '{urn:ietf:params:xml:ns:xmpp-sasl}response'
                             },
          'stream-reinit' : {
                             'description' : 'new stream where one already exists'
                             },
          'iq' : {
                  'description' : 'incoming IQ stanza',
                  'xpath' : '{jabber:client}iq'
                  },
          'message' : {
                       'description' : 'incoming message stanza',
                       'xpath' : '{jabber:client}message'
                       },
          'presence' : {
                        'description' : 'incoming presence stanza',
                        'xpath' : '{jabber:client}presence'
                        },
          'db-result' : {
                         'description' : 'result of dialback coming from the other server',
                         'xpath' : '{jabber:server:dialback}result'
                         },
          'db-verify' : {
                         'description' : 'verification of the dialback key',
                         'xpath' : '{jabber:server:dialback}verify'
                         }
          }