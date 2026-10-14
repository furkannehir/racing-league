"""Remaining audit findings: use isolated data and never contact external providers."""
import json
import os
import types
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from bson import ObjectId
from pymongo.errors import OperationFailure, DuplicateKeyError
from firebase_admin import auth

from test_regressions import RegressionFixture, db
import test_regressions as regressions
from src.config import mongo
from src.league_module.league import League
from src.league_module.league_member import LeagueMember
from src.league_module.league_service import LeagueService
from src.league_module.race import Race
from src.league_module.race_result import RaceResult
from src.league_module.point_system_preset import PointSystemPreset
from src.auth_module.auth_controller import auth_blueprint
from src.auth_module import account_limits as limits
from src.email_module import account_notifications as notifications
from src.email_module.email_service import EmailService
from scripts.migrate_league_schema import migrate
from scripts.start_server import main


class RemainingLeagueTests(RegressionFixture, unittest.TestCase):
    def test_leave_removes_all_current_team_assignments_and_retains_recorded_results(self):
        league, race = self.make_league()
        LeagueService.set_teams(str(league._id), {'Team': [self.driver.email, self.owner.email]})
        # Include a second stale assignment from an older database state.
        db.teams.insert_one({'league_id': league._id, 'name': 'Old Team', 'member_ids': [str(self.driver._id)]})
        LeagueService.submit_race_result(str(league._id), str(race._id), {self.driver.email: {'position': 1}})
        history = list(db.race_results.find({}))
        self.actor = self.driver
        response = self.client.post(f'/api/v1/leagues/{league._id}/leave', headers=self.headers)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(LeagueMember.is_member(str(league._id), str(self.driver._id)))
        self.assertEqual(db.teams.count_documents({'member_ids': str(self.driver._id)}), 0)
        self.assertIsNone(db.teams.find_one({'name': 'Old Team'}))
        self.assertEqual(list(db.race_results.find({})), history)
        self.assertEqual(LeagueService.get_league_standings(str(league._id))[0]['user_id'], str(self.driver._id))
        self.actor = self.owner
        self.assertEqual(self.client.post(f'/api/v1/leagues/{league._id}/teams', headers=self.headers,
                                         json={'Team': [self.owner.email]}).status_code, 200)

    def test_failed_leave_rolls_back_membership_and_team_updates(self):
        league, _ = self.make_league()
        LeagueService.set_teams(str(league._id), {'Team': [self.driver.email]})
        before = list(db.teams.find({}))
        collection = db.league_members
        self.actor = self.driver
        with patch.object(collection, 'delete_one', side_effect=OperationFailure('leave write failed')):
            response = self.client.post(f'/api/v1/leagues/{league._id}/leave', headers=self.headers)
        self.assertEqual(response.status_code, 503)
        self.assertTrue(LeagueMember.is_member(str(league._id), str(self.driver._id)))
        self.assertEqual(list(db.teams.find({})), before)
        self.assertNotIn('write failed', response.get_data(as_text=True))

    def test_owner_cannot_leave_and_invalid_or_deleted_leagues_are_rejected(self):
        league, _ = self.make_league()
        self.assertEqual(self.client.post(f'/api/v1/leagues/{league._id}/leave', headers=self.headers).status_code, 400)
        with self.assertRaisesRegex(ValueError, 'owner'):
            LeagueMember.remove(str(league._id), str(self.owner._id))
        self.assertEqual(self.client.post('/api/v1/leagues/not-an-id/leave', headers=self.headers).status_code, 404)
        League.soft_delete(str(league._id))
        self.assertEqual(self.client.post(f'/api/v1/leagues/{league._id}/leave', headers=self.headers).status_code, 404)

    def test_tied_driver_ranks_match_detail_standings_and_my_leagues(self):
        league, race = self.make_league()
        # Same points, different wins: insertion order and email spelling must not decide the rank.
        for user, position, points in ((self.owner, 2, 25), (self.driver, 1, 25)):
            RaceResult(race._id, league._id, str(user._id), position=position, points=points).save()
        detail = LeagueService.get_league_detail(str(league._id))
        standings = LeagueService.get_league_standings(str(league._id))
        self.assertEqual(standings[0]['user_id'], str(self.driver._id))
        self.assertEqual(detail['standings']['overall'][self.driver.email]['position'], 1)
        self.assertEqual(detail['standings']['overall'][self.owner.email]['position'], 2)
        self.assertEqual(LeagueService.get_my_leagues(str(self.driver._id))[0]['position'], 1)
        self.assertEqual(LeagueService.get_my_leagues(str(self.owner._id))[0]['position'], 2)

    def test_exact_ties_and_zero_result_drivers_have_stable_backend_positions(self):
        league, _ = self.make_league()
        expected = sorted([str(self.owner._id), str(self.driver._id)])
        for _ in range(2):
            standings = RaceResult.get_standings(str(league._id))
            self.assertEqual([row['user_id'] for row in standings], expected)
            self.assertEqual([row['position'] for row in standings], [1, 2])
        db.league_members.update_one({'user_id': expected[0]}, {'$set': {'is_participating': False}})
        self.assertEqual(RaceResult.get_standings(str(league._id))[0]['position'], 1)

    def test_team_ranks_are_shared_by_detail_team_endpoint_and_standings(self):
        league, race = self.make_league()
        LeagueService.set_teams(str(league._id), {'Earlier Team': [self.owner.email], 'Winner Team': [self.driver.email]})
        for user, position in ((self.owner, 2), (self.driver, 1)):
            RaceResult(race._id, league._id, str(user._id), position=position, points=25).save()
        teams = LeagueService.get_teams(str(league._id))
        detail = LeagueService.get_league_detail(str(league._id))
        ranking = LeagueService.get_team_standings(str(league._id))
        self.assertEqual(teams['Winner Team']['position'], 1)
        self.assertEqual(detail['teams']['Winner Team']['position'], 1)
        self.assertEqual(ranking[0]['name'], 'Winner Team')

    def test_discovery_is_bounded_paged_and_private_data_stays_hidden(self):
        for index in range(13):
            self.make_league()
        private, _ = self.make_league()
        db.leagues.update_one({'_id': private._id}, {'$set': {'public': False}})
        deleted, _ = self.make_league()
        League.soft_delete(str(deleted._id))
        pages = []
        for page in (1, 2, 3):
            response = self.client.get(f'/api/v1/leagues/discovery?page={page}&page_size=5')
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json['total'], 13)
            self.assertEqual(response.json['total_pages'], 3)
            self.assertLessEqual(len(response.json['leagues']), 5)
            pages.extend(response.json['leagues'])
        self.assertEqual(len({league['_id'] for league in pages}), 13)
        for body in pages:
            self.assert_summary_shape(body)
            self.assertEqual(body['participantsCount'], 2)
            self.assertEqual(body['next_race']['track'], 'Monza')
        for path in ('all', 'public'):
            response = self.client.get('/api/v1/leagues/' + path)
            self.assertEqual(len(response.json), 10)
            self.assertEqual(response.headers['X-Total-Count'], '13')

    def test_discovery_search_is_literal_and_validates_page_size(self):
        league, _ = self.make_league()
        self.make_league()
        db.leagues.update_one({'_id': league._id}, {'$set': {'name': 'A literal .* [league]'}})
        response = self.client.get('/api/v1/leagues/discovery', query_string={'q': '.* [LEAGUE]'})
        self.assertEqual(response.json['total'], 1)
        self.assertEqual(response.json['leagues'][0]['_id'], str(league._id))
        for query in ({'page': 0}, {'page': -1}, {'page': 'nope'}, {'page_size': 0}, {'page_size': 51}, {'q': 'x' * 101}):
            self.assertEqual(self.client.get('/api/v1/leagues/discovery', query_string=query).status_code, 400)
        self.assertEqual(self.client.get('/api/v1/leagues/0/10', headers=self.headers).status_code, 400)
        self.assertEqual(self.client.get('/api/v1/leagues/discovery?page=9999999999').json['leagues'], [])

    def test_discovery_batches_related_queries_instead_of_querying_every_league(self):
        for _ in range(8):
            self.make_league()
        with patch.object(LeagueMember, 'get_participant_count', side_effect=AssertionError('No per-league counts')), \
                patch.object(Race, 'get_next_race', side_effect=AssertionError('No per-league races')), \
                patch.object(db.league_members, 'aggregate', wraps=db.league_members.aggregate) as counts, \
                patch.object(db.races, 'aggregate', wraps=db.races.aggregate) as races:
            response = self.client.get('/api/v1/leagues/discovery?page_size=8')
        self.assertEqual(response.status_code, 200)
        counts.assert_called_once()
        races.assert_called_once()

    def test_f1_default_is_current_and_obsolete_default_is_retained_but_retired(self):
        league, race = self.make_league()
        LeagueService.submit_race_result(str(league._id), str(race._id), {self.owner.email: {'position': 1, 'fastestLap': True}})
        before = list(db.race_results.find({}))
        legacy = PointSystemPreset('F1 Current (2010\u2013Present)', {
            '1': 25, '2': 18, '3': 15, '4': 12, '5': 10, '6': 8, '7': 6, '8': 4, '9': 2, '10': 1},
            fastest_lap_point=1, description='Current Formula 1 point system used since 2010')
        legacy.save()
        PointSystemPreset.seed_defaults()
        PointSystemPreset.seed_defaults()
        self.assertFalse(PointSystemPreset.get_by_id(str(legacy._id)).active)
        current = next(preset for preset in PointSystemPreset.get_active() if preset.name.startswith('F1 Current'))
        self.assertEqual(current.fastest_lap_point, 0)
        self.assertEqual(current.points['1'], 25)
        self.assertEqual(League.get_by_id(str(league._id)).fastest_lap_point, 1)
        self.assertEqual(list(db.race_results.find({})), before)
        self.assertEqual(len(PointSystemPreset.get_active()), 4)

    def test_f1_seeding_preserves_customized_old_records(self):
        custom = PointSystemPreset('F1 Current (2010\u2013Present)', {'1': 30}, fastest_lap_point=5,
                                   description='Owner customized rules')
        custom.save()
        PointSystemPreset.seed_defaults()
        saved = PointSystemPreset.get_by_id(str(custom._id))
        self.assertTrue(saved.active)
        self.assertEqual(saved.fastest_lap_point, 5)


