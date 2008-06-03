"""Authentication mechanisms (SASL and iq-auth)"""

# Some of this code (ie. some SASL decoding) is borrowed from Twisted.
# See TWISTED-LICENCE for defails.

import binascii
import base64
import re

from pjs.db import DBautocommit
from pjs.utils import generateId
from pjs.elementtree.ElementTree import Element
from pjs.jid import JID

try:
    # python >= 2.5
    from hashlib import md5, sha1
except ImportError:
    from md5 import new as md5
    from sha import new as sha1

try:
    # Python >= 2.4
    from base64 import b64decode, b64encode
except ImportError:
    import base64

    def b64encode(s):
        return "".join(base64.encodestring(s).split("\n"))

    b64decode = base64.decodestring

base64Pattern = re.compile("^[0-9A-Za-z+/]*[0-9A-Za-z+/=]{,2}$")

def fromBase64(s):
    """
    Decode base64 encoded string.

    This helper performs regular decoding of a base64 encoded string, but also
    rejects any characters that are not in the base64 alphabet and padding
    occurring elsewhere from the last or last two characters, as specified in
    section 14.9 of RFC 3920. This safeguards against various attack vectors
    among which the creation of a covert channel that "leaks" information.
    """

    if base64Pattern.match(s) is None:
        raise

    return b64decode(s) # could raise an exception if cannot decode

def H(s):
    """Let H(s) be the 16 octet MD5 hash [RFC 1321] of the octet string s.

    See: RFC 2831
    """
    return md5(s).digest()

def HEX(n):
    """Let HEX(n) be the representation of the 16 octet MD5 hash n as a
    string of 32 hex digits (with alphabetic characters always in lower
    case, since MD5 is case sensitive).

    See: RFC 2831
    """
    return binascii.b2a_hex(n)

def KD(k, s):
    """Let KD(k, s) be H({k, ":", s}), i.e., the 16 octet hash of the string
    k, a colon and the string s.

    See: RFC 2831
    """
    return H('%s:%s' % (k, s))

class SASLPlain:
    """Implements the SASL PLAIN authentication mechanism"""
    def __init__(self, msg):
        self.msg = msg

    def handle(self, b64text):
        """Verify the username/password in response"""
        authtext = ''
        if b64text:
            try:
                authtext = fromBase64(b64text)
            except:
                raise SASLIncorrectEncodingError

            auth = authtext.split('\x00')

            if len(auth) != 3:
                raise SASLIncorrectEncodingError

            con = DBautocommit()
            c = con.cursor()
            c.execute("SELECT * FROM jids WHERE \
                jid = ? AND password = ?", (auth[1] + \
                                            '@' + self.msg.conn.server.hostname, auth[2]))
            res = c.fetchall()
            if len(res) == 0:
                c.close()
                con.close()
                raise SASLAuthError
            c.close()
            con.close()

        self.msg.conn.data['sasl']['complete'] = True
        self.msg.conn.data['sasl']['in-progress'] = False
        self.msg.conn.data['user']['jid'] = '%s@%s' % (auth[1], self.msg.conn.server.hostname)

        # record the JID for local delivery
        self.msg.conn.server.conns[self.msg.conn.id] = (JID(self.msg.conn.data['user']['jid']),
                                                        self.msg.conn)

        self.msg.conn.parser.resetParser()

        return Element('success',
                       {'xmlns' : 'urn:ietf:params:xml:ns:xmpp-sasl'})

