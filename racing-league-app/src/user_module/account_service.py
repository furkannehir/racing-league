"""Coordinate Firebase signup with application persistence and email work."""
import logging
import hashlib
import uuid
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from bson import ObjectId
from firebase_admin import auth, exceptions as firebase_errors
from pymongo.errors import PyMongoError, DuplicateKeyError
from pymongo import ReturnDocument
from src.auth_module.auth_service import AuthError, AuthService
from src.config import mongo
from src.email_module import account_notifications
from src.user_module.user import User
from src.user_module.account_validation import normalize_email, validate_name, validate_password

logger = logging.getLogger(__name__)


def already_registered():
    return AuthError('An account already uses this email. Sign in or reset your password.',
                     'account_exists', 409)


@contextmanager
def registration_lease(email):
    """Prevent another signup from recovering an account while cleanup deletes it."""
    now = datetime.now(timezone.utc)
    key = hashlib.sha256(email.encode()).hexdigest()
    token = uuid.uuid4().hex
    try:
        mongo.db.registration_leases.find_one_and_update(
            {'_id': key, 'expires_at': {'$lte': now}},
            {'$set': {'token': token, 'expires_at': now + timedelta(minutes=10)}},
            upsert=True, return_document=ReturnDocument.AFTER)
    except DuplicateKeyError as error:
        raise AuthError('Registration is already in progress. Please wait a moment and retry.',
                        'registration_in_progress', 409) from error
    except PyMongoError as error:
        raise AuthError('Registration is temporarily unavailable. Please try again.',
                        'registration_unavailable', 503) from error
    try:
        yield {'_id': key, 'token': token}
    finally:
        try:
            mongo.db.registration_leases.delete_one({'_id': key, 'token': token})
        except PyMongoError:
            logger.warning('Registration lease release failed; it will expire automatically')


class AccountService:
    @staticmethod
    def register(data):
        if not isinstance(data, dict) or set(data) - {'name', 'email', 'password'}:
            raise ValueError('Name, email, and password are required')
        name = validate_name(data.get('name'))
        email = normalize_email(data.get('email'))
        password = validate_password(data.get('password'))
        with registration_lease(email) as lease:
            return AccountService.persist_registration(name, email, password, lease)

    @staticmethod
    def persist_registration(name, email, password, lease):
        try:
            if User.email_is_registered(email):
                raise already_registered()
        except PyMongoError as error:
            raise AuthError('Registration is temporarily unavailable. Please try again.',
                            'registration_unavailable', 503) from error

        created = False
        try:
            firebase_user = AuthService.register_user(email, password, name)
            created = True
        except auth.EmailAlreadyExistsError:
            # A previous signup may have failed after Firebase creation. Ownership
            # must be proved with the password before restoring its missing profile.
            try:
                tokens = AuthService.login_user(email, password)
                firebase_user = auth.get_user(tokens.uid)
                if firebase_user.disabled or firebase_user.email.casefold() != email:
                    raise already_registered()
            except AuthError as error:
                if error.status == 401:
                    raise already_registered() from error
                raise
            except (ValueError, auth.UserNotFoundError) as error:
                raise already_registered() from error
            except firebase_errors.FirebaseError as error:
                raise AuthError('Registration is temporarily unavailable. Please try again.',
                                'registration_unavailable', 503) from error
        except (ValueError, firebase_errors.InvalidArgumentError) as error:
            raise AuthError('The registration details were rejected.', 'invalid_registration', 400) from error
        except firebase_errors.FirebaseError as error:
            raise AuthError('Registration is temporarily unavailable. Please try again.',
                            'registration_unavailable', 503) from error

        user = User(ObjectId(), name, email, firebase_uid=firebase_user.uid)
        def persist(session):
            user.save(session=session)
            account_notifications.enqueue('verification', email, session=session, initial_registration=True)
            return user
        try:
            return mongo.run_transaction(persist)
        except PyMongoError as error:
            # Commit acknowledgement can be lost. Never delete Firebase while a
            # committed profile could already be using the account.
            try:
                committed = User.get_by_firebase_uid(firebase_user.uid)
                if committed:
                    if committed.email.casefold() == email:
                        return committed
                    raise already_registered()
                existing = User.email_is_registered(email)
            except PyMongoError:
                logger.warning('Registration persistence could not be confirmed; retry can recover it')
                raise AuthError('Registration could not be completed. Please retry with the same details.',
                                'registration_unavailable', 503) from error
            if created:
                try:
                    # Extend the still-owned lease before making the external delete.
                    # If the lease was lost, a retry may already be restoring this UID.
                    now = datetime.now(timezone.utc)
                    retained = mongo.db.registration_leases.update_one(
                        {**lease, 'expires_at': {'$gt': now}},
                        {'$set': {'expires_at': now + timedelta(minutes=10)}})
                    if retained.matched_count == 1:
                        auth.delete_user(firebase_user.uid)
                except auth.UserNotFoundError:
                    pass
                except (firebase_errors.FirebaseError, PyMongoError):
                    logger.warning('Registration cleanup could not be completed; retry can recover it')
            if existing:
                raise already_registered() from error
            raise AuthError('Registration could not be completed. Please retry with the same details.',
                            'registration_unavailable', 503) from error
