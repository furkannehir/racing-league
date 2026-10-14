"""Exercise uploads and paid-call boundaries using actual Pillow bytes and a fake provider."""
import base64
import io
import json
import types
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock, patch

import httpx
from bson import ObjectId
from openai import APITimeoutError, APIStatusError
from PIL import Image
from werkzeug.datastructures import FileStorage

from test_regressions import RegressionFixture, db, mongo
from src.league_module import image_extraction as extraction
from src.league_module.league import League


def picture(mode="RGB", size=(20, 10), file_format="PNG", **options):
    with io.BytesIO() as buffer, Image.new(mode, size) as image:
        image.save(buffer, format=file_format, **options)
        return buffer.getvalue()


def completion(rows=None, content=None, finish="stop", refusal=None):
    return types.SimpleNamespace(choices=[types.SimpleNamespace(
        finish_reason=finish, message=types.SimpleNamespace(
            content=content if content is not None else json.dumps({"results": rows or []}), refusal=refusal))])


class ImageTests(RegressionFixture, unittest.TestCase):
    def setUp(self):
        super().setUp()
        self.app.config["MAX_CONTENT_LENGTH"] = extraction.MAX_REQUEST_BYTES
        self.league, self.race = self.make_league()
        self.url = f"/api/v1/leagues/{self.league._id}/races/{self.race._id}/extract-results"
        self.provider = Mock()
        self.provider.chat.completions.create.return_value = completion([{"driver": "Owner", "position": 1}])
        from src.league_module.league_service import get_openai_client
        self.real_client_factory = get_openai_client
        client_patch = patch("src.league_module.league_service.get_openai_client", return_value=self.provider)
        self.client_factory = client_patch.start()
        self.addCleanup(client_patch.stop)

    def upload(self, files=None, url=None, headers=None):
        files = [(picture(), "image/png")] if files is None else files
        response = self.client.post(url or self.url, headers=self.headers if headers is None else headers,
                                    data={"images": [(io.BytesIO(raw), "screenshot", mime) for raw, mime in files]})
        response.request.input_stream.close()
        return response

    def assert_no_call(self):
        self.provider.chat.completions.create.assert_not_called()
        self.assertEqual(db.ai_image_usage.count_documents({}), 0)
        self.assertEqual(db.ai_image_leases.count_documents({}), 0)

    def test_normalizes_palette_gray_alpha_and_cmyk_without_tempfiles(self):
        for mode, file_format, mime in (("P", "PNG", "image/png"), ("L", "PNG", "image/png"),
                                        ("LA", "PNG", "image/png"), ("RGBA", "PNG", "image/png"),
                                        ("CMYK", "JPEG", "image/jpg")):
            with self.subTest(mode=mode), patch("tempfile.NamedTemporaryFile", side_effect=AssertionError("No temp file")):
                response = self.upload([(picture(mode, file_format=file_format), mime)])
                self.assertEqual(response.status_code, 200, response.json)
                self.assertEqual(response.json, {"results": [{"driver": "Owner", "position": 1}]})
                request = self.provider.chat.completions.create.call_args.kwargs
                encoded = request["messages"][1]["content"][1]["image_url"]["url"].split(",")[1]
                with Image.open(io.BytesIO(base64.b64decode(encoded))) as output:
                    self.assertEqual(output.mode, "RGB")
                self.assertEqual(db.ai_image_leases.count_documents({}), 0)
        self.assertEqual(db.ai_image_usage.find_one({"_id": {"$regex": "^global-day:"}})["count"], 5)

    def test_transparency_is_white_orientation_is_applied_and_resolution_is_bounded(self):
        encoded = extraction.encode_upload(FileStorage(io.BytesIO(picture("RGBA")), content_type="image/png"))
        with Image.open(io.BytesIO(base64.b64decode(encoded["image_url"]["url"].split(",")[1]))) as result:
            self.assertEqual(result.getpixel((0, 0)), (255, 255, 255))
        exif = Image.Exif()
        exif[274] = 6
        raw = picture(size=(100, 30), file_format="JPEG", exif=exif)
        encoded = extraction.encode_upload(FileStorage(io.BytesIO(raw), content_type="image/jpeg"))
        with Image.open(io.BytesIO(base64.b64decode(encoded["image_url"]["url"].split(",")[1]))) as result:
            self.assertEqual(result.size, (30, 100))
        raw = picture(size=(2500, 100))
        encoded = extraction.encode_upload(FileStorage(io.BytesIO(raw), content_type="image/png"))
        with Image.open(io.BytesIO(base64.b64decode(encoded["image_url"]["url"].split(",")[1]))) as result:
            self.assertEqual(max(result.size), 2048)

    def test_two_images_share_one_structured_bounded_paid_request_and_never_save_results(self):
        response = self.upload([(picture(), "image/png"), (picture(), "application/octet-stream")])
        self.assertEqual(response.status_code, 200)
        self.provider.chat.completions.create.assert_called_once()
        request = self.provider.chat.completions.create.call_args.kwargs
        self.assertEqual(len(request["messages"][1]["content"]), 3)
        self.assertEqual(request["model"], "gpt-4o")
        self.assertEqual(request["timeout"], 20)
        self.assertEqual(request["max_completion_tokens"], 4000)
        self.assertFalse(request["store"])
        self.assertTrue(request["response_format"]["json_schema"]["strict"])
        self.assertEqual(db.race_results.count_documents({}), 0)

    def test_real_client_configuration_disables_automatic_paid_retries(self):
        from src.league_module import league_service
        with patch.object(league_service, "client", None), patch.object(league_service.Config, "OPENAI_API_KEY", "test-key"), \
                patch("openai.OpenAI") as constructor:
            self.real_client_factory()
            self.assertEqual(constructor.call_args.kwargs["max_retries"], 0)
            self.assertEqual(constructor.call_args.kwargs["timeout"], 20)

    def test_invalid_count_corrupt_empty_or_disguised_files_never_call_provider(self):
        for files, status in (([], 400), ([(picture(), "image/png")] * 3, 400),
                              ([(b"", "image/png")], 400), ([(b"not an image", "image/png")], 400),
                              ([(picture()[:-20], "image/png")], 400),
                              ([(picture(), "text/plain")], 415), ([(picture(), "image/jpeg")], 415),
                              ([(picture(file_format="GIF"), "image/png")], 415)):
            with self.subTest(status=status, size=len(files)):
                response = self.upload(files)
                self.assertEqual(response.status_code, status, response.json)
                self.assert_no_call()

    def test_file_and_total_body_limits_are_enforced_before_provider(self):
        response = self.upload([(b"x" * (extraction.MAX_IMAGE_BYTES + 1), "image/png")])
        self.assertEqual(response.status_code, 413)
        # Oversized non-image form fields must also count toward the request cap.
        response = self.client.post(self.url, headers=self.headers,
                                    data={"unexpected": "x" * (extraction.MAX_REQUEST_BYTES + 1)})
        self.assertEqual(response.status_code, 413)
        self.assertEqual(response.json["code"], "request_too_large")
        self.assert_no_call()

    def test_pixel_dimension_bomb_and_animation_limits_reject_before_decode(self):
        for size in ((4000, 4000), (8193, 1)):
            image = Mock(format="PNG", size=size)
            image.__enter__ = Mock(return_value=image)
            image.__exit__ = Mock(return_value=False)
            with patch.object(extraction.Image, "open", return_value=image):
                response = self.upload()
                self.assertEqual(response.status_code, 413)
                image.load.assert_not_called()
                image.verify.assert_not_called()
        with patch.object(extraction.Image, "open", side_effect=Image.DecompressionBombError()):
            self.assertEqual(self.upload().status_code, 413)
        with io.BytesIO() as buffer, Image.new("RGB", (5, 5), "red") as first, Image.new("RGB", (5, 5), "blue") as second:
            first.save(buffer, format="PNG", save_all=True, append_images=[second])
            self.assertEqual(self.upload([(buffer.getvalue(), "image/png")]).status_code, 415)
        self.assert_no_call()

    def test_member_role_race_relationship_and_active_league_are_required(self):
        self.assertEqual(self.upload(headers={}).status_code, 401)
        self.actor = self.other
        self.assertEqual(self.upload().status_code, 404)
        self.actor = self.driver
        self.assertEqual(self.upload().status_code, 403)
        self.actor = self.owner
        other_league, other_race = self.make_league()
        for race_id in (str(other_race._id), str(ObjectId()), "invalid"):
            url = f"/api/v1/leagues/{self.league._id}/races/{race_id}/extract-results"
            self.assertEqual(self.upload(url=url).status_code, 404)
        League.soft_delete(str(self.league._id))
        self.assertEqual(self.upload().status_code, 404)
        self.assert_no_call()

    def test_canonical_and_uppercase_objectids_refer_to_the_same_race(self):
        url = f"/api/v1/leagues/{str(self.league._id).upper()}/races/{str(self.race._id).upper()}/extract-results"
        self.assertEqual(self.upload(url=url).status_code, 200)

    def test_invalid_refused_or_truncated_ai_output_is_failure_without_raw_content(self):
        for response in (completion(content="secret raw provider text"), completion(content="[]"),
                         completion(content='{"results":{}}'), completion([{"position": 1}]),
                         completion([{"driver": "Owner", "position": True}]),
                         completion([{"driver": 123, "position": 1}]),
                         completion([{"driver": "Owner", "position": 0}]),
                         completion([{"driver": "Owner", "position": 1}] * 201),
                         completion(finish="length"), completion(refusal="secret raw provider text")):
            with self.subTest(response=response):
                db.ai_image_usage.delete_many({})
                self.provider.chat.completions.create.return_value = response
                result = self.upload()
                self.assertEqual(result.status_code, 502)
                self.assertEqual(result.json["code"], "invalid_ai_results")
                self.assertNotIn("secret", result.get_data(as_text=True))
                self.assertNotIn("raw_content", result.json)
                self.assertEqual(db.ai_image_leases.count_documents({}), 0)

    def test_partial_and_empty_results_are_valid_suggestions(self):
        for rows in ([], [{"driver": None, "position": 1}], [{"driver": "Owner", "position": None}]):
            self.provider.chat.completions.create.return_value = completion(rows)
            result = self.upload()
            self.assertEqual(result.status_code, 200)
            self.assertEqual(result.json["results"], rows)

    def test_provider_timeout_or_failure_is_sanitized_and_consumes_only_one_attempt(self):
        request = httpx.Request("POST", "https://example.test")
        for failure, expected in ((APITimeoutError(request=request), 504),
                                  (APIStatusError("secret", response=httpx.Response(500, request=request), body=None), 503)):
            self.provider.chat.completions.create.side_effect = failure
            result = self.upload()
            self.assertEqual(result.status_code, expected)
            self.assertNotIn("secret", result.get_data(as_text=True))
            self.assertEqual(db.ai_image_leases.count_documents({}), 0)
        self.assertEqual(self.provider.chat.completions.create.call_count, 2)
        self.assertEqual(db.ai_image_usage.find_one({"_id": {"$regex": "^global-day:"}})["count"], 2)

    def test_missing_client_configuration_and_database_failures_do_not_make_paid_calls(self):
        self.client_factory.side_effect = ValueError("secret config")
        result = self.upload()
        self.assertEqual(result.status_code, 503)
        self.assertNotIn("secret", result.get_data(as_text=True))
        self.assert_no_call()
        self.client_factory.side_effect = None
        with patch.object(mongo, "run_transaction", side_effect=RuntimeError("secret db")):
            self.assertEqual(self.upload().status_code, 503)
        self.assert_no_call()

    def test_processing_slot_blocks_other_workers_and_recovers_expired_lease(self):
        now = datetime.now(timezone.utc)
        db.ai_image_leases.insert_one({"_id": "processing", "token": "other-worker", "expires_at": now + timedelta(minutes=1)})
        result = self.upload()
        self.assertEqual(result.status_code, 429)
        self.assertEqual(result.headers["Retry-After"], "15")
        self.provider.chat.completions.create.assert_not_called()
        self.assertEqual(db.ai_image_leases.find_one()["token"], "other-worker")
        db.ai_image_leases.update_one({"_id": "processing"}, {"$set": {"expires_at": now - timedelta(seconds=1)}})
        self.assertEqual(self.upload().status_code, 200)
        self.assertEqual(db.ai_image_leases.count_documents({}), 0)

    def test_user_and_global_quotas_refuse_without_incrementing_other_counters(self):
        with patch.object(extraction.Config, "AI_IMAGE_USER_HOURLY_LIMIT", 1, create=True):
            self.assertEqual(self.upload().status_code, 200)
            before = list(db.ai_image_usage.find({}))
            result = self.upload()
            self.assertEqual(result.status_code, 429)
            self.assertGreater(int(result.headers["Retry-After"]), 0)
            self.assertEqual(list(db.ai_image_usage.find({})), before)
        db.ai_image_usage.delete_many({})
        with patch.object(extraction.Config, "AI_IMAGE_GLOBAL_DAILY_LIMIT", 1, create=True):
            self.assertEqual(self.upload().status_code, 200)
            self.actor = self.driver
            from src.league_module.league_member import LeagueMember
            member = LeagueMember.get_member(str(self.league._id), str(self.driver._id))
            db.league_members.update_one({"_id": member._id}, {"$set": {"role": "admin"}})
            self.assertEqual(self.upload().status_code, 429)
            self.assertEqual(db.ai_image_usage.count_documents({"_id": {"$regex": str(self.driver._id)}}), 0)
        self.assertEqual(db.ai_image_leases.count_documents({}), 0)

    def test_quota_counters_roll_back_on_failure_and_new_hour_reopens_hourly_limit(self):
        now = datetime.now(timezone.utc).replace(minute=15, second=0, microsecond=0)
        with patch.object(extraction.Config, "AI_IMAGE_USER_HOURLY_LIMIT", 1, create=True):
            extraction.consume_quota(str(self.owner._id), now)
            with self.assertRaises(extraction.ExtractionError):
                extraction.consume_quota(str(self.owner._id), now + timedelta(minutes=10))
            extraction.consume_quota(str(self.owner._id), now + timedelta(hours=1))
        db.ai_image_usage.delete_many({})
        collection = db.ai_image_usage
        original = collection.update_one
        calls = 0

        def fail_second(*args, **kwargs):
            nonlocal calls
            calls += 1
            if calls == 2:
                raise RuntimeError("write failed")
            return original(*args, **kwargs)

        with patch.object(collection, "update_one", side_effect=fail_second), self.assertRaises(RuntimeError):
            extraction.consume_quota(str(self.owner._id), now)
        self.assertEqual(db.ai_image_usage.count_documents({}), 0)

    def test_daily_user_limit_and_zero_budget_disable_paid_calls(self):
        with patch.object(extraction.Config, "AI_IMAGE_USER_DAILY_LIMIT", 1, create=True):
            self.assertEqual(self.upload().status_code, 200)
            before = list(db.ai_image_usage.find({}))
            self.assertEqual(self.upload().status_code, 429)
            self.assertEqual(list(db.ai_image_usage.find({})), before)
        db.ai_image_usage.delete_many({})
        self.provider.chat.completions.create.reset_mock()
        with patch.object(extraction.Config, "AI_IMAGE_GLOBAL_DAILY_LIMIT", 0, create=True):
            self.assertEqual(self.upload().status_code, 429)
        self.assert_no_call()
