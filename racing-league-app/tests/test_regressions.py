"""API and migration regressions, using MongoDB query semantics without external services."""
import copy
import importlib
import os
import sys
import types
import unittest
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import Mock, patch
from urllib.parse import urlparse

import mongomock
from bson import ObjectId
from flask import Flask
from pymongo import MongoClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# Replace configuration and external clients before importing application modules.
test_uri = os.getenv("RACING_LEAGUE_TEST_MONGO_URI")
if test_uri and urlparse(test_uri).hostname not in ("localhost", "127.0.0.1"):
    raise ValueError("Integration tests only accept a local MongoDB URI")
test_db_name = "regression_tests_" + uuid.uuid4().hex
config_module = types.ModuleType("src.config.config")
config_module.Config = type("Config", (), {
    "MONGO_URI": test_uri or "mongodb://localhost", "MONGO_DB_NAME": test_db_name,
    "OPENAI_API_KEY": None, "ORIGINS": ["http://localhost"],
    "init_firebase": staticmethod(lambda: None),
})
sys.modules[config_module.__name__] = config_module
email_module = types.ModuleType("src.email_module.email_service")
email_module.EmailService = Mock()
sys.modules[email_module.__name__] = email_module
mongo_client = MongoClient(test_uri, serverSelectionTimeoutMS=5000) if test_uri else mongomock.MongoClient()
with patch("pymongo.MongoClient", return_value=mongo_client):
    from src.config import mongo
from src.invite_module.invite import Invite
from src.league_module.league import League
from src.league_module.league_member import LeagueMember
from src.league_module.league_service import LeagueService
from src.league_module import race_result, team
from src.league_module.race import Race
from src.user_module.user import User
from scripts.migrate_league_schema import build_plan, migrate

db = mongo.db


def memory_transaction(callback, database=None):
    """Test the write boundary and rollback behavior; real-driver test lives separately."""
    database = db if database is None else database
    snapshot = {name: copy.deepcopy(list(database[name].find({})))
                for name in database.list_collection_names()}
    try:
        return callback(None)
    except Exception:
        for name in database.list_collection_names():
            database[name].delete_many({})
        for name, docs in snapshot.items():
            for doc in docs:
                database[name].insert_one(doc)
        raise


