""" List of phases and their descriptions """

from pjs.conf.handlers import handlers as h

# TODO: add functions to fetch phases from the config file
# TODO: add ordering to phases, so that we can decide on conflicts

class PrioritizedDict(dict):
    def __init__(self, d=None):
        self.priolist = []
        if d is not None:
            dict.__init__(self, d)
            self.reprioritize()
        else:
            dict.__init__(self)
    def reprioritize(self):
        self.priolist = dict.keys(self)
        self.priolist.sort(cmp=self.compare)
    def compare(self, x, y):
        return dict.get(self, y).get('priority', 0) - dict.get(self, x).get('priority', 0)
    def __iter__(self):
        for i in self.priolist:
            yield i
    def __setitem__(self, key, value):
        dict.__setitem__(self, key, value)
        self.reprioritize()
    def __delitem__(self, key):
        dict.__delitem__(self, key)
        self.reprioritize()
    iterkeys = __iter__
        
#dd = {
#      'a' : { 'name' : 'a', 'priority' : 1},
#      'b' : { 'name' : 'b', 'priority' : 2},
#      'c' : { 'name' : 'c',}
#      }
#d = PrioritizedDict()
#d['a'] = { 'name' : 'a', 'priority' : 1}
#d['b'] = { 'name' : 'b', 'priority' : 2}
#d['c'] = { 'name' : 'c',}
#
#for i in d:
#    print d[i]


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
corePhases = PrioritizedDict(_corePhases)

# XMPP stanzas for client-to-server (iq/presence/message)
_c2sStanzaPhases = {
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
                 'handlers' : []
                 },
    'presence' : {
                  'description' : 'incoming presence stanza',
                  'xpath' : '{jabber:client}presence',
                  'handlers' : [h['presence']],
                  },
    'subscription' : {
                      'description' : 'subscription handling',
                      'xpath' : "{jabber:client}presence[@type]",
                      'handlers' : [h['subscription']],
                      'priority' : 1
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
                      'handlers' : []
                      }
    }
s2sStanzaPhases = PrioritizedDict(_s2sStanzaPhases)