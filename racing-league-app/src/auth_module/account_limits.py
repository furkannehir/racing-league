"""Shared limits on account-email producers and worker attempts, across all processes."""
import hashlib
import ipaddress
import math
from datetime import datetime, timedelta, timezone

from pymongo.errors import DuplicateKeyError
from werkzeug.middleware.proxy_fix import ProxyFix

from src.config import mongo
from src.config.config import Config


class RateLimited(Exception):
    def __init__(self, retry_after):
        super().__init__("Too many account requests. Please try again later.")
        self.retry_after = retry_after


def reserve(buckets, now, session):
    counters = mongo.db.account_rate_limits
    for key, reset, limit in buckets:
        count = (counters.find_one({'_id': key}, session=session) or {}).get('count', 0)
        if count >= limit:
            raise RateLimited(max(1, math.ceil((reset - now).total_seconds())))
    for key, reset, _ in buckets:
        counters.update_one({'_id': key}, {
            '$inc': {'count': 1}, '$setOnInsert': {'expires_at': reset + timedelta(days=1)},
        }, upsert=True, session=session)


def reserve_request(peer, now=None):
    now = now or datetime.now(timezone.utc)
    # Group IPv6 addresses by /64 and normalize IPv4-mapped IPv6 addresses.
    try:
        address = ipaddress.ip_address(peer)
        if isinstance(address, ipaddress.IPv6Address) and address.ipv4_mapped:
            address = address.ipv4_mapped
        peer = str(ipaddress.ip_network(f'{address}/64', strict=False)) if address.version == 6 else str(address)
    except ValueError:
        peer = 'unknown'
    peer_key = hashlib.sha256(peer.encode()).hexdigest()
    minute = now.replace(minute=(now.minute // 10) * 10, second=0, microsecond=0)
    hour = now.replace(minute=0, second=0, microsecond=0)
    day = hour.replace(hour=0)
    buckets = [
        (f'account-ip:{peer_key}:{minute.isoformat()}', minute + timedelta(minutes=10),
         getattr(Config, 'ACCOUNT_REQUEST_IP_LIMIT', 30)),
        (f'account-hour:{hour.isoformat()}', hour + timedelta(hours=1),
         getattr(Config, 'ACCOUNT_REQUEST_GLOBAL_HOURLY_LIMIT', 300)),
        (f'account-day:{day.isoformat()}', day + timedelta(days=1),
         getattr(Config, 'ACCOUNT_REQUEST_GLOBAL_DAILY_LIMIT', 1000)),
    ]
    # First insertion of a shared bucket can collide. Recheck using a new transaction.
    for attempt in range(3):
        try:
            return mongo.run_transaction(lambda session: reserve(buckets, now, session))
        except DuplicateKeyError:
            if attempt == 2:
                raise


def reserve_delivery(now, session):
    hour = now.replace(minute=0, second=0, microsecond=0)
    day = hour.replace(hour=0)
    reserve([
        (f'delivery-hour:{hour.isoformat()}', hour + timedelta(hours=1),
         getattr(Config, 'ACCOUNT_DELIVERY_HOURLY_LIMIT', 100)),
        (f'delivery-day:{day.isoformat()}', day + timedelta(days=1),
         getattr(Config, 'ACCOUNT_DELIVERY_DAILY_LIMIT', 500)),
    ], now, session)


def configure_proxy(app):
    # Untrusted forwarded headers are ignored unless the deployment opts in.
    hops = getattr(Config, 'TRUSTED_PROXY_HOPS', 0)
    if hops:
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=hops, x_proto=0, x_host=0, x_port=0, x_prefix=0)