class RegressionFixture:
    def setUp(self):
        for name in db.list_collection_names():
            db.drop_collection(name)
        mongo.ensure_indexes()
        self.owner = User(None, "Owner", "owner@example.test")
        self.owner.save()
        self.driver = User(None, "Driver", "driver@example.test")
        self.driver.save()
        self.other = User("legacy-firebase-id", "Other", "other@example.test")
        self.other.save()
        self.actor = self.owner
        self.patches = [
            patch("firebase_admin.auth.verify_id_token", return_value={"user_id": "firebase-uid"}),
            patch("firebase_admin.auth.get_user", side_effect=lambda uid: types.SimpleNamespace(email=self.actor.email)),
        ]
        if not test_uri:
            self.patches.extend([
                patch.object(race_result, "run_transaction", side_effect=memory_transaction),
                patch.object(team, "run_transaction", side_effect=memory_transaction),
                patch.object(mongo, "run_transaction", side_effect=memory_transaction),
            ])
        for p in self.patches:
            p.start()
            self.addCleanup(p.stop)
        from src.league_module.league_controller import league_blueprint
        from src.invite_module.invite_controller import invite_blueprint
        from src.user_module.user_controller import user_blueprint
        self.app = Flask(__name__)
        self.app.config["TESTING"] = True
        for blueprint in (league_blueprint, invite_blueprint, user_blueprint):
            self.app.register_blueprint(blueprint)
        self.client = self.app.test_client()
        self.headers = {"Authorization": "Bearer test"}

    def make_league(self):
        league = LeagueService.create_league({
            "name": "Test League", "public": True, "pointSystem": {"1": 25, "2": 18},
            "fastestLapPoint": 1, "calendar": [{
                "track": "Monza", "date": (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()
            }],
        }, str(self.owner._id))
        LeagueMember(league._id, str(self.driver._id), display_name="Custom Driver").save()
        return league, Race.get_by_league(str(league._id))[0]

    def assert_league_shape(self, body):
        self.assertIsInstance(body, dict)
        for key in ("owner", "calendar", "participants", "standings", "admins", "pointSystem", "fastestLapPoint"):
            self.assertIn(key, body)

class RegressionTests(RegressionFixture, unittest.TestCase):
    def test_user_lookup_supports_objectids_and_legacy_strings(self):
        self.assertEqual(User.get_user_by_id(str(self.owner._id)).email, self.owner.email)
        self.assertEqual(User.get_user_by_id(self.owner._id).email, self.owner.email)
        self.assertEqual(User.get_user_by_id(self.other._id).email, self.other.email)
        self.assertEqual(set(User.get_users_by_ids([str(self.owner._id), self.other._id])),
                         {str(self.owner._id), self.other._id})
        User.delete_user(str(self.driver._id))
        self.assertIsNone(User.get_user_by_id(str(self.driver._id)))

    def test_create_and_update_return_complete_league(self):
        response = self.client.post("/api/v1/leagues", headers=self.headers, json={
            "name": "Created", "public": True, "pointSystem": {"1": 25}, "fastestLapPoint": 1
        })
        self.assertEqual(response.status_code, 201)
        self.assert_league_shape(response.json)
        league_id = response.json["_id"]
        response = self.client.put(f"/api/v1/leagues/{league_id}", headers=self.headers,
                                   json={"name": "Renamed", "max_players": 12, "fastestLapPoint": 2})
        self.assertEqual(response.status_code, 200)
        self.assert_league_shape(response.json)
        self.assertEqual(response.json["owner"], self.owner.email)
        self.assertEqual(response.json["fastestLapPoint"], 2)
        self.assertEqual(response.json["admins"], [self.owner.email])
        self.assertEqual(response.json["participants"][0]["email"], self.owner.email)

    def test_invalid_settings_do_not_change_saved_league(self):
        league, _ = self.make_league()
        for data in ({"name": ""}, {"max_players": -1}, {"max_players": 1}, {"fastestLapPoint": -2}):
            response = self.client.put(f"/api/v1/leagues/{league._id}", headers=self.headers, json=data)
            self.assertEqual(response.status_code, 400)
        self.assertEqual(League.get_by_id(str(league._id)).name, "Test League")

    def test_public_listing_preserves_member_count_and_calendar(self):
        league, _ = self.make_league()
        response = self.client.get("/api/v1/leagues/all")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json[0]["participantsCount"], 2)
        self.assertEqual(response.json[0]["next_race"]["track"], "Monza")
        self.assertEqual(response.json[0]["_id"], str(league._id))

    def test_invites_use_mongo_identity_and_keep_display_details(self):
        league, _ = self.make_league()
        invite = Invite(league._id, str(self.owner._id), self.other.email)
        invite.save()
        sent = self.client.get("/api/v1/invites/sent", headers=self.headers)
        self.assertEqual(sent.json[0]["_id"], str(invite._id))
        self.actor = self.other
        received = self.client.get("/api/v1/invites/my", headers=self.headers)
        self.assertEqual(received.json[0]["inviter"]["email"], self.owner.email)
        self.assertEqual(received.json[0]["league"]["participantsCount"], 2)
        self.assertIn("createdAt", received.json[0])
        accepted = self.client.post(f"/api/v1/invites/{invite._id}/accept", headers=self.headers,
                                    json={"league_user_name": "Invited Driver"})
        self.assertEqual(accepted.status_code, 200)
        self.assertTrue(LeagueMember.is_member(str(league._id), self.other._id))
        self.assertEqual(self.client.get("/api/v1/invites/my", headers=self.headers).json, [])

    def test_full_or_deleted_leagues_reject_invite_acceptance(self):
        league, _ = self.make_league()
        invite = Invite(league._id, str(self.owner._id), self.other.email)
        invite.save()
        self.actor = self.other
        db.leagues.update_one({"_id": league._id}, {"$set": {"max_players": 2}})
        response = self.client.post(f"/api/v1/invites/{invite._id}/accept", headers=self.headers, json={})
        self.assertEqual(response.status_code, 400)
        League.soft_delete(str(league._id))
        response = self.client.post(f"/api/v1/invites/{invite._id}/accept", headers=self.headers, json={})
        self.assertEqual(response.status_code, 400)
        self.assertFalse(LeagueMember.is_member(str(league._id), self.other._id))

    def test_team_emails_are_normalized_and_response_is_dictionary(self):
        league, _ = self.make_league()
        response = self.client.post(f"/api/v1/leagues/{league._id}/teams", headers=self.headers,
                                    json={"Red Bull": [self.owner.email, self.driver.email]})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json["Red Bull"]["members"], [self.owner.email, self.driver.email])
        stored = db.teams.find_one({"league_id": league._id})
        self.assertEqual(stored["member_ids"], [str(self.owner._id), str(self.driver._id)])
        invalid = self.client.post(f"/api/v1/leagues/{league._id}/teams", headers=self.headers,
                                   json={"A": [self.driver.email], "B": [str(self.driver._id)]})
        self.assertEqual(invalid.status_code, 400)
        self.assertEqual(db.teams.find_one({"league_id": league._id}), stored)

    def test_submit_results_returns_league_and_awards_fastest_lap(self):
        league, race = self.make_league()
        response = self.client.post(f"/api/v1/leagues/{league._id}/races/{race._id}/results",
                                    headers=self.headers, json={
            self.owner.email: {"position": 1, "fastestLap": True, "points": 999},
            self.driver.email: {"position": 2, "dnf": True},
        })
        self.assertEqual(response.status_code, 200)
        self.assert_league_shape(response.json)
        self.assertEqual(response.json["standings"]["overall"][self.owner.email]["points"], 26)
        driver = response.json["standings"]["overall"][self.driver.email]
        self.assertEqual((driver["points"], driver["podiums"], driver["dnfs"]), (0, 0, 1))
        self.assertTrue(response.json["standings"]["races"][str(race._id)][self.owner.email]["fastestLap"])
        self.assertEqual(response.json["calendar"][0]["status"], "Completed")

    def test_failed_validation_and_write_preserve_previous_results(self):
        league, race = self.make_league()
        submit = lambda results: LeagueService.submit_race_result(str(league._id), str(race._id), results)
        submit({self.owner.email: {"position": 1}})
        previous = list(db.race_results.find({}))
        for results in (
            {"missing@example.test": {"position": 1}},
            {self.other.email: {"position": 1}},
            {self.owner.email: {"position": 1}, self.driver.email: {"position": 1}},
            {self.owner.email: {"position": 1, "dnf": True, "fastestLap": True}},
        ):
            with self.assertRaises(Exception):
                submit(results)
            self.assertEqual(list(db.race_results.find({})), previous)
        with patch.object(race_result.RaceResult, "bulk_save", side_effect=RuntimeError("write failed")):
            with self.assertRaisesRegex(RuntimeError, "write failed"):
                submit({self.owner.email: {"position": 2}})
        self.assertEqual(list(db.race_results.find({})), previous)
        self.assertEqual(Race.get_by_id(str(race._id)).status, "Completed")

    def test_resubmission_replaces_results_without_double_counting(self):
        league, race = self.make_league()
        for position in (1, 2):
            response = LeagueService.submit_race_result(str(league._id), str(race._id),
                                                        {self.owner.email: {"position": position}})
        self.assertEqual(db.race_results.count_documents({}), 1)
        self.assertEqual(response["standings"]["overall"][self.owner.email]["points"], 18)

    def test_failed_team_replacement_keeps_previous_teams(self):
        league, _ = self.make_league()
        LeagueService.set_teams(str(league._id), {"Original": [self.owner.email]})
        previous = list(db.teams.find({}))
        collection_type = type(db.teams)
        insert_many = collection_type.insert_many

        def fail_team_insert(collection, *args, **kwargs):
            if collection.name == "teams":
                raise RuntimeError("team write failed")
            return insert_many(collection, *args, **kwargs)

        with patch.object(collection_type, "insert_many", fail_team_insert):
            with self.assertRaisesRegex(RuntimeError, "team write failed"):
                LeagueService.set_teams(str(league._id), {"Replacement": [self.driver.email]})
        self.assertEqual(list(db.teams.find({})), previous)

    def test_docker_entrypoint_imports_and_registers_presets(self):
        module = importlib.import_module("app")
        routes = {rule.rule for rule in module.app.url_map.iter_rules()}
        self.assertIn("/api/v1/point-systems", routes)
        self.assertEqual(db.point_system_presets.count_documents({}), 4)
        dockerfile = Path("Dockerfile").read_text()
        self.assertIn('"app:app"', dockerfile)

    def test_preset_seeding_is_repeatable_and_preserves_customization(self):
        from src.league_module.point_system_preset import PointSystemPreset
        PointSystemPreset.seed_defaults()
        preset = db.point_system_presets.find_one({})
        db.point_system_presets.update_one({"_id": preset["_id"]}, {"$set": {"active": False}})
        PointSystemPreset.seed_defaults()
        self.assertEqual(db.point_system_presets.count_documents({}), 4)
        self.assertFalse(db.point_system_presets.find_one({"_id": preset["_id"]})["active"])


