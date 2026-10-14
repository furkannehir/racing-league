"""Authentication lifecycle checks with no Firebase or HTTP network access."""
import types
import unittest
from unittest.mock import Mock, patch

import requests
from firebase_admin import auth, exceptions as firebase_errors
from flask import abort, jsonify
from pymongo.errors import ServerSelectionTimeoutError

from test_regressions import RegressionFixture, db
from src.auth_module.auth_controller import auth_blueprint
from src.auth_module.auth_service import AuthError, AuthService, AuthTokens, login_required
from src.user_module.user import User


class AuthTests(RegressionFixture, unittest.TestCase):
    def setUp(self):
        super().setUp()
        self.app.register_blueprint(auth_blueprint)

        @self.app.get('/auth-probe')
        @login_required
        def probe():
            return jsonify({"uid": AuthService.get_current_user(),
                            "email": AuthService.get_current_mongo_user().email,
                            "name": AuthService.get_current_firebase_user().email})

        @self.app.get('/bad-route')
        @login_required
        def bad_route():
            abort(400, 'Invalid token-related route input')

    def provider_response(self, refresh=False, uid='firebase-uid'):
        keys = ('user_id', 'id_token', 'refresh_token', 'expires_in') if refresh else (
            'localId', 'idToken', 'refreshToken', 'expiresIn')
        return Mock(status_code=200, json=Mock(return_value=dict(zip(keys, (
            uid, 'new-id-token', 'new-refresh-token', '3600')))))

    def test_login_returns_refresh_expiry_and_canonical_identity_without_cache(self):
        with patch('src.auth_module.auth_service.requests.post', return_value=self.provider_response()) as post:
            response = self.client.post('/api/v1/auth/login', json={
                'email': self.owner.email.upper(), 'password': 'valid-password'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json['token'], 'new-id-token')
        self.assertEqual(response.json['refreshToken'], 'new-refresh-token')
        self.assertEqual(response.json['expiresIn'], 3600)
        self.assertEqual(response.json['user'], {'id': 'firebase-uid', 'mongoId': str(self.owner._id),
                                                'name': self.owner.name, 'email': self.owner.email})
        self.assertEqual(response.headers['Cache-Control'], 'no-store')
        self.assertEqual(post.call_args.kwargs['timeout'], (5, 10))

    def test_invalid_credentials_do_not_lookup_or_reveal_account_state(self):
        rejected = Mock(status_code=400, json=Mock(return_value={
            'error': {'message': 'INVALID_LOGIN_CREDENTIALS'}}))
        with patch('src.auth_module.auth_service.requests.post', return_value=rejected), \
                patch('firebase_admin.auth.get_user') as get_user:
            responses = [self.client.post('/api/v1/auth/login', json={'email': email, 'password': 'wrong'})
                         for email in (self.owner.email, 'missing@example.test')]
        self.assertEqual([r.status_code for r in responses], [401, 401])
        self.assertEqual(responses[0].json, responses[1].json)
        get_user.assert_not_called()

    def test_bad_login_and_refresh_payloads_do_not_call_provider(self):
        with patch('src.auth_module.auth_service.requests.post') as post:
            for endpoint in ('login', 'refresh'):
                for data in (None, [], {}, {'email': {}, 'password': []}, {'refreshToken': {}}):
                    with self.subTest(endpoint=endpoint, data=data):
                        response = self.client.post('/api/v1/auth/' + endpoint, json=data)
                        self.assertEqual(response.status_code, 400)
            post.assert_not_called()

    def test_refresh_uses_form_exchange_and_checks_returned_identity(self):
        with patch('src.auth_module.auth_service.requests.post', return_value=self.provider_response(True)) as post:
            response = self.client.post('/api/v1/auth/refresh', json={'refreshToken': 'old-refresh'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json['user']['id'], 'firebase-uid')
        self.assertEqual(response.json['refreshToken'], 'new-refresh-token')
        self.assertEqual(post.call_args.kwargs['data'], {
            'grant_type': 'refresh_token', 'refresh_token': 'old-refresh'})
        self.assertNotIn('json', post.call_args.kwargs)
        self.assertEqual(post.call_args.kwargs['timeout'], (5, 10))
        self.assertEqual(response.headers['Cache-Control'], 'no-store')

    def test_invalid_refresh_is_401_but_outages_or_configuration_errors_are_503(self):
        cases = [
            (400, {'error': {'message': 'INVALID_REFRESH_TOKEN'}}, 401),
            (400, {'error': {'message': 'API key not valid. Please pass a valid API key.'}}, 503),
            (429, {}, 503), (503, {}, 503), (200, {'id_token': 'incomplete'}, 503),
        ]
        for status, payload, expected in cases:
            with self.subTest(status=status, payload=payload), \
                    patch('src.auth_module.auth_service.requests.post', return_value=Mock(
                        status_code=status, json=Mock(return_value=payload))):
                response = self.client.post('/api/v1/auth/refresh', json={'refreshToken': 'refresh'})
                self.assertEqual(response.status_code, expected)
                self.assertNotIn('refresh', response.json['message'].lower())
        with patch('src.auth_module.auth_service.requests.post', side_effect=requests.Timeout('private detail')):
            response = self.client.post('/api/v1/auth/login', json={'email': self.owner.email, 'password': 'secret'})
        self.assertEqual(response.status_code, 503)
        self.assertNotIn('private detail', response.get_data(as_text=True))

    def test_exchange_rejects_a_uid_different_from_the_verified_token(self):
        with patch('src.auth_module.auth_service.requests.post', return_value=self.provider_response(uid='other-uid')):
            response = self.client.post('/api/v1/auth/login', json={'email': self.owner.email, 'password': 'password'})
        self.assertEqual(response.status_code, 503)
        self.assertNotIn('token', response.json)

    def test_protected_request_verifies_revocation_once_and_uses_cached_identity(self):
        with patch('firebase_admin.auth.verify_id_token', return_value={
            'user_id': 'firebase-uid', 'email_verified': True}) as verify, \
                patch('firebase_admin.auth.get_user', return_value=types.SimpleNamespace(
                    email=self.owner.email, disabled=False, email_verified=True)) as get_user:
            response = self.client.get('/auth-probe', headers=self.headers)
        self.assertEqual(response.status_code, 200)
        verify.assert_called_once_with('test', check_revoked=True)
        get_user.assert_called_once_with('firebase-uid')
        self.assertEqual(response.json['email'], self.owner.email)
        self.assertEqual(response.headers['Cache-Control'], 'no-store')

    def test_expired_revoked_invalid_and_disabled_tokens_have_distinct_401_codes(self):
        cases = [
            (auth.ExpiredIdTokenError('expired', None), 'token_expired'),
            (auth.RevokedIdTokenError('revoked'), 'token_revoked'),
            (auth.InvalidIdTokenError('invalid'), 'invalid_token'),
            (auth.UserDisabledError('disabled'), 'account_disabled'),
            (auth.UserNotFoundError('deleted'), 'invalid_token'),
        ]
        for failure, code in cases:
            with self.subTest(code=code), patch('firebase_admin.auth.verify_id_token', side_effect=failure):
                response = self.client.get('/auth-probe', headers=self.headers)
                self.assertEqual(response.status_code, 401)
                self.assertEqual(response.json['code'], code)

    def test_missing_or_malformed_bearer_headers_are_401(self):
        for header in ('', 'Basic test', 'Bearer', 'Bearer test extra'):
            with self.subTest(header=header):
                response = self.client.get('/auth-probe', headers={'Authorization': header})
                self.assertEqual(response.status_code, 401)
        self.assertEqual(self.client.get('/auth-probe', headers={'Authorization': 'bearer  test'}).status_code, 200)

    def test_unverified_or_disabled_accounts_cannot_use_valid_tokens(self):
        for verified, disabled in ((False, False), (True, True)):
            with self.subTest(verified=verified, disabled=disabled), \
                    patch('firebase_admin.auth.get_user', return_value=types.SimpleNamespace(
                        email=self.owner.email, email_verified=verified, disabled=disabled)):
                response = self.client.get('/auth-probe', headers=self.headers)
                self.assertEqual(response.status_code, 401)
        with patch('firebase_admin.auth.verify_id_token', return_value={
            'user_id': 'firebase-uid', 'email_verified': False}):
            self.assertEqual(self.client.get('/auth-probe', headers=self.headers).status_code, 401)

    def test_verification_returns_current_profile_and_rejects_deleted_accounts(self):
        db.users.update_one({'_id': self.owner._id}, {'$set': {'name': 'Fresh profile'}})
        response = self.client.get('/api/v1/auth/verify', headers=self.headers)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json['user']['name'], 'Fresh profile')
        User.delete_user(str(self.owner._id))
        response = self.client.get('/api/v1/auth/verify', headers=self.headers)
        self.assertEqual(response.status_code, 401)

    def test_email_casing_resolves_uniquely_but_ambiguous_accounts_are_rejected(self):
        db.users.update_one({'_id': self.owner._id}, {'$set': {'email': self.owner.email.upper()}})
        self.assertEqual(self.client.get('/auth-probe', headers=self.headers).status_code, 200)
        duplicate = User(None, 'Duplicate', self.owner.email)
        duplicate.save()
        self.assertEqual(self.client.get('/auth-probe', headers=self.headers).status_code, 401)

    def test_provider_and_database_outages_preserve_authentication_as_retryable(self):
        with patch('firebase_admin.auth.verify_id_token', side_effect=auth.CertificateFetchError('private', None)):
            response = self.client.get('/auth-probe', headers=self.headers)
            self.assertEqual(response.status_code, 503)
        with patch.object(User, 'get_user_by_auth_email', side_effect=ServerSelectionTimeoutError('private host')):
            response = self.client.get('/auth-probe', headers=self.headers)
            self.assertEqual(response.status_code, 503)
            self.assertNotIn('private host', response.get_data(as_text=True))

    def test_route_errors_are_not_treated_as_invalid_tokens(self):
        response = self.client.get('/bad-route', headers=self.headers)
        self.assertEqual(response.status_code, 400)

    def test_browser_logout_does_not_revoke_other_devices_but_explicit_logout_all_does(self):
        with patch('firebase_admin.auth.revoke_refresh_tokens') as revoke:
            response = self.client.post('/api/v1/auth/logout', headers=self.headers, json={'allDevices': False})
            self.assertEqual(response.status_code, 200)
            revoke.assert_not_called()
            response = self.client.post('/api/v1/auth/logout', headers=self.headers, json={'allDevices': True})
            self.assertEqual(response.status_code, 200)
            revoke.assert_called_once_with('firebase-uid')

    def test_password_change_uses_ui_fields_and_revokes_existing_sessions(self):
        tokens = AuthTokens('firebase-uid', 'token', 'refresh', 3600)
        with patch.object(AuthService, 'login_user', return_value=tokens) as login, \
                patch('firebase_admin.auth.update_user') as update, \
                patch('firebase_admin.auth.revoke_refresh_tokens') as revoke:
            response = self.client.put('/api/v1/users/update/password', headers=self.headers, json={
                'currentPassword': 'old-password', 'newPassword': 'new-password', 'confirmPassword': 'new-password'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json['code'], 'password_updated')
        login.assert_called_once_with(self.owner.email, 'old-password')
        update.assert_called_once_with('firebase-uid', password='new-password')
        revoke.assert_called_once_with('firebase-uid')

    def test_password_failures_do_not_report_success_or_end_a_valid_session(self):
        tokens = AuthTokens('firebase-uid', 'token', 'refresh', 3600)
        for exception, expected in ((ValueError('bad password'), 400),
                                    (firebase_errors.UnavailableError('private'), 503)):
            with self.subTest(expected=expected), patch.object(AuthService, 'login_user', return_value=tokens), \
                    patch('firebase_admin.auth.update_user', side_effect=exception), \
                    patch('firebase_admin.auth.revoke_refresh_tokens') as revoke:
                response = self.client.put('/api/v1/users/update/password', headers=self.headers, json={
                    'currentPassword': 'old-password', 'newPassword': 'new-password'})
                self.assertEqual(response.status_code, expected)
                revoke.assert_not_called()

    def test_password_changed_but_failed_revocation_is_explicitly_reported(self):
        with patch.object(AuthService, 'login_user', return_value=AuthTokens('firebase-uid', 'token', 'refresh', 3600)), \
                patch('firebase_admin.auth.update_user'), \
                patch('firebase_admin.auth.revoke_refresh_tokens', side_effect=firebase_errors.UnavailableError('private')):
            response = self.client.put('/api/v1/users/update/password', headers=self.headers, json={
                'currentPassword': 'old-password', 'newPassword': 'new-password'})
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json['code'], 'password_changed_revocation_failed')
        self.assertIn('password was changed', response.json['message'])

    def test_wrong_password_or_mismatched_identity_cannot_change_another_account(self):
        for result in (AuthError('Invalid credentials', 'invalid_credentials'),
                       AuthTokens('another-user', 'token', 'refresh', 3600)):
            with self.subTest(result=type(result).__name__), \
                    patch.object(AuthService, 'login_user', **(
                        {'side_effect': result} if isinstance(result, Exception) else {'return_value': result})), \
                    patch('firebase_admin.auth.update_user') as update, \
                    patch('firebase_admin.auth.revoke_refresh_tokens') as revoke:
                response = self.client.put('/api/v1/users/update/password', headers=self.headers, json={
                    'currentPassword': 'wrong-password', 'newPassword': 'new-password'})
                self.assertEqual(response.status_code, 400)
                update.assert_not_called()
                revoke.assert_not_called()

    def test_refresh_cannot_restore_a_revoked_unverified_or_deleted_account(self):
        with patch('src.auth_module.auth_service.requests.post', return_value=self.provider_response(True)):
            with patch('firebase_admin.auth.verify_id_token', side_effect=auth.RevokedIdTokenError('revoked')):
                response = self.client.post('/api/v1/auth/refresh', json={'refreshToken': 'old-refresh'})
                self.assertEqual(response.status_code, 401)
                self.assertEqual(response.json['code'], 'token_revoked')
                self.assertNotIn('token', response.json)
            with patch('firebase_admin.auth.get_user', return_value=types.SimpleNamespace(
                    email=self.owner.email, disabled=False, email_verified=False)):
                response = self.client.post('/api/v1/auth/refresh', json={'refreshToken': 'old-refresh'})
                self.assertEqual(response.status_code, 401)
                self.assertEqual(response.json['code'], 'email_not_verified')
            User.delete_user(str(self.owner._id))
            response = self.client.post('/api/v1/auth/refresh', json={'refreshToken': 'old-refresh'})
            self.assertEqual(response.status_code, 401)
            self.assertEqual(response.json['code'], 'account_unavailable')
