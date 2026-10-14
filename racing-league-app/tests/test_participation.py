"""Membership, invitation, transaction, and notification regressions with isolated data."""
import unittest
import importlib.util
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import Mock, patch

from bson import ObjectId
from test_regressions import RegressionFixture, db
from src.config.config import Config
from src.email_module.email_service import EmailService
from src.invite_module.invite import Invite
from src.invite_module import invitation_notifications as notifications
from src.league_module.league_member import LeagueMember
from src.league_module.race import Race
from src.league_module.race_result import RaceResult
from src.league_module.team import Team


class ParticipationTests(RegressionFixture, unittest.TestCase):
    def setUp(self):
        super().setUp()
        for user in (self.owner, self.driver, self.other):
            user.email = user.email.replace('.test', '.com')
            user.update()
        EmailService.reset_mock()
        EmailService.send_custom_email.reset_mock(return_value=True, side_effect=True)

    def creation_payload(self, **changes):
        payload = {
            'name': 'Managed league', 'public': False, 'creatorParticipates': False,
            'max_players': 1, 'pointSystem': {'1': 25, '2': 18},
            'calendar': [{'track': 'Monza', 'date': (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()}],
            'invites': [self.driver.email],
        }
        payload.update(changes)
        return payload

    def create(self, **changes):
        response = self.client.post('/api/v1/leagues', headers=self.headers, json=self.creation_payload(**changes))
        self.assertEqual(response.status_code, 201, response.get_data(as_text=True))
        return response.json

    def accept(self, user, invite):
        self.actor = user
        return self.client.post(f'/api/v1/invites/{invite._id}/accept', headers=self.headers,
                                json={'league_user_name': user.name})

    def test_nonparticipating_owner_retains_identity_management_and_private_access(self):
        body = self.create(owner=self.driver.email, admins=[self.driver.email], participants=[self.driver.email])
        league_id = body['_id']
        self.assertEqual(body['owner'], self.owner.email)
        self.assertEqual(body['admins'], [self.owner.email])
        self.assertFalse(body['creatorParticipates'])
        self.assertEqual(body['participants'], [])
        self.assertEqual(body['participantsCount'], 0)
        self.assertEqual(body['standings']['overall'], {})
        self.assertEqual(LeagueMember.get_member_count(league_id), 1)
        self.assertEqual(LeagueMember.get_participant_count(league_id), 0)
        owner = LeagueMember.get_member(league_id, str(self.owner._id))
        self.assertEqual(owner.role, 'owner')
        self.assertFalse(owner.is_participating)
        for path in self.league_read_urls(league_id):
            expected = 404 if path.endswith('/standings/' + self.owner.email) else 200
            self.assertEqual(self.client.get(path, headers=self.headers).status_code, expected)
        mine = self.client.get('/api/v1/leagues/my', headers=self.headers).json[0]
        self.assertFalse(mine['isParticipating'])
        self.assertIsNone(mine['position'])
        self.assertEqual(self.client.put(f'/api/v1/leagues/{league_id}', headers=self.headers,
            json={'name': 'Still managed'}).status_code, 200)

    def test_creation_saves_pending_invitations_without_membership_or_inline_email(self):
        body = self.create(invites=['  DRIVER@EXAMPLE.COM ', self.driver.email, self.other.email])
        self.assertEqual(db.invites.count_documents({}), 2)
        self.assertEqual(db.league_members.count_documents({}), 1)
        self.assertEqual({doc['email_status'] for doc in db.invites.find({})}, {'pending'})
        self.assertFalse(LeagueMember.is_member(body['_id'], str(self.driver._id)))
        EmailService.send_custom_email.assert_not_called()
        sent = self.client.get('/api/v1/invites/sent', headers=self.headers,
                               query_string={'league_id': body['_id']})
        self.assertEqual(sent.status_code, 200)
        self.assertEqual({invite['email_status'] for invite in sent.json}, {'pending'})
        self.actor = self.driver
        self.assertEqual(self.client.get('/api/v1/invites/sent', headers=self.headers,
                         query_string={'league_id': body['_id']}).status_code, 403)

    def test_participating_and_legacy_members_keep_existing_driver_behavior(self):
        body = self.create(creatorParticipates=True, invites=[])
        self.assertEqual(body['participants'][0]['email'], self.owner.email)
        self.assertEqual(body['participantsCount'], 1)
        db.league_members.update_many({}, {'$unset': {'is_participating': ''}})
        loaded = self.client.get('/api/v1/leagues/' + body['_id'], headers=self.headers).json
        self.assertTrue(loaded['creatorParticipates'])
        self.assertEqual(loaded['participantsCount'], 1)
        self.assertTrue(LeagueMember.is_participant(body['_id'], str(self.owner._id)))

    def test_all_creation_inputs_are_validated_before_any_write(self):
        for changes in ({'creatorParticipates': 'false'}, {'public': 'false'}, {'max_players': 0},
                        {'invites': ['not-an-email']}, {'invites': [None]},
                        {'invites': [self.owner.email]}, {'calendar': 'invalid'},
                        {'calendar': [{'track': 'Monza', 'date': 'bad-date'}]},
                        {'calendar': self.creation_payload()['calendar'] + [{'date': '2026-10-20'}]}):
            with self.subTest(changes=changes):
                response = self.client.post('/api/v1/leagues', headers=self.headers,
                                             json=self.creation_payload(**changes))
                self.assertEqual(response.status_code, 400)
                for name in ('leagues', 'league_members', 'races', 'invites'):
                    self.assertEqual(db[name].count_documents({}), 0)
        EmailService.send_custom_email.assert_not_called()

    def test_failed_creation_rolls_back_league_owner_races_and_delivery_work(self):
        original = Invite.save
        count = 0
        def fail_second(invite, session=None):
            nonlocal count
            count += 1
            if count == 2:
                raise RuntimeError('Simulated write failure')
            return original(invite, session=session)
        with patch.object(Invite, 'save', autospec=True, side_effect=fail_second):
            with self.assertRaises(RuntimeError):
                self.client.post('/api/v1/leagues', headers=self.headers,
                    json=self.creation_payload(invites=[self.driver.email, self.other.email]))
        for name in ('leagues', 'league_members', 'races', 'invites'):
            self.assertEqual(db[name].count_documents({}), 0)
        EmailService.send_custom_email.assert_not_called()

    def test_pending_invitations_do_not_reserve_slots_and_acceptance_checks_driver_capacity(self):
        body = self.create(invites=[self.driver.email, self.other.email])
        first = Invite.get_pending_by_email(self.driver.email)[0]
        second = Invite.get_pending_by_email(self.other.email)[0]
        self.assertEqual(self.accept(self.driver, first).status_code, 200)
        self.assertTrue(LeagueMember.is_participant(body['_id'], str(self.driver._id)))
        rejected = self.accept(self.other, second)
        self.assertEqual(rejected.status_code, 400)
        self.assertIn('full', rejected.json['message'].lower())
        self.assertEqual(Invite.get_by_id(str(second._id)).status, 'pending')
        self.assertFalse(LeagueMember.is_member(body['_id'], str(self.other._id)))
        self.assertEqual(LeagueMember.get_participant_count(body['_id']), 1)

    def test_failed_acceptance_does_not_strand_a_joined_member(self):
        body = self.create()
        invite = Invite.get_pending_by_email(self.driver.email)[0]
        with patch.object(Invite, 'update', side_effect=RuntimeError('Simulated status failure')):
            self.assertEqual(self.accept(self.driver, invite).status_code, 400)
        self.assertFalse(LeagueMember.is_member(body['_id'], str(self.driver._id)))
        self.assertEqual(Invite.get_by_id(str(invite._id)).status, 'pending')

    def test_public_joins_use_driver_capacity_and_nonparticipant_owner_keeps_access(self):
        body = self.create(public=True, invites=[])
        self.actor = self.driver
        self.assertEqual(self.client.post(f"/api/v1/leagues/{body['_id']}/join", headers=self.headers).status_code, 200)
        self.actor = self.other
        self.assertEqual(self.client.post(f"/api/v1/leagues/{body['_id']}/join", headers=self.headers).status_code, 400)
        self.actor = self.owner
        summary = self.client.get('/api/v1/leagues/public').json[0]
        self.assertEqual(summary['participantsCount'], 1)
        self.assertEqual(self.client.get(f"/api/v1/leagues/{body['_id']}", headers=self.headers).status_code, 200)

    def test_owner_can_correct_participation_without_losing_membership(self):
        body = self.create(invites=[])
        path = '/api/v1/leagues/' + body['_id']
        enabled = self.client.put(path, headers=self.headers, json={'creatorParticipates': True})
        self.assertEqual(enabled.status_code, 200)
        self.assertEqual(enabled.json['participantsCount'], 1)
        disabled = self.client.put(path, headers=self.headers, json={'creatorParticipates': False})
        self.assertEqual(disabled.status_code, 200)
        self.assertEqual(disabled.json['participantsCount'], 0)
        self.assertTrue(LeagueMember.is_admin_or_owner(body['_id'], str(self.owner._id)))

    def test_owner_cannot_enter_a_full_roster_or_be_changed_by_an_admin(self):
        body = self.create()
        invite = Invite.get_pending_by_email(self.driver.email)[0]
        self.assertEqual(self.accept(self.driver, invite).status_code, 200)
        LeagueMember.update_role(body['_id'], str(self.driver._id), 'admin')
        path = '/api/v1/leagues/' + body['_id']
        self.assertEqual(self.client.put(path, headers=self.headers, json={'creatorParticipates': True}).status_code, 403)
        self.actor = self.owner
        self.assertEqual(self.client.put(path, headers=self.headers, json={'creatorParticipates': True}).status_code, 400)
        self.assertFalse(LeagueMember.is_participant(body['_id'], str(self.owner._id)))
        expanded = self.client.put(path, headers=self.headers, json={'creatorParticipates': True, 'max_players': 2})
        self.assertEqual(expanded.status_code, 200)
        self.assertEqual(expanded.json['participantsCount'], 2)

    def test_nonparticipant_owner_can_manage_results_and_teams_but_cannot_race(self):
        body = self.create()
        self.assertEqual(self.accept(self.driver, Invite.get_pending_by_email(self.driver.email)[0]).status_code, 200)
        self.actor = self.owner
        base = '/api/v1/leagues/' + body['_id']
        results = base + '/races/' + body['calendar'][0]['_id'] + '/results'
        self.assertEqual(self.client.post(results, headers=self.headers,
                         json={self.driver.email: {'position': 1}}).status_code, 200)
        self.assertEqual(self.client.post(results, headers=self.headers,
                         json={self.owner.email: {'position': 1}}).status_code, 400)
        self.assertEqual(db.race_results.count_documents({}), 1)
        self.assertEqual(self.client.post(base + '/teams', headers=self.headers,
                         json={'Drivers': [self.driver.email]}).status_code, 200)
        self.assertEqual(self.client.post(base + '/teams', headers=self.headers,
                         json={'Owner': [self.owner.email]}).status_code, 400)
        loaded = self.client.get(base, headers=self.headers).json
        self.assertNotIn(self.owner.email, loaded['standings']['overall'])
        self.assertEqual(loaded['standings']['overall'][self.driver.email]['points'], 25)

    def test_opting_out_does_not_hide_recorded_results_or_leave_an_ineligible_team_member(self):
        body = self.create(creatorParticipates=True, invites=[])
        base = '/api/v1/leagues/' + body['_id']
        self.assertEqual(self.client.post(base + '/teams', headers=self.headers,
                         json={'Owner': [self.owner.email]}).status_code, 200)
        response = self.client.put(base, headers=self.headers, json={'creatorParticipates': False})
        self.assertEqual(response.status_code, 400)
        self.assertTrue(LeagueMember.is_participant(body['_id'], str(self.owner._id)))
        db.teams.delete_many({})
        self.assertEqual(self.client.post(base + '/races/' + body['calendar'][0]['_id'] + '/results',
                         headers=self.headers, json={self.owner.email: {'position': 1}}).status_code, 200)
        self.assertEqual(self.client.put(base, headers=self.headers, json={'creatorParticipates': False}).status_code, 400)
        self.assertEqual(db.race_results.count_documents({}), 1)

    def test_email_casing_is_consistent_for_pending_lookup_and_acceptance(self):
        body = self.create()
        self.driver.email = self.driver.email.upper()
        self.driver.update()
        self.actor = self.driver
        pending = self.client.get('/api/v1/invites/my', headers=self.headers)
        self.assertEqual(len(pending.json), 1)
        invite = Invite.get_by_id(pending.json[0]['_id'])
        self.assertEqual(self.accept(self.driver, invite).status_code, 200)
        self.assertTrue(LeagueMember.is_member(body['_id'], str(self.driver._id)))

    def test_invitation_batch_conflict_does_not_partially_save_or_send(self):
        body = self.create()
        response = self.client.post('/api/v1/invites', headers=self.headers,
            json={'league_id': body['_id'], 'emails': [self.other.email, self.driver.email]})
        self.assertEqual(response.status_code, 409)
        self.assertEqual(db.invites.count_documents({}), 1)
        EmailService.send_custom_email.assert_not_called()

    def test_notifications_use_leases_and_send_only_after_creation_commit(self):
        body = self.create()
        claim = notifications.claim_next()
        self.assertIsNotNone(claim)
        self.assertIsNone(notifications.claim_next())
        self.assertEqual(notifications.deliver_claimed(claim), 'sent')
        EmailService.send_custom_email.assert_called_once()
        self.assertEqual(EmailService.send_custom_email.call_args.kwargs['url'], Config.FRONTEND_URL + '/leagues')
        invite = Invite.get_pending_by_email(self.driver.email)[0]
        self.assertEqual(invite.email_status, 'sent')
        self.assertEqual(notifications.process_pending(), 0)
        self.assertFalse(LeagueMember.is_member(body['_id'], str(self.driver._id)))

    def test_notification_failure_preserves_invite_and_allows_owner_retry(self):
        body = self.create()
        invite = Invite.get_pending_by_email(self.driver.email)[0]
        with patch.object(EmailService, 'send_custom_email', return_value=None):
            self.assertEqual(notifications.process_pending(), 1)
        self.assertEqual(Invite.get_by_id(str(invite._id)).email_status, 'failed')
        self.assertEqual(notifications.process_pending(), 0)  # Backoff, not a tight retry loop.
        self.assertEqual(db.leagues.count_documents({}), 1)
        self.actor = self.driver
        path = f'/api/v1/invites/{invite._id}/retry-email'
        self.assertEqual(self.client.post(path, headers=self.headers).status_code, 403)
        self.actor = self.owner
        self.assertEqual(self.client.post(path, headers=self.headers).status_code, 200)
        self.assertEqual(Invite.get_by_id(str(invite._id)).email_status, 'pending')
        self.assertEqual(notifications.process_pending(), 1)
        self.assertEqual(Invite.get_by_id(str(invite._id)).email_status, 'sent')
        self.assertEqual(LeagueMember.get_participant_count(body['_id']), 0)

    def test_automatic_retries_are_bounded_and_expired_claims_recover(self):
        self.create()
        claim = notifications.claim_next()
        db.invites.update_one({'_id': claim['_id']}, {'$set': {
            'email_lock_until': datetime.now(timezone.utc) - timedelta(seconds=1)}})
        recovered = notifications.claim_next()
        self.assertIsNotNone(recovered)
        self.assertNotEqual(claim['email_claim_token'], recovered['email_claim_token'])
        self.assertEqual(notifications.deliver_claimed(claim), 'cancelled')
        EmailService.send_custom_email.assert_not_called()
        with patch.object(EmailService, 'send_custom_email', return_value=None):
            notifications.deliver_claimed(recovered)
            for _ in range(8):
                db.invites.update_one({'_id': claim['_id']}, {'$set': {
                    'email_retry_at': datetime.now(timezone.utc) - timedelta(seconds=1)}})
                notifications.process_pending()
        saved = Invite.get_by_id(str(claim['_id']))
        self.assertEqual(saved.email_attempts, notifications.MAX_ATTEMPTS)
        self.assertEqual(saved.email_status, 'failed')
        self.assertIsNone(notifications.claim_next())

    def test_notifications_skip_handled_invites_deleted_leagues_and_legacy_unknown_delivery(self):
        body = self.create()
        invite = Invite.get_pending_by_email(self.driver.email)[0]
        self.assertEqual(self.accept(self.driver, invite).status_code, 200)
        self.assertEqual(notifications.process_pending(), 0)
        self.actor = self.owner
        legacy = Invite(ObjectId(body['_id']), str(self.owner._id), self.other.email)
        legacy.save()
        db.invites.update_one({'_id': legacy._id}, {'$unset': {'email_status': '', 'email_attempts': ''}})
        self.assertEqual(notifications.process_pending(), 0)
        self.assertEqual(Invite.get_by_id(str(legacy._id)).email_status, 'unknown')
        self.assertEqual(self.client.post(f'/api/v1/invites/{legacy._id}/retry-email', headers=self.headers).status_code, 200)
        db.leagues.update_one({'_id': ObjectId(body['_id'])}, {'$set': {'deleted_at': datetime.now(timezone.utc)}})
        self.assertEqual(notifications.process_pending(), 1)
        self.assertEqual(Invite.get_by_id(str(legacy._id)).email_status, 'cancelled')
        EmailService.send_custom_email.assert_not_called()

    def test_live_claim_and_accepted_invite_cannot_be_requeued(self):
        self.create()
        invite = Invite.get_pending_by_email(self.driver.email)[0]
        notifications.claim_next()
        path = f'/api/v1/invites/{invite._id}/retry-email'
        self.assertEqual(self.client.post(path, headers=self.headers).status_code, 400)
        self.assertEqual(self.accept(self.driver, invite).status_code, 200)
        self.actor = self.owner
        self.assertEqual(self.client.post(path, headers=self.headers).status_code, 400)

    def test_stale_decline_or_cancel_cannot_overwrite_acceptance(self):
        self.create()
        invite = Invite.get_pending_by_email(self.driver.email)[0]
        original_read = Invite.get_by_id
        for action, actor in [('decline', self.driver), ('', self.owner)]:
            with self.subTest(action=action or 'cancel'):
                db.invites.update_one({'_id': invite._id}, {'$set': {'status': 'pending'}})
                def read_then_accept(invite_id):
                    pending = original_read(invite_id)
                    db.invites.update_one({'_id': invite._id}, {'$set': {'status': 'accepted'}})
                    return pending
                self.actor = actor
                path = f'/api/v1/invites/{invite._id}' + ('/' + action if action else '')
                with patch.object(Invite, 'get_by_id', side_effect=read_then_accept):
                    response = (self.client.post(path, headers=self.headers) if action else
                                self.client.delete(path, headers=self.headers))
                self.assertEqual(response.status_code, 400)
                self.assertEqual(original_read(str(invite._id)).status, 'accepted')

    def test_result_commit_rechecks_participation_and_preserves_previous_results(self):
        league, race = self.make_league()
        path = f'/api/v1/leagues/{league._id}/races/{race._id}/results'
        self.assertEqual(self.client.post(path, headers=self.headers,
                         json={self.driver.email: {'position': 1}}).status_code, 200)
        replace = RaceResult.replace_by_race
        def opt_out_before_commit(*args):
            db.league_members.update_one({'league_id': league._id, 'user_id': str(self.owner._id)},
                                        {'$set': {'is_participating': False}})
            return replace(*args)
        with patch.object(RaceResult, 'replace_by_race', side_effect=opt_out_before_commit):
            self.assertEqual(self.client.post(path, headers=self.headers,
                             json={self.owner.email: {'position': 1}}).status_code, 400)
        self.assertEqual([result.user_id for result in RaceResult.get_by_race(str(race._id))],
                         [str(self.driver._id)])

    def test_team_commit_rechecks_participation_and_preserves_previous_teams(self):
        league, _ = self.make_league()
        path = f'/api/v1/leagues/{league._id}/teams'
        self.assertEqual(self.client.post(path, headers=self.headers,
                         json={'Drivers': [self.driver.email]}).status_code, 200)
        replace = Team.set_teams_for_league
        def opt_out_before_commit(*args):
            db.league_members.update_one({'league_id': league._id, 'user_id': str(self.owner._id)},
                                        {'$set': {'is_participating': False}})
            return replace(*args)
        with patch.object(Team, 'set_teams_for_league', side_effect=opt_out_before_commit):
            self.assertEqual(self.client.post(path, headers=self.headers,
                             json={'Owner': [self.owner.email]}).status_code, 400)
        self.assertEqual(Team.get_by_league(str(league._id))[0].member_ids, [str(self.driver._id)])

    def test_real_mail_service_returns_provider_outcome_without_leaking_errors(self):
        # Load the implementation with a mocked client; the API fixtures mock this module.
        provider = Mock()
        accepted = object()
        provider.emails.send.return_value = accepted
        source = Path(__file__).resolve().parents[1] / 'src/email_module/email_service.py'
        spec = importlib.util.spec_from_file_location('isolated_email_service', source)
        service = importlib.util.module_from_spec(spec)
        with patch.multiple(Config, MAILER_SENDER_API_KEY='test-key',
                            SENDER_EMAIL='sender@example.com', SENDER_NAME='Test sender',
                            EMAIL_TEMPLATE_ID='test-template', create=True), \
                patch('mailersend.MailerSendClient', return_value=provider) as client:
            spec.loader.exec_module(service)
            arguments = {'to_email': self.driver.email, 'name': self.driver.name, 'subject': 'Invitation',
                         'message_top': 'Join us', 'message_bottom': 'Sign in first',
                         'button_name': 'View invitation', 'url': 'https://frontend.example.test/leagues'}
            self.assertIs(service.EmailService.send_custom_email(**arguments), accepted)
            client.assert_called_once_with(api_key='test-key', timeout=10, max_retries=0)
            provider.emails.send.side_effect = RuntimeError('Sensitive provider diagnostic')
            with self.assertLogs(service.logger, level='WARNING') as logged:
                self.assertIsNone(service.EmailService.send_custom_email(**arguments))
            self.assertNotIn('Sensitive provider diagnostic', str(logged.output))

    def test_notification_links_require_a_configured_frontend_and_worker_starts_after_fork(self):
        for invalid in (None, '', 'ftp://example.com', 'https://user:password@example.com',
                        'https://example.com?', 'https://example.com#', 'https://example.com:bad'):
            with self.subTest(url=invalid), patch.object(Config, 'FRONTEND_URL', invalid):
                with self.assertRaises(ValueError):
                    notifications.invitation_url()
        import app as application
        with patch.object(Config, 'INVITATION_EMAIL_WORKER_ENABLED', True), \
                patch.object(notifications, 'start_delivery_worker') as start:
            response = application.app.test_client().get('/api/v1/check')
            self.assertEqual(response.status_code, 200)
            start.assert_called_once()