class MigrationTests(RegressionFixture, unittest.TestCase):
    def legacy_league(self, race_id=None):
        league_id, race_id = ObjectId(), race_id or ObjectId()
        now = datetime.now(timezone.utc)
        doc = {
            "_id": league_id, "name": "Legacy", "owner": self.other.email, "public": True,
            "admins": [self.other.email], "participants": [self.other.email, {
                "email": self.driver.email, "league_user_name": "Custom Name"
            }], "pointSystem": {"1": 25}, "fastestLapPoint": 1, "created_at": now,
            "calendar": [{"_id": str(race_id), "track": "Spa", "date": now.isoformat()}],
            "standings": {"races": {str(race_id): {self.driver.email: {
                "position": 1, "points": 26, "fastest_lap": True
            }}}, "overall": {}}, "teams": {"Team": [self.driver.email]},
        }
        db.leagues.insert_one(doc)
        db.invites.insert_one({"league": str(league_id), "inviter": self.other.email,
                              "invited_user": self.owner.email, "status": "pending", "created_at": now})
        return db.leagues.find_one({"_id": league_id}), race_id

    def test_docker_startup_migrates_before_launching_workers(self):
        from scripts.start_server import main
        legacy, _ = self.legacy_league()

        def launch(executable, command):
            mongo.assert_schema_ready()
            detail = LeagueService.get_league_detail(str(legacy["_id"]))
            self.assertEqual(detail["standings"]["overall"][self.driver.email]["points"], 26)
            self.assertEqual(executable, "gunicorn")
            self.assertEqual(command, ["gunicorn", "-w", "4", "app:app"])

        with patch("scripts.start_server.os.execvp", side_effect=launch) as execute:
            self.assertEqual(main(["gunicorn", "-w", "4", "app:app"]), 0)
            execute.assert_called_once()
            self.assertEqual(main(["gunicorn", "-w", "4", "app:app"]), 0)
        self.assertEqual(db.race_results.count_documents({}), 1)
        self.assertEqual(db.league_members.count_documents({}), 2)
        self.assertIn('ENTRYPOINT ["python", "scripts/start_server.py"]', Path("Dockerfile").read_text())

    def test_migration_maps_legacy_uuid_race_ids_without_losing_results(self):
        for legacy_id in ("56614b84b5d14293af7c940eae350820", "56614b84-b5d1-4293-af7c-940eae350820"):
            with self.subTest(legacy_id=legacy_id):
                legacy, _ = self.legacy_league(race_id=legacy_id)
                first_plan = build_plan(db)
                self.assertEqual(first_plan, build_plan(db))
                self.assertTrue(migrate(db, apply=True)["applied"])
                race = db.races.find_one({"league_id": legacy["_id"]})
                self.assertIsInstance(race["_id"], ObjectId)
                self.assertEqual(race["legacy_id"], legacy_id)
                result = db.race_results.find_one({"league_id": legacy["_id"]})
                self.assertEqual(result["race_id"], race["_id"])
                detail = LeagueService.get_league_detail(str(legacy["_id"]))
                self.assertEqual(detail["standings"]["overall"][self.driver.email]["points"], 26)
                self.assertTrue(detail["standings"]["races"][str(race["_id"])][self.driver.email]["fastestLap"])
                self.assertEqual(db.leagues.find_one({"_id": legacy["_id"]})["calendar"], legacy["calendar"])
                self.assertEqual(migrate(db, apply=True)["operations"], 0)

    def test_docker_startup_handles_the_production_legacy_uuid(self):
        from scripts.start_server import main
        self.legacy_league(race_id="56614b84b5d14293af7c940eae350820")
        with patch("scripts.start_server.os.execvp") as execute:
            self.assertEqual(main(["gunicorn", "app:app"]), 0)
            execute.assert_called_once()
        mongo.assert_schema_ready()
        self.assertEqual(db.race_results.find_one({})["points"], 26)

    def test_docker_startup_does_not_launch_workers_on_failed_preflight(self):
        from scripts.start_server import main
        legacy, _ = self.legacy_league()
        db.leagues.update_one({"_id": legacy["_id"]}, {"$set": {"owner": "missing@example.test"}})
        with patch("scripts.start_server.os.execvp") as execute:
            self.assertEqual(main(["gunicorn", "app:app"]), 1)
            execute.assert_not_called()
        self.assertNotIn("owner_id", db.leagues.find_one({"_id": legacy["_id"]}))
        self.assertEqual(db.races.count_documents({}), 0)

    def test_startup_default_command_honors_port(self):
        from scripts.start_server import main
        with patch.dict(os.environ, {"PORT": "10000"}), patch("scripts.start_server.os.execvp") as execute:
            self.assertEqual(main([]), 0)
        execute.assert_called_once_with("gunicorn", [
            "gunicorn", "--workers", "4", "--bind", "0.0.0.0:10000", "app:app"
        ])

    def test_migration_dry_run_apply_and_repeat_preserve_legacy_data(self):
        legacy, race_id = self.legacy_league()
        summary = migrate(db)
        self.assertGreater(summary["operations"], 0)
        self.assertFalse(summary["applied"])
        self.assertEqual(db.leagues.find_one({"_id": legacy["_id"]}), legacy)
        self.assertEqual(db.races.count_documents({}), 0)
        with self.assertRaisesRegex(RuntimeError, "requires migration"):
            mongo.assert_schema_ready()
        self.assertTrue(migrate(db, apply=True)["applied"])
        mongo.assert_schema_ready()
        detail = LeagueService.get_league_detail(str(legacy["_id"]))
        self.assertEqual(detail["owner"], self.other.email)
        self.assertEqual(detail["standings"]["overall"][self.driver.email]["points"], 26)
        self.assertEqual(detail["calendar"][0]["_id"], str(race_id))
        self.assertEqual(detail["calendar"][0]["status"], "Completed")
        self.assertEqual(detail["teams"]["Team"]["total_points"], 26)
        participant = next(p for p in detail["participants"] if p["email"] == self.driver.email)
        self.assertEqual(participant["league_user_name"], "Custom Name")
        self.assertEqual(db.leagues.find_one({"_id": legacy["_id"]})["calendar"], legacy["calendar"])
        self.assertEqual(migrate(db, apply=True)["operations"], 0)
        self.assertEqual(db.league_members.count_documents({}), 2)
        self.assertEqual(db.invites.find_one({})["inviter_id"], self.other._id)

    def test_migration_preflight_failure_does_not_write(self):
        legacy, _ = self.legacy_league()
        db.leagues.update_one({"_id": legacy["_id"]}, {"$set": {"owner": "missing@example.test"}})
        with self.assertRaisesRegex(ValueError, "Cannot resolve"):
            migrate(db, apply=True)
        self.assertEqual(db.races.count_documents({}), 0)
        self.assertNotIn("owner_id", db.leagues.find_one({"_id": legacy["_id"]}))

    def test_migration_uses_stable_ids_and_preserves_existing_child_records(self):
        legacy, race_id = self.legacy_league()
        db.race_results.insert_one({"race_id": race_id, "user_id": str(self.driver._id),
                                   "result_type": "race", "points": 99, "league_id": legacy["_id"]})
        self.assertEqual(build_plan(db), build_plan(db))
        migrate(db, apply=True)
        self.assertEqual(db.race_results.find_one({})["points"], 99)

    def test_failed_migration_write_rolls_back_all_collections(self):
        legacy, _ = self.legacy_league()
        collection_type = type(db.leagues)
        update_one = collection_type.update_one

        def fail_league_update(collection, *args, **kwargs):
            if collection.name == "leagues":
                raise RuntimeError("migration write failed")
            return update_one(collection, *args, **kwargs)

        with patch.object(collection_type, "update_one", fail_league_update):
            with self.assertRaisesRegex(RuntimeError, "migration write failed"):
                migrate(db, apply=True)
        self.assertEqual(db.leagues.find_one({"_id": legacy["_id"]}), legacy)
        for name in ("league_members", "races", "race_results", "teams"):
            self.assertEqual(db[name].count_documents({}), 0)


def tearDownModule():
    mongo_client.drop_database(test_db_name)
    mongo_client.close()


if __name__ == "__main__":
    unittest.main()