class SASLDigestMD5:
    """Implements the SASL's DIGEST-MD5 authentication mechanism. Stores state
    of the authentication, so should be saved between requests.
    handle() should be called more than once for a successful auth.
    """

    # states
    INIT = 0
    SENT_CHALLENGE1 = 1
    SENT_CHALLENGE2 = 2

    # max # of auth failures before reset of state
    MAX_FAILURES = 2


    def __init__(self, msg):
        """
        msg -- the Message object. This has to be passed in, because this object
                may be shared between Message instances
        """
        self.nonce = None
        self.nc = 0x0
        self.realm = msg.conn.server.hostname
        self.msg = msg
        self.username = None
        self.failures = 0
        self.state = SASLDigestMD5.INIT

    def handle(self, data=None):
        """Performs DIGEST-MD5 auth based on current state.

        data -- either None for initial challenge, base64-encoded text when
                the client responds to challenge 1, or the tree when the client
                responds to challenge 2.
        """

        # TODO: authz
        # TODO: subsequent auth

        qop = 'qop="auth"'
        charset = 'charset=utf-8'
        algo = 'algorithm=md5-sess'

        if self.state == SASLDigestMD5.INIT: # initial challenge
            self.nonce = generateId()
            self.state = SASLDigestMD5.SENT_CHALLENGE1

            nonce = 'nonce="%s"' % self.nonce
            realm = 'realm="%s"' % self.realm

            res = Element('challenge',
                          {'xmlns' : 'urn:ietf:params:xml:ns:xmpp-sasl'})
            res.text = base64.b64encode(','.join([realm, qop, nonce, charset, algo]))

            return res
        elif self.state == SASLDigestMD5.SENT_CHALLENGE1 and data:
            # response to client's reponse (ie. challenge 2)
            try:
                text = fromBase64(data)
            except:
                raise SASLIncorrectEncodingError

            pairs = self._parse(text)
            try:
                username = pairs['username']
                nonce = pairs['nonce']
                realm = pairs['realm']
                cnonce = pairs['cnonce']
                nc = pairs['nc']
                qop = pairs['qop']
                response = pairs['response']
                digest_uri = pairs['digest-uri']
            except KeyError:
                self._handleFailure()
                raise SASLAuthError

            self.username = username

            # authz is ignored for now
            if nonce != self.nonce or realm != self.realm \
                or int(nc, 16) != 1 or qop[0] != 'auth' or not response\
                or not digest_uri:
                self._handleFailure()
                raise SASLAuthError

            # fetch the password now
            con = DBautocommit()
            c = con.cursor()
            c.execute("SELECT password FROM jids WHERE \
                jid = ?", (username + '@%s' % self.msg.conn.server.hostname,))
            for row in c:
                password = row['password']
                break
            else:
                self._handleFailure()
                c.close()
                con.close()
                raise SASLAuthError
            c.close()
            con.close()

            # compute the digest as per RFC 2831
            a1 = "%s:%s:%s" % (H("%s:%s:%s" % (username, realm, password)),
                               nonce, cnonce)
            a2 = ":%s" % digest_uri
            a2client = "AUTHENTICATE:%s" % digest_uri

            digest = HEX(KD(HEX(H(a1)),
                            "%s:%s:%s:%s:%s" % (nonce, nc,
                                                  cnonce, "auth",
                                                  HEX(H(a2client)))))

            if digest == response:
                rspauth = HEX(KD(HEX(H(a1)),
                                 "%s:%s:%s:%s:%s" % (nonce, nc,
                                                       cnonce, "auth",
                                                       HEX(H(a2)))))

                self.state = SASLDigestMD5.SENT_CHALLENGE2

                res = Element('challenge',
                              {'xmlns' : 'urn:ietf:params:xml:ns:xmpp-sasl'})
                res.text = base64.b64encode(u"rspauth=%s" % rspauth)

                return res

            else:
                self._handleFailure()
                raise SASLAuthError
        elif self.state == SASLDigestMD5.SENT_CHALLENGE2 and isinstance(data, Element):
            # expect to get <response xmlns='urn:ietf:params:xml:ns:xmpp-sasl'/>
            respInd = data.tag.find('{urn:ietf:params:xml:ns:xmpp-sasl}response')
            d = self.msg.conn.data
            if respInd != -1 and len(data) == 0:
                self.state = SASLDigestMD5.INIT
                d['sasl']['complete'] = True
                d['sasl']['in-progress'] = False
                d['user']['jid'] = '%s@%s' % (self.username,
                                            self.msg.conn.server.hostname)

                # record the JID for local delivery
                self.msg.conn.server.conns[self.msg.conn.id] = (JID(d['user']['jid']),
                                                                self.msg.conn)

                self.msg.conn.parser.resetParser()

                res = Element('success',
                              {'xmlns' : 'urn:ietf:params:xml:ns:xmpp-sasl'})
                return res
            else:
                self._handleFailure()
                raise SASLAuthError
        else:
            self._handleFailure()
            raise SASLAuthError


    def _parse(self, challenge):
        """Parses the client's response to our challenge 1.
        This code is a modified version of twisted's auth_mechanisms.py.
        See TWISTED-LICENSE.
        """
        s = challenge
        paramDict = {}
        cur = 0 # current starting position
        remainingParams = True
        while remainingParams:
            # Parse a param. We can't just split on commas, because there can
            # be some commas inside (quoted) param values, e.g.:
            # qop="auth,auth-int"

            middle = s.index("=", cur)
            if middle < 1: # can't have a blank key
                raise SASLIncorrectEncodingError
            name = s[cur:middle].lstrip()
            middle += 1
            if s[middle] == '"':
                middle += 1
                end = s.index('"', middle)
                if end == -1:
                    raise SASLIncorrectEncodingError
                value = s[middle:end]
                cur = s.find(',', end) + 1
                if cur == 0:
                    remainingParams = False
            else:
                end = s.find(',', middle)
                if end == -1:
                    value = s[middle:].rstrip()
                    remainingParams = False
                else:
                    value = s[middle:end].rstrip()
                cur = end + 1
            paramDict[name] = value

        for param in ('qop', 'cipher'):
            if param in paramDict:
                paramDict[param] = paramDict[param].split(',')

        return paramDict

    def _handleFailure(self):
        self.failures += 1
        if (self.failures > SASLDigestMD5.MAX_FAILURES):
            self.failures = 0
            self.state = SASLDigestMD5.INIT

