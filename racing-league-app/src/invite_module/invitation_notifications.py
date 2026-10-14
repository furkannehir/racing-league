"""Deliver committed invitations with database leases and bounded retries."""
import atexit
import logging
import uuid
from datetime import datetime, timedelta, timezone
from urllib.parse import urlsplit
from threading import Lock

from pymongo import ReturnDocument
from src.config.config import Config
from src.config.mongo import db
from src.email_module.email_service import EmailService
from src.league_module.league import League
from src.user_module.user import User

logger = logging.getLogger(__name__)
MAX_ATTEMPTS = 5
LEASE_SECONDS = 120
_scheduler = None
_scheduler_lock = Lock()


def invitation_url():
    value = (getattr(Config, 'FRONTEND_URL', None) or '').strip()
    parsed = urlsplit(value)
    if (parsed.scheme not in ('http', 'https') or not parsed.hostname or
            parsed.username or parsed.password or '?' in value or '#' in value):
        raise ValueError('FRONTEND_URL must be a frontend HTTP(S) URL')
    parsed.port  # Reject malformed ports before attempting delivery.
    return value.rstrip('/') + '/leagues'


def claim_next(now=None):
    now = now or datetime.now(timezone.utc)
    # A worker that died on its last attempt must not leave a permanent sending state.
    db.invites.update_many({'status': 'pending', 'email_status': 'sending',
                           'email_lock_until': {'$lte': now}, 'email_attempts': {'$gte': MAX_ATTEMPTS}},
                          {'$set': {'email_status': 'failed'}})
    return db.invites.find_one_and_update({
        'status': 'pending', 'email_attempts': {'$lt': MAX_ATTEMPTS},
        '$or': [
            {'email_status': {'$in': ['pending', 'failed']},
             'email_retry_at': {'$lte': now}},
            {'email_status': 'sending', 'email_lock_until': {'$lte': now}},
        ],
    }, {'$set': {'email_status': 'sending', 'email_claim_token': uuid.uuid4().hex,
                'email_lock_until': now + timedelta(seconds=LEASE_SECONDS)},
        '$inc': {'email_attempts': 1}}, sort=[('created_at', 1)], return_document=ReturnDocument.AFTER)


def deliver_claimed(invite):
    claim = {'_id': invite['_id'], 'email_claim_token': invite['email_claim_token'],
             'email_status': 'sending'}
    state = 'cancelled'
    try:
        # Handled invitations and deleted leagues no longer need a notification.
        if (db.invites.find_one({**claim, 'status': 'pending'}) and
                League.get_by_id(str(invite['league_id']))):
            url = invitation_url()
            user = User.get_user_by_auth_email(invite['invited_email'])
            response = EmailService.send_custom_email(
                to_email=invite['invited_email'], name=user.name if user else invite['invited_email'],
                subject="You're invited to join a league!",
                message_top="You have been invited to join a league. Sign in to accept or decline the invitation, or create an account first.",
                message_bottom="You join the driver roster after accepting the invitation.",
                button_name="View Invitation", url=url)
            if response is None or response is False:
                raise RuntimeError('Email provider did not accept the notification')
            state = 'sent'
    except Exception:
        state = 'failed'
        logger.warning('Invitation notification attempt failed')
    now = datetime.now(timezone.utc)
    db.invites.update_one(claim, {'$set': {
        'email_status': state, 'email_last_attempt_at': now,
        'email_retry_at': now + timedelta(seconds=min(60 * 2 ** (invite['email_attempts'] - 1), 3600)),
    }, '$unset': {'email_claim_token': '', 'email_lock_until': ''}})
    return state


def process_pending(limit=10):
    processed = 0
    for _ in range(limit):
        invite = claim_next()
        if not invite:
            break
        deliver_claimed(invite)
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