class ArchiveAndPortTests(RegressionFixture, unittest.TestCase):
    legacy_league = regressions.MigrationTests.legacy_league

    def test_archived_corrupt_league_and_invitations_are_retained_without_blocking_startup(self):
        legacy, _ = self.legacy_league()
        db.leagues.update_one({'_id': legacy['_id']}, {'$set': {
            'deleted_at': datetime.now(timezone.utc), 'owner': 'missing@example.test', 'calendar': 'broken'}})
        db.invites.update_many({}, {'$set': {'inviter': 'missing@example.test'}})
        db.invites.insert_many([
            {'status': 'declined', 'league': 'broken', 'inviter': None},
            {'deleted_at': datetime.now(timezone.utc), 'league': None},
        ])
        before = {name: list(db[name].find({})) for name in ('leagues', 'invites')}
        summary = migrate(db, apply=True)
        self.assertEqual(summary['operations'], 0)
        self.assertEqual(summary['skipped_archived_leagues'], 1)
        self.assertEqual(summary['skipped_archived_invites'], 3)
        mongo.assert_schema_ready()
        with patch('scripts.start_server.os.execvp') as launch:
            self.assertEqual(main(['gunicorn']), 0)
        launch.assert_called_once()
        for name in before:
            self.assertEqual(list(db[name].find({})), before[name])

    def test_valid_live_data_is_migrated_while_bad_archives_stay_stored(self):
        active, _ = self.legacy_league()
        archive, _ = self.legacy_league()
        db.leagues.update_one({'_id': archive['_id']}, {'$set': {'deleted_at': datetime.now(timezone.utc), 'owner': 'missing'}})
        self.assertGreater(migrate(db, apply=True)['operations'], 0)
        mongo.assert_schema_ready()
        self.assertIn('owner_id', db.leagues.find_one({'_id': active['_id']}))
        self.assertNotIn('owner_id', db.leagues.find_one({'_id': archive['_id']}))
        self.assertEqual(migrate(db, apply=True)['operations'], 0)

    def test_malformed_live_invites_and_reactivated_bad_archives_still_fail_preflight(self):
        legacy, _ = self.legacy_league()
        for reference in ('not-a-league', str(ObjectId())):
            db.invites.update_many({}, {'$set': {'league': reference}})
            with self.assertRaises(ValueError):
                migrate(db, apply=True)
            self.assertNotIn('owner_id', db.leagues.find_one({'_id': legacy['_id']}))
        db.invites.delete_many({})
        db.leagues.update_one({'_id': legacy['_id']}, {'$set': {'owner': 'missing', 'deleted_at': None}})
        with self.assertRaises(ValueError):
            migrate(db, apply=True)
        with self.assertRaises(RuntimeError):
            mongo.assert_schema_ready()

    def test_actual_docker_command_uses_render_port_and_keeps_worker_timeout(self):
        line = next(line for line in Path('Dockerfile').read_text().splitlines() if line.startswith('CMD '))
        command = json.loads(line[4:])
        with patch.dict(os.environ, {'PORT': '10000'}), patch('scripts.start_server.prepare_database'), \
                patch('scripts.start_server.os.execvp') as launch:
            self.assertEqual(main(command), 0)
        args = launch.call_args.args[1]
        self.assertEqual(args[args.index('--bind') + 1], '0.0.0.0:10000')
        self.assertEqual(args[args.index('--timeout') + 1], '90')
        self.assertEqual(args[-1], 'app:app')

    def test_invalid_default_port_stops_before_database_preparation_and_custom_command_is_preserved(self):
        for value in ('', 'not-a-port', '0', '65536'):
            with patch.dict(os.environ, {'PORT': value}), patch('scripts.start_server.prepare_database') as prepare, \
                    patch('scripts.start_server.os.execvp') as launch:
                self.assertEqual(main(['gunicorn']), 1)
                prepare.assert_not_called()
                launch.assert_not_called()
        command = ['gunicorn', '--workers', '2', '--bind', '0.0.0.0:9000', 'app:app']
        with patch('scripts.start_server.prepare_database'), patch('scripts.start_server.os.execvp') as launch:
            self.assertEqual(main(command), 0)
        launch.assert_called_once_with('gunicorn', command)


