"""List of phases and their descriptions. These are modifiable at run-time.
See handlers.py for the definition of the handlers.

See the design doc for description on what phases are for and how they work.
"""

from pjs.conf.handlers import handlers as h
from pjs.utils import PrioritizedDict

# TODO: add functions to fetch phases from the config file

# XMPP core phases (stream, init, db, sasl, tls, etc. no stanzas like iq/message/presence)
_corePhases = {
          'default' : {
                       'description' : 'default phase for when no other matches'
                       },
          'in-stream-init' : {
                           'description' : 'initializes stream data and sends out features',
                           'handlers' : [h['in-stream-init'], h['features-init'], h['write']]
                           },
          'in-stream-reinit' : {
                             'description' : 'new stream where one already exists',
                             'handlers' : [h['in-stream-reinit']]
                             },
          'out-stream-init' : {
                               'description' : 'handling reply to our initial s2s stream',
                               'handlers' : [h['out-stream-init'], h['write']]
                               },
          'stream-end' : {
                          'description' : 'stream ended by the other side',
                          'handlers' : [h['stream-end'], h['cleanup-conn']]
                          },
          'close-stream' : {
                            'description' : 'we actively close the stream',
                            'handlers' : []
                            },
          'features' : {
                        'description' : 'stream features such as TLS and resource binding',
                        'xpath' : '{http://etherx.jabber.org/streams}features',
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
                         },
          'db-verify' : {
                         'description' : 'verification of the dialback key',
                         'xpath' : '{jabber:server:dialback}verify',
                         },
          'test' : {
                    'description' : 'test phase for simple tests',
                    'handlers' : [h['simple-reply'], h['write']]
                    }
          }
corePhases = PrioritizedDict(_corePhases)

# XMPP stanzas for client-to-server (iq/presence/message)
_c2sStanzaPhases = {
    'default' : {
                 'description' : 'default phase for when no other matches'
                 },
    'iq-auth-get' : {
                     'description' : 'responds to iq-auth get',
                     'xpath' : "{jabber:client}iq[@type='get']/{jabber:iq:auth}query",
                     'handlers' : [h['iq-auth-get'], h['write']]
                     },
    'iq-auth-set' : {
                     'description' : 'responds to iq-auth set',
                     'xpath' : "{jabber:client}iq[@type='set']/{jabber:iq:auth}query",
                     'handlers' : [h['iq-auth-set'], h['write']]
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
    'iq-roster-get' : {
                       'description' : 'client requesting their roster',
                       'xpath' : "{jabber:client}iq[@type='get']/{jabber:iq:roster}query",
                       'handlers' : [h['iq-roster-get'], h['write']]
                       },
    'iq-roster-update' : {
                          'description' : 'client adding or updating their roster',
                          'xpath' : "{jabber:client}iq[@type='set']/{jabber:iq:roster}query",
                          'handlers' : [h['iq-roster-update'], h['write']]
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
                 'handlers' : [h['c2s-message']]
                 },
    'c2s-presence' : {
                  'description' : 'incoming presence stanza from client',
                  'xpath' : '{jabber:client}presence',
                  'handlers' : [h['c2s-presence'], h['write']],
                  },
    'c2s-presence-unavailable' : {
              'description' : 'incoming unavailable presence stanza from client',
              'xpath' : "{jabber:client}presence[@type='unavailable']",
              'handlers' : [h['c2s-presence']],
              'priority' : 1
              },
    'subscription' : {
                      'description' : 'subscription handling',
                      'xpath' : "{jabber:client}presence[@type]",
                      'handlers' : [h['c2s-subscription']],
                      'priority' : 1
                      },
    'unknown-iq' : {
                    'description' : 'unknown iq stanza',
                    'xpath' : '{jabber:client}iq',
                    'handlers' : [h['iq-not-implemented'], h['write']],
                    'priority' : -1
                    }
    }
c2sStanzaPhases = PrioritizedDict(_c2sStanzaPhases)

# XMPP stanzas for server-to-server
_s2sStanzaPhases = {
    'default' : {
                 'description' : 'default phase for when no other matches'
                 },
    'subscription' : {
                      'description' : 'subscription handling',
                      'xpath' : "{jabber:server}presence[@type]",
                      'handlers' : [h['s2s-subscription']],
                      'priority' : 1
                      },
    's2s-presence' : {
                      'description' : 'incoming presence from server',
                      'xpath' : "{jabber:server}presence",
                      'handlers' : [h['s2s-presence'], h['write']]
                      },
    's2s-presence-unavailable' : {
                      'description' : 'incoming unavailable ' +\
                                        'presence from server',
                      'xpath' : "{jabber:server}presence[@type='unavailable']",
                      'handlers' : [h['s2s-presence'], h['write']],
                      'priority' : 2
                      },
    's2s-presence-probe' : {
                     'description' : 'incoming <presence type="probe"/> ' +\
                                     'from other servers',
                     'xpath' : "{jabber:server}presence[@type='probe']",
                     'handlers' : [h['s2s-probe']],
                     'priority' : 2
                     },
    'message' : {
                 'description' : '<message>',
                 'xpath' : "{jabber:server}message",
                 'handlers' : [h['s2s-message']]
                 }
    }
s2sStanzaPhases = PrioritizedDict(_s2sStanzaPhases)