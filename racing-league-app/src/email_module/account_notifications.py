"""Durable, coalesced account emails; public requests do not reveal account existence."""
import atexit
import hashlib
import logging
import uuid
from datetime import datetime, timedelta, timezone
from threading import Lock

from firebase_admin import auth
from pymongo import ReturnDocument
from src.auth_module.auth_service import AuthError
from src.config import mongo
from src.email_module.email_service import EmailService
from src.user_module.user import User
from src.auth_module.account_limits import reserve_delivery, RateLimited
from pymongo.errors import PyMongoError

logger = logging.getLogger(__name__)
MAX_ATTEMPTS = 5
_scheduler = None
_scheduler_lock = Lock()


def utc(value):
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value


def enqueue(kind, email, session=None, initial_registration=False):
    """Reuse pending work; allow at most three new emails per address/kind/hour."""
    if kind not in ('verification', 'password_reset'):
        raise ValueError('Invalid account email type')
    now = datetime.now(timezone.utc)
    key = hashlib.sha256((kind + ':' + email.casefold()).encode()).hexdigest()
    jobs = mongo.db.account_notifications
    existing = jobs.find_one({'_id': key}, session=session)
    if existing:
        # A second request must not restart an in-flight delivery or its retry budget.
        if not initial_registration and (existing['status'] in ('pending', 'sending') or (
                existing['status'] == 'failed' and existing['attempts'] < MAX_ATTEMPTS)):
            return
        window_start = utc(existing['window_start'])
        count = existing['window_count']
        if not initial_registration and (now - utc(existing['queued_at']) < timedelta(minutes=1) or (
                now - window_start < timedelta(hours=1) and count >= 3)):
            raise AuthError('Please wait before requesting another email.', 'email_rate_limited', 429)
        if now - window_start >= timedelta(hours=1):
            window_start, count = now, 0
    else:
        window_start, count = now, 0
    jobs.replace_one({'_id': key}, {
        '_id': key, 'kind': kind, 'email': email, 'status': 'pending', 'attempts': 0,
        'retry_at': now, 'queued_at': now, 'window_start': window_start,
        'window_count': count + 1, 'expires_at': now + timedelta(days=7),
    }, upsert=True, session=session)


def request_email(kind, email):
    # Both existing and unknown addresses use the same transaction and response.
    mongo.run_transaction(lambda session: enqueue(kind, email, session=session))


def claim_next(now=None):
    now = now or datetime.now(timezone.utc)
    jobs = mongo.db.account_notifications
    jobs.update_many({'status': 'sending', 'lock_until': {'$lte': now}, 'attempts': {'$gte': MAX_ATTEMPTS}},
                     {'$set': {'status': 'failed'}})
    query = {
        'attempts': {'$lt': MAX_ATTEMPTS}, '$or': [
            {'status': {'$in': ['pending', 'failed']}, 'retry_at': {'$lte': now}},
            {'status': 'sending', 'lock_until': {'$lte': now}},
        ],
    }

    def claim(session):
        job = jobs.find_one_and_update(query, {
            '$set': {'status': 'sending', 'claim_token': uuid.uuid4().hex,
                     'lock_until': now + timedelta(seconds=120)}, '$inc': {'attempts': 1}},
            sort=[('queued_at', 1)], return_document=ReturnDocument.AFTER, session=session)
        if job:
            reserve_delivery(now, session)
        return job

    try:
        return mongo.run_transaction(claim)
    except RateLimited:
        # Leave jobs pending with the same attempt count until a budget window reopens.
        return None
    except PyMongoError:
        logger.warning('Account email work could not be claimed; retrying on the next poll')
        return None


def deliver_claimed(job):
    claim = {'_id': job['_id'], 'status': 'sending', 'claim_token': job['claim_token']}
    state = 'cancelled'
    try:
        if mongo.db.account_notifications.find_one(claim):
            user = User.get_user_by_auth_email(job['email'])
            # A failed signup can leave only a Firebase account. It must still be
            # able to receive a reset link before its owner retries registration.
            # Deleted or ambiguous application records are not eligible for recovery.
            if user or not User.email_is_registered(job['email']):
                firebase_user = auth.get_user_by_email(job['email'])
                bound = user is None or user.firebase_uid is None or user.firebase_uid == firebase_user.uid
                eligible = not firebase_user.disabled and bound and (
                    job['kind'] != 'verification' or not firebase_user.email_verified)
                if eligible:
                    send = (EmailService.send_verification_email if job['kind'] == 'verification'
                            else EmailService.send_reset_password_email)
                    outcome = send(to_email=firebase_user.email,
                                   name=(user.name if user else getattr(firebase_user, 'display_name', None)) or '')
                    if outcome is None or outcome is False:
                        raise RuntimeError('Email provider did not accept the message')
                    state = 'sent'
    except (auth.UserNotFoundError, auth.EmailNotFoundError):
        pass
    except Exception:
        state = 'failed'
        logger.warning('Account email delivery attempt failed')
    now = datetime.now(timezone.utc)
    mongo.db.account_notifications.update_one(claim, {
        '$set': {'status': state, 'last_attempt_at': now,
                 'retry_at': now + timedelta(seconds=min(60 * 2 ** (job['attempts'] - 1), 3600))},
        '$unset': {'claim_token': '', 'lock_until': ''},
    })
    return state


def process_pending(limit=10):
    processed = 0
    for _ in range(limit):
        job = claim_next()
        if job is None:
            break
        deliver_claimed(job)
        processed += 1
    return processed


def start_delivery_worker():
    global _scheduler
    with _scheduler_lock:
        if _scheduler is not None:
            return
        from apscheduler.schedulers.background import BackgroundScheduler
        scheduler = BackgroundScheduler(timezone='UTC')
        scheduler.add_job(process_pending, 'interval', seconds=15, max_instances=1, coalesce=True)
        scheduler.start()
        _scheduler = scheduler
        atexit.register(lambda: scheduler.shutdown(wait=False) if scheduler.running else None)