class IQAuthPlain:
    """Handles the old-style jabber:iq:auth plaintext auth"""
    def __init__(self, msg):
        self.msg = msg

    def handle(self, username, password):
        con = DBautocommit()
        c = con.cursor()
        c.execute("SELECT password FROM jids WHERE \
            jid = ?", (username + '@%s' % self.msg.conn.server.hostname,))
        res = c.fetchone()
        if res:
            password = res[0]
        else:
            c.close()
            con.close()
            raise IQAuthError
        c.close()
        con.close()

        d = self.msg.conn.data
        d['user']['jid'] = '%s@%s' % (username, self.msg.conn.server.hostname)
        # record the JID for local delivery
        self.msg.conn.server.conns[self.msg.conn.id] = (JID(d['user']['jid']),
                                                        self.msg.conn)

        self.msg.conn.parser.resetParser()

class IQAuthDigest:
    """Handles the old-style jabber:iq:auth digest auth"""
    def __init__(self, msg):
        self.msg = msg
        self.streamid = msg.conn.data['stream']['id']
    def handle(self, username, digest):
        con = DBautocommit()
        c = con.cursor()
        c.execute("SELECT password FROM jids WHERE \
            jid = ?", (username + '@%s' % self.msg.conn.server.hostname,))
        res = c.fetchone()
        if res:
            password = res[0]
        else:
            c.close()
            con.close()
            raise IQAuthError
        c.close()
        con.close()

        s = sha1()
        s.update(self.streamid + password)
        hashtext = s.hexdigest()

        if hashtext == digest:
            d = self.msg.conn.data
            d['user']['jid'] = '%s@%s' % (username,
                                          self.msg.conn.server.hostname)

            # record the JID for local delivery
            self.msg.conn.server.conns[self.msg.conn.id] = (JID(d['user']['jid']),
                                                            self.msg.conn)

            self.msg.conn.parser.resetParser()
            return
        else:
            raise IQAuthError

class IQAuthError(Exception):
    pass

class SASLError(Exception):
    def errorElement(self):
        raise NotImplementedError, 'must be overridden in a subclass'
class SASLIncorrectEncodingError(SASLError):
    def errorElement(self):
        return Element('incorrect-encoding')
class SASLInvalidAuthzError(SASLError):
    def errorElement(self):
        return Element('invalid-authzid')
class SASLInvalidMechanismError(SASLError):
    def errorElement(self):
        return Element('invalid-mechanism')
class SASLMechanismTooWeakError(SASLError):
    def errorElement(self):
        return Element('mechanism-too-weak')
class SASLAuthError(SASLError):
    def errorElement(self):
        return Element('not-authorized')
class SASLTempAuthError(SASLError):
    def errorElement(self):
        return Element('temporary-auth-failure')