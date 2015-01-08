"""
Test out our authentication module.
"""
import os
import unittest

import mock

from archelond.web import wsgi_app
from archelond.auth import (
    check_basic_auth,
    generate_token,
    get_hashhash,
    get_signature,
    check_token_auth
)


class TestAuth(unittest.TestCase):
    """
    Verify each piece of our authentication module using
    the htpasswd in tests/config/
    """
    TEST_USER = 'foo'
    TEST_PASS = 'bar'
    TEST_TOKEN = ('eyJhbGciOiJIUzI1NiJ9.eyJ1c2VybmFtZSI6ImZvbyIsImhhc2'
                  'hoYXNoIjoiNTEwNjI3M2Y3Nzg5ZjFlMjZiNGEyMTI3ODk5OTJmN'
                  'zVjMTU0MzNmNDAyZjNlOTRhZDE4ZTdjODBhZWU4MGZhZiJ9.Bas'
                  'bIHjgUzemMiBI34SmbiOkOm49ktZZWrFT6b71mVs')
    NOT_USER = 'notuser'

    def setUp(self):
        """
        Change the app.config and build the app object
        """

        os.environ['ARCHELOND_CONF'] = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            'config', 'basic.py'
        )
        self.app = wsgi_app()
        # Set well known secret for known token generation
        self.app.config['FLASK_SECRET'] = 'wellknown'

    def test_check_basic_auth(self):
        """
        Validate a test user works with the correct password
        and doesn't with a bad one
        """
        with self.app.app_context():
            print(self.app.config['users'].users())
            self.assertTrue(self.TEST_USER in self.app.config['users'].users())
            # Verify positive case
            valid, username = check_basic_auth(self.TEST_USER, self.TEST_PASS)
            self.assertTrue(valid)
            self.assertEqual(username, self.TEST_USER)

            # Verify negative password case
            valid, username = check_basic_auth(self.TEST_USER, 'blah')
            self.assertFalse(valid)
            self.assertEqual(self.TEST_USER, username)

            # Verify negative user case
            not_user = self.NOT_USER
            self.assertTrue(not_user not in self.app.config['users'].users())
            valid, username = check_basic_auth(not_user, 'blah')
            self.assertFalse(valid)
            self.assertEqual(not_user, username)

    def test_token_generation(self):
        """
        Verify token generation using known hashes and signature
        """
        test_user = self.TEST_USER
        not_user = self.NOT_USER
        known_token = self.TEST_TOKEN
        known_hashhash = ('5106273f7789f1e26b4a212789992f75c15433f402f3e94a'
                          'd18e7c80aee80faf')

        with self.app.app_context():

            # Verify token generation against known value
            token = generate_token(test_user)
            self.assertEqual(known_token, token)

            # Verify hashhash against known value
            hashhash = get_hashhash(test_user)
            self.assertEqual(hashhash, known_hashhash)

            # Now go ahead and verify the reverse
            serializer = get_signature()
            data = serializer.loads(token)
            self.assertTrue(data['username'], test_user)
            self.assertTrue(data['hashhash'], hashhash)

            # Verify no user handling (don't really care what
            # exception gets raised).
            with self.assertRaises(Exception):
                token = generate_token(not_user)

    @mock.patch('archelond.auth.log')
    def test_token_auth(self, log):
        """
        Validate authentication by token works properly
        """
        with self.app.app_context():
            # Test bad token
            valid, username = check_token_auth('asdfasdf.asdfasdf')
            self.assertEqual(False, valid)
            self.assertEqual(None, username)
            log.warn.assert_called_with('Received bad token signature')

            # Test bad username, but valid signature for users that have
            # been deleted
            sig = get_signature()
            token = sig.dumps({
                'username': self.NOT_USER,
            })
            valid, username = check_token_auth(token)
            self.assertEqual(False, valid)
            self.assertEqual(None, username)
            log.warn.assert_called_with(
                'Token auth signed message, but invalid user %s',
                self.NOT_USER
            )