class AccountLimitTests(RegressionFixture, unittest.TestCase):
    def setUp(self):
        super().setUp()
        self.app.register_blueprint(auth_blueprint)
        EmailService.reset_mock()
        for method in (EmailService.send_verification_email, EmailService.send_reset_password_email):
            method.reset_mock(return_value=True, side_effect=True)

    def email_request(self, index, peer='192.0.2.1', path='reset-password', forwarded=None):
        return self.client.post('/api/v1/auth/' + path, json={'email': f'driver{index}@example.com'},
                                environ_overrides={'REMOTE_ADDR': peer}, headers={'X-Forwarded-For': forwarded} if forwarded else {})

    def test_rotating_addresses_and_forwarded_headers_cannot_bypass_peer_limit(self):
        with patch.object(limits.Config, 'ACCOUNT_REQUEST_IP_LIMIT', 2, create=True), \
                patch('firebase_admin.auth.get_user_by_email') as lookup:
            self.assertEqual(self.email_request(0, forwarded='198.51.100.1').status_code, 202)
            self.assertEqual(self.email_request(1, path='verification-email', forwarded='198.51.100.2').status_code, 202)
            result = self.email_request(2, forwarded='198.51.100.3')
            self.assertEqual(result.status_code, 429)
            self.assertGreater(int(result.headers['Retry-After']), 0)
            self.assertEqual(result.headers['Cache-Control'], 'no-store')
            self.assertEqual(db.account_notifications.count_documents({}), 2)
            lookup.assert_not_called()
            registration = self.client.post('/api/v1/auth/register', json={}, environ_overrides={'REMOTE_ADDR': '192.0.2.1'})
            self.assertEqual(registration.status_code, 429)
        self.assertNotIn('192.0.2.1', str(list(db.account_rate_limits.find({}))))

    def test_distributed_peers_share_global_limits_and_refusals_do_not_charge_other_buckets(self):
        with patch.object(limits.Config, 'ACCOUNT_REQUEST_GLOBAL_HOURLY_LIMIT', 2, create=True):
            self.assertEqual(self.email_request(0, '192.0.2.1').status_code, 202)
            self.assertEqual(self.email_request(1, '192.0.2.2').status_code, 202)
            before = list(db.account_rate_limits.find({}))
            self.assertEqual(self.email_request(2, '192.0.2.3').status_code, 429)
            self.assertEqual(list(db.account_rate_limits.find({})), before)
        self.assertEqual(db.account_notifications.count_documents({}), 2)

    def test_ipv6_rotation_within_one_subnet_is_limited_and_window_reopens(self):
        now = datetime.now(timezone.utc).replace(minute=10, second=0, microsecond=0)
        with patch.object(limits.Config, 'ACCOUNT_REQUEST_IP_LIMIT', 1, create=True):
            limits.reserve_request('2001:db8::1', now)
            with self.assertRaises(limits.RateLimited):
                limits.reserve_request('2001:db8::abcd', now + timedelta(seconds=1))
            limits.reserve_request('2001:db8::abcd', now + timedelta(minutes=10))

    def test_trusted_proxy_is_explicit_and_uses_only_the_configured_hop(self):
        with patch.object(limits.Config, 'TRUSTED_PROXY_HOPS', 1, create=True), \
                patch.object(limits.Config, 'ACCOUNT_REQUEST_IP_LIMIT', 1, create=True):
            limits.configure_proxy(self.app)
            self.assertEqual(self.email_request(0, forwarded='203.0.113.1, 198.51.100.4').status_code, 202)
            self.assertEqual(self.email_request(1, forwarded='203.0.113.2, 198.51.100.4').status_code, 429)
            self.assertEqual(self.email_request(2, forwarded='203.0.113.2, 198.51.100.5').status_code, 202)

    def test_delivery_budget_defers_jobs_without_consuming_retry_attempts_and_recovers_next_window(self):
        notifications.request_email('verification', self.owner.email)
        notifications.request_email('verification', self.driver.email)
        with patch.object(limits.Config, 'ACCOUNT_DELIVERY_HOURLY_LIMIT', 1, create=True):
            now = datetime.now(timezone.utc)
            first = notifications.claim_next(now)
            self.assertIsNotNone(first)
            before = list(db.account_notifications.find({}))
            self.assertIsNone(notifications.claim_next(now))
            self.assertEqual(list(db.account_notifications.find({})), before)
            job = notifications.claim_next(now + timedelta(hours=1))
            self.assertIsNotNone(job)
        EmailService.send_verification_email.assert_not_called()

    def test_delivery_budget_covers_missing_accounts_and_failed_provider_attempts(self):
        notifications.request_email('verification', 'missing@example.com')
        notifications.request_email('verification', self.owner.email)
        with patch.object(limits.Config, 'ACCOUNT_DELIVERY_DAILY_LIMIT', 1, create=True), \
                patch('firebase_admin.auth.get_user_by_email', side_effect=auth.UserNotFoundError('missing', None, None)) as lookup:
            self.assertEqual(notifications.process_pending(), 1)
            self.assertEqual(notifications.process_pending(), 0)
            lookup.assert_called_once()
        db.account_rate_limits.delete_many({})
        with patch.object(limits.Config, 'ACCOUNT_DELIVERY_DAILY_LIMIT', 1, create=True), \
                patch('firebase_admin.auth.get_user_by_email', return_value=types.SimpleNamespace(
                    uid='firebase-uid', email=self.owner.email, disabled=False, email_verified=False)), \
                patch.object(EmailService, 'send_verification_email', return_value=False):
            self.assertEqual(notifications.process_pending(), 1)
            db.account_notifications.update_many({'status': 'failed'}, {'$set': {'retry_at': datetime.now(timezone.utc)}})
            self.assertEqual(notifications.process_pending(), 0)

    def test_counter_failure_rolls_back_claim_and_blocks_new_work_without_leaking_details(self):
        notifications.request_email('verification', self.owner.email)
        with patch.object(db.account_rate_limits, 'update_one', side_effect=OperationFailure('secret detail')):
            self.assertIsNone(notifications.claim_next())
            response = self.email_request(1)
        self.assertEqual(response.status_code, 503)
        self.assertNotIn('secret', response.get_data(as_text=True))
        self.assertEqual(db.account_notifications.find_one({})['attempts'], 0)
        self.assertEqual(db.account_notifications.find_one({})['status'], 'pending')
        EmailService.send_verification_email.assert_not_called()

    def test_zero_budget_disables_requests_and_empty_worker_polls_do_not_charge_budget(self):
        self.assertIsNone(notifications.claim_next())
        self.assertEqual(db.account_rate_limits.count_documents({}), 0)
        with patch.object(limits.Config, 'ACCOUNT_REQUEST_GLOBAL_DAILY_LIMIT', 0, create=True):
            self.assertEqual(self.email_request(1).status_code, 429)
        self.assertEqual(db.account_notifications.count_documents({}), 0)

    def test_new_counter_collision_rechecks_before_admitting_request(self):
        original = mongo.run_transaction
        attempts = 0

        def collide_once(callback):
            nonlocal attempts
            attempts += 1
            if attempts == 1:
                raise DuplicateKeyError('bucket collision')
            return original(callback)

        with patch.object(mongo, 'run_transaction', side_effect=collide_once):
            limits.reserve_request('192.0.2.1')
        self.assertEqual(attempts, 2)
        self.assertEqual([record['count'] for record in db.account_rate_limits.find({})], [1, 1, 1])
