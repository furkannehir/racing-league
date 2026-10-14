"""Registration, profile, and account email failures with isolated external services."""
import types
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from firebase_admin import auth, exceptions as firebase_errors
from pymongo.errors import AutoReconnect, OperationFailure, ServerSelectionTimeoutError
from test_regressions import RegressionFixture, db
from src.auth_module.auth_controller import auth_blueprint
from src.auth_module.auth_service import AuthError, AuthService, AuthTokens
from src.config import mongo
from src.email_module import account_notifications as notifications
from src.email_module.email_service import EmailService
from src.user_module.account_service import registration_lease
from src.user_module.user import User


class AccountTests(RegressionFixture, unittest.TestCase):
    def setUp(self):
        super().setUp()
        self.app.register_blueprint(auth_blueprint)
        for user in (self.owner, self.driver, self.other):
            user.email = user.email.replace('.test', '.com')
            user.update()
        self.firebase = types.SimpleNamespace(uid='new-firebase-uid', email='new@example.com',
                                              disabled=False, email_verified=False)
        self.create_user = self.start_patch(patch('firebase_admin.auth.create_user', return_value=self.firebase))
        self.delete_user = self.start_patch(patch('firebase_admin.auth.delete_user'))
        self.start_patch(patch('firebase_admin.auth.get_user_by_email', side_effect=self.firebase_by_email))
        self.start_patch(patch('src.auth_module.auth_service.requests.post',
                               side_effect=AssertionError('An external authentication call was not mocked')))
        EmailService.reset_mock()
        for method in (EmailService.send_verification_email, EmailService.send_reset_password_email):
            method.reset_mock(return_value=True, side_effect=True)

    def start_patch(self, value):
        result = value.start()
        self.addCleanup(value.stop)
        return result

    def firebase_by_email(self, email):
        user = User.get_user_by_auth_email(email)
        if user is None:
            raise auth.UserNotFoundError('Missing user', None, None)
        return types.SimpleNamespace(uid=user.firebase_uid or 'firebase-uid', email=user.email,
                                     disabled=False, email_verified=False)

    def register(self, **overrides):
        payload = {'name': ' New driver ', 'email': ' NEW@EXAMPLE.COM ', 'password': 'valid-password'}
        payload.update(overrides)
        return self.client.post('/api/v1/auth/register', json=payload)

    def test_registration_stores_identity_and_verification_work_together(self):
        response = self.register()
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json['emailStatus'], 'queued')
        user = User.get_user_by_auth_email('new@example.com')
        self.assertEqual(user.name, 'New driver')
        self.assertEqual(user.bio, '')
        self.assertEqual(user.firebase_uid, self.firebase.uid)
        self.create_user.assert_called_once_with(email='new@example.com', password='valid-password',
                                                  display_name='New driver')
        self.assertEqual(db.account_notifications.count_documents({'status': 'pending'}), 1)
        self.assertEqual(db.registration_leases.count_documents({}), 0)
        EmailService.send_verification_email.assert_not_called()
        self.assertEqual(response.headers['Cache-Control'], 'no-store')

    def test_registered_account_signs_in_after_verification_with_its_stable_identity(self):
        self.assertEqual(self.register().status_code, 201)
        user = User.get_user_by_auth_email(self.firebase.email)
        self.actor = user
        credentials = AuthTokens(self.firebase.uid, 'id-token', 'refresh-token', 3600)
        with patch.object(AuthService, 'login_user', return_value=credentials), \
                patch('firebase_admin.auth.get_user', return_value=self.firebase), \
                patch('firebase_admin.auth.verify_id_token', return_value={
                    'user_id': self.firebase.uid, 'email_verified': False}):
            self.assertEqual(self.client.post('/api/v1/auth/login', json={
                'email': user.email, 'password': 'valid-password'}).status_code, 401)
        self.firebase.email_verified = True
        with patch.object(AuthService, 'login_user', return_value=credentials), \
                patch('firebase_admin.auth.get_user', return_value=self.firebase), \
                patch('firebase_admin.auth.verify_id_token', return_value={
                    'user_id': self.firebase.uid, 'email_verified': True}):
            signed_in = self.client.post('/api/v1/auth/login', json={'email': user.email, 'password': 'valid-password'})
            profile = self.client.get('/api/v1/users/profile', headers=self.headers)
        self.assertEqual(signed_in.status_code, 200)
        self.assertEqual(signed_in.json['user']['mongoId'], str(user._id))
        self.assertEqual(profile.json['name'], 'New driver')

    def test_invalid_registration_never_creates_an_account(self):
        cases = [None, [], {}, {'name': 'Name', 'email': {}, 'password': 'password'},
                 {'name': 'Name', 'email': 'invalid', 'password': 'password'},
                 {'name': ' ', 'email': 'new@example.com', 'password': 'password'},
                 {'name': 'x' * 101, 'email': 'new@example.com', 'password': 'password'},
                 {'name': 'Name', 'email': 'new@example.com', 'password': []},
                 {'name': 'Name', 'email': 'new@example.com', 'password': 'short'},
                 {'name': 'Name', 'email': 'new@example.com', 'password': 'x' * 129}]
        for data in cases:
            with self.subTest(data=data):
                self.assertEqual(self.client.post('/api/v1/auth/register', json=data).status_code, 400)
        self.create_user.assert_not_called()
        self.assertEqual(db.users.count_documents({}), 3)
        self.assertEqual(db.registration_leases.count_documents({}), 0)

    def test_registration_rejects_case_variants_deleted_accounts_and_client_identity(self):
        self.assertEqual(self.register(email=self.owner.email.upper()).status_code, 409)
        User.delete_user(self.owner._id)
        self.assertEqual(self.register(email=self.owner.email).status_code, 409)
        self.assertEqual(self.register(firebase_uid='someone-else').status_code, 400)
        self.create_user.assert_not_called()

    def test_registration_firebase_failure_is_sanitized_without_application_writes(self):
        with patch('firebase_admin.auth.create_user', side_effect=firebase_errors.UnavailableError('Private key detail')):
            response = self.register()
        self.assertEqual(response.status_code, 503)
        self.assertNotIn('Private key detail', response.get_data(as_text=True))
        self.assertEqual(db.users.count_documents({}), 3)
        self.assertEqual(db.account_notifications.count_documents({}), 0)

    def test_registration_database_failure_compensates_only_its_new_firebase_account(self):
        with patch.object(User, 'save', side_effect=OperationFailure('Sensitive database detail')):
            response = self.register()
        self.assertEqual(response.status_code, 503)
        self.delete_user.assert_called_once_with(self.firebase.uid)
        self.assertEqual(db.users.count_documents({}), 3)
        self.assertEqual(db.account_notifications.count_documents({}), 0)
        self.assertNotIn('Sensitive database detail', response.get_data(as_text=True))

    def test_outbox_failure_rolls_back_the_profile_and_cleans_up_firebase(self):
        with patch.object(notifications, 'enqueue', side_effect=OperationFailure('Queue unavailable')):
            response = self.register()
        self.assertEqual(response.status_code, 503)
        self.assertIsNone(User.get_user_by_auth_email(self.firebase.email))
        self.delete_user.assert_called_once_with(self.firebase.uid)

    def test_uncertain_commit_does_not_delete_a_committed_account(self):
        def committed_without_ack(callback):
            before = db.users.find_one({'firebase_uid': self.firebase.uid})
            result = callback(None)
            if before is None and db.users.find_one({'firebase_uid': self.firebase.uid}):
                raise AutoReconnect('Commit acknowledgement was lost')
            return result
        with patch.object(mongo, 'run_transaction', side_effect=committed_without_ack):
            response = self.register()
        self.assertEqual(response.status_code, 201)
        self.assertIsNotNone(User.get_user_by_auth_email(self.firebase.email))
        self.assertEqual(db.account_notifications.count_documents({}), 1)
        self.delete_user.assert_not_called()

    def test_unconfirmed_persistence_does_not_delete_a_potentially_committed_account(self):
        with patch.object(User, 'save', side_effect=AutoReconnect('Write outcome unknown')), \
                patch.object(User, 'get_by_firebase_uid', side_effect=ServerSelectionTimeoutError('Database unreachable')):
            response = self.register()
        self.assertEqual(response.status_code, 503)
        self.delete_user.assert_not_called()

    def test_failed_cleanup_can_be_recovered_with_the_same_credentials(self):
        with patch.object(User, 'save', side_effect=OperationFailure('Write failed')), \
                patch('firebase_admin.auth.delete_user', side_effect=firebase_errors.UnavailableError('Cleanup unavailable')):
            self.assertEqual(self.register().status_code, 503)
        with patch('firebase_admin.auth.create_user', side_effect=auth.EmailAlreadyExistsError('Already created', None, None)), \
                patch.object(AuthService, 'login_user', return_value=AuthTokens(self.firebase.uid, 'id', 'refresh', 3600)), \
                patch('firebase_admin.auth.get_user', return_value=self.firebase):
            recovered = self.register()
        self.assertEqual(recovered.status_code, 201)
        self.assertEqual(User.get_user_by_auth_email(self.firebase.email).firebase_uid, self.firebase.uid)

    def test_existing_firebase_account_is_not_recovered_without_password_proof(self):
        with patch('firebase_admin.auth.create_user', side_effect=auth.EmailAlreadyExistsError('Already created', None, None)), \
                patch.object(AuthService, 'login_user', side_effect=AuthError('Wrong password', 'invalid_credentials')):
            response = self.register()
        self.assertEqual(response.status_code, 409)
        self.assertIsNone(User.get_user_by_auth_email(self.firebase.email))
        self.delete_user.assert_not_called()

    def test_recovery_rejects_disabled_or_differently_addressed_firebase_accounts(self):
        for changes in ({'disabled': True}, {'email': 'different@example.com'}):
            with self.subTest(changes=changes), \
                    patch('firebase_admin.auth.create_user', side_effect=auth.EmailAlreadyExistsError('Exists', None, None)), \
                    patch.object(AuthService, 'login_user', return_value=AuthTokens(self.firebase.uid, 'id', 'refresh', 3600)), \
                    patch('firebase_admin.auth.get_user', return_value=types.SimpleNamespace(**{
                        **vars(self.firebase), **changes})):
                self.assertEqual(self.register().status_code, 409)
        self.assertEqual(db.users.count_documents({}), 3)
        self.delete_user.assert_not_called()

    def test_failed_recovery_does_not_delete_a_preexisting_firebase_account(self):
        with patch('firebase_admin.auth.create_user', side_effect=auth.EmailAlreadyExistsError('Already created', None, None)), \
                patch.object(AuthService, 'login_user', return_value=AuthTokens(self.firebase.uid, 'id', 'refresh', 3600)), \
                patch('firebase_admin.auth.get_user', return_value=self.firebase), \
                patch.object(User, 'save', side_effect=OperationFailure('Database unavailable')):
            response = self.register()
        self.assertEqual(response.status_code, 503)
        self.delete_user.assert_not_called()

    def test_registration_lease_blocks_concurrent_recovery_and_allows_expired_leases(self):
        with registration_lease('new@example.com'):
            response = self.register()
            self.assertEqual(response.status_code, 409)
            self.assertEqual(response.json['code'], 'registration_in_progress')
            self.create_user.assert_not_called()
        with registration_lease('new@example.com') as lease:
            db.registration_leases.update_one(lease, {'$set': {
                'expires_at': datetime.now(timezone.utc) - timedelta(seconds=1)}})
            self.assertEqual(self.register().status_code, 201)

    def test_lost_registration_lease_cannot_delete_an_account_or_release_another_lease(self):
        def lose_lease(uid):
            db.registration_leases.update_one({}, {'$set': {'token': 'another-attempt'}})
            return None
        with patch.object(User, 'save', side_effect=OperationFailure('Database failed')), \
                patch.object(User, 'get_by_firebase_uid', side_effect=lose_lease):
            self.assertEqual(self.register().status_code, 503)
        self.delete_user.assert_not_called()
        self.assertEqual(db.registration_leases.find_one({})['token'], 'another-attempt')

    def test_profile_saves_name_and_bio_and_preserves_identity_and_membership(self):
        league, _ = self.make_league()
        response = self.client.put('/api/v1/users/update', headers=self.headers,
                                  json={'name': ' New name ', 'bio': ' Racing is fun '})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json['name'], 'New name')
        self.assertEqual(response.json['bio'], 'Racing is fun')
        self.assertEqual(response.json['_id'], str(self.owner._id))
        self.assertEqual(response.json['email'], self.owner.email)
        loaded = self.client.get('/api/v1/users/profile', headers=self.headers)
        self.assertEqual(loaded.json['bio'], 'Racing is fun')
        self.assertEqual(db.league_members.count_documents({'league_id': league._id, 'user_id': str(self.owner._id)}), 1)
        self.assertNotIn('firebase_uid', response.json)

    def test_partial_profile_updates_and_clearing_bio_do_not_overwrite_other_fields(self):
        path = '/api/v1/users/update'
        self.client.put(path, headers=self.headers, json={'name': 'Saved name', 'bio': 'Saved bio'})
        response = self.client.put(path, headers=self.headers, json={'bio': ''})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json['name'], 'Saved name')
        self.assertEqual(response.json['bio'], '')
        self.assertEqual(self.client.put(path, headers=self.headers, json={
            'name': 'Legacy client', 'email': self.owner.email.upper()}).status_code, 200)

    def test_invalid_profile_fields_are_rejected_without_partial_changes(self):
        invalid = [None, [], {}, {'name': ''}, {'name': None}, {'name': 'x' * 101},
                   {'bio': {}}, {'bio': 'x' * 1001}, {'email': 'other@example.com', 'name': 'Changed'},
                   {'name': 'Changed', 'role': 'admin'}, {'firebase_uid': 'another-uid'}]
        for data in invalid:
            with self.subTest(data=data):
                self.assertEqual(self.client.put('/api/v1/users/update', headers=self.headers, json=data).status_code, 400)
        stored = User.get_user_by_id(self.owner._id)
        self.assertEqual(stored.name, self.owner.name)
        self.assertEqual(stored.email, self.owner.email)
        self.assertEqual(stored.bio, '')

    def test_profile_database_failure_is_not_reported_as_saved(self):
        with patch.object(User, 'update_profile', side_effect=OperationFailure('Sensitive diagnostic')):
            response = self.client.put('/api/v1/users/update', headers=self.headers, json={'name': 'Updated'})
        self.assertEqual(response.status_code, 503)
        self.assertNotIn('Sensitive diagnostic', response.get_data(as_text=True))

    def test_password_length_validation_runs_before_provider_calls(self):
        with patch.object(AuthService, 'login_user') as login:
            for password in ('short', 'x' * 129):
                response = self.client.put('/api/v1/users/update/password', headers=self.headers,
                                          json={'currentPassword': 'old-password', 'newPassword': password})
                self.assertEqual(response.status_code, 400)
            login.assert_not_called()

    def test_profile_disappearing_after_authentication_is_not_reported_as_saved(self):
        with patch.object(User, 'update_profile', return_value=None):
            response = self.client.put('/api/v1/users/update', headers=self.headers, json={'name': 'Updated'})
        self.assertEqual(response.status_code, 401)

    def test_bio_is_not_added_to_other_users_or_inviter_summaries(self):
        db.users.update_one({'_id': self.owner._id}, {'$set': {'bio': 'Personal biography'}})
        self.assertNotIn('bio', self.client.get(f'/api/v1/users/{self.owner._id}', headers=self.headers).json)
        self.assertIn('bio', self.client.get('/api/v1/users/profile', headers=self.headers).json)

    def test_profile_reads_cannot_fetch_another_accounts_email_by_id(self):
        path = f'/api/v1/users/{self.owner._id}'
        self.assertEqual(self.client.get(path, headers=self.headers).status_code, 200)
        self.actor = self.driver
        self.assertEqual(self.client.get(path, headers=self.headers).status_code, 404)
        self.assertEqual(self.client.get(path).status_code, 401)
        self.actor = self.other
        self.assertEqual(self.client.get(f'/api/v1/users/{self.other._id}', headers=self.headers).status_code, 200)

    def test_new_accounts_cannot_be_used_by_a_different_firebase_identity_with_the_same_email(self):
        db.users.update_one({'_id': self.owner._id}, {'$set': {'firebase_uid': 'different-firebase-uid'}})
        response = self.client.get('/api/v1/users/profile', headers=self.headers)
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json['code'], 'account_unavailable')

    def test_public_email_requests_are_uniform_and_coalesce_without_inline_email(self):
        for kind, endpoint in [('password_reset', 'reset-password'), ('verification', 'verification-email')]:
            responses = [self.client.post('/api/v1/auth/' + endpoint, json={'email': email})
                         for email in (self.owner.email.upper(), 'missing@example.com', self.owner.email)]
            self.assertEqual([r.status_code for r in responses], [202, 202, 202])
            self.assertEqual(responses[0].json, responses[1].json)
            self.assertEqual(db.account_notifications.count_documents({'kind': kind}), 2)
        EmailService.send_verification_email.assert_not_called()
        EmailService.send_reset_password_email.assert_not_called()
        self.assertEqual(notifications.process_pending(), 4)
        self.assertEqual(db.account_notifications.count_documents({'status': 'sent'}), 2)
        self.assertEqual(db.account_notifications.count_documents({'status': 'cancelled'}), 2)

    def test_firebase_only_signup_can_reset_its_password_without_restoring_a_deleted_profile(self):
        notifications.request_email('password_reset', self.firebase.email)
        with patch('firebase_admin.auth.get_user_by_email', return_value=self.firebase):
            self.assertEqual(notifications.process_pending(), 1)
        EmailService.send_reset_password_email.assert_called_once_with(to_email=self.firebase.email, name='')
        self.assertIsNone(User.get_user_by_auth_email(self.firebase.email))
        User.delete_user(self.owner._id)
        notifications.request_email('password_reset', self.owner.email)
        with patch('firebase_admin.auth.get_user_by_email', return_value=self.firebase) as lookup:
            notifications.process_pending()
            lookup.assert_not_called()
        self.assertEqual(EmailService.send_reset_password_email.call_count, 1)

    def test_account_email_delivery_recovers_leases_and_bounds_retries(self):
        notifications.request_email('verification', self.owner.email)
        old = notifications.claim_next()
        db.account_notifications.update_one({'_id': old['_id']}, {'$set': {
            'lock_until': datetime.now(timezone.utc) - timedelta(seconds=1)}})
        current = notifications.claim_next()
        self.assertNotEqual(old['claim_token'], current['claim_token'])
        self.assertEqual(notifications.deliver_claimed(old), 'cancelled')
        EmailService.send_verification_email.assert_not_called()
        with patch.object(EmailService, 'send_verification_email', return_value=None):
            self.assertEqual(notifications.deliver_claimed(current), 'failed')
            self.assertEqual(notifications.process_pending(), 0)
            for _ in range(8):
                db.account_notifications.update_many({}, {'$set': {
                    'retry_at': datetime.now(timezone.utc) - timedelta(seconds=1)}})
                notifications.process_pending()
        self.assertEqual(db.account_notifications.find_one({})['attempts'], notifications.MAX_ATTEMPTS)
        self.assertIsNone(notifications.claim_next())

    def test_account_email_cooldown_applies_to_known_and_unknown_addresses(self):
        for email in (self.owner.email, 'missing@example.com'):
            notifications.request_email('verification', email)
        notifications.process_pending()
        for email in (self.owner.email, 'missing@example.com'):
            response = self.client.post('/api/v1/auth/verification-email', json={'email': email})
            self.assertEqual(response.status_code, 429)
        db.account_notifications.update_many({}, {'$set': {
            'queued_at': datetime.now(timezone.utc) - timedelta(minutes=2), 'window_count': 3}})
        for email in (self.owner.email, 'missing@example.com'):
            self.assertEqual(self.client.post('/api/v1/auth/verification-email', json={'email': email}).status_code, 429)
        db.account_notifications.update_many({}, {'$set': {
            'window_start': datetime.now(timezone.utc) - timedelta(hours=2)}})
        self.assertEqual(self.client.post('/api/v1/auth/verification-email', json={'email': self.owner.email}).status_code, 202)

    def test_prior_unknown_email_work_cannot_block_initial_registration(self):
        notifications.request_email('verification', self.firebase.email)
        claimed = notifications.claim_next()
        self.assertEqual(self.register().status_code, 201)
        self.assertEqual(notifications.deliver_claimed(claimed), 'cancelled')
        self.assertEqual(notifications.process_pending(), 1)
        EmailService.send_verification_email.assert_called_once()

    def test_verified_disabled_deleted_or_rebound_accounts_do_not_receive_verification_email(self):
        notifications.request_email('verification', self.owner.email)
        with patch('firebase_admin.auth.get_user_by_email', return_value=types.SimpleNamespace(
                uid='firebase-uid', email=self.owner.email, email_verified=True, disabled=False)):
            self.assertEqual(notifications.process_pending(), 1)
        self.assertEqual(db.account_notifications.find_one({})['status'], 'cancelled')
        EmailService.send_verification_email.assert_not_called()
        for case in ('disabled', 'deleted', 'rebound'):
            with self.subTest(case=case):
                db.account_notifications.delete_many({})
                notifications.request_email('verification', self.owner.email)
                if case == 'deleted':
                    User.delete_user(self.owner._id)
                elif case == 'rebound':
                    db.users.update_one({'_id': self.owner._id}, {'$set': {'deleted_at': None, 'firebase_uid': 'bound-uid'}})
                with patch('firebase_admin.auth.get_user_by_email', return_value=types.SimpleNamespace(
                        uid='other-uid', email=self.owner.email, email_verified=False, disabled=case == 'disabled')):
                    notifications.process_pending()
                self.assertEqual(db.account_notifications.find_one({})['status'], 'cancelled')
        EmailService.send_verification_email.assert_not_called()

    def test_bad_or_unavailable_public_email_requests_do_not_claim_success(self):
        for endpoint in ('verification-email', 'reset-password'):
            for data in (None, [], {}, {'email': {}}, {'email': 'invalid'}):
                self.assertEqual(self.client.post('/api/v1/auth/' + endpoint, json=data).status_code, 400)
            with patch('src.auth_module.auth_controller.request_email', side_effect=OperationFailure('Private detail')):
                response = self.client.post('/api/v1/auth/' + endpoint, json={'email': self.owner.email})
            self.assertEqual(response.status_code, 503)
            self.assertNotIn('Private detail', response.get_data(as_text=True))
