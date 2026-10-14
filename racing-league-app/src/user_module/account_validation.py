"""Validate account inputs before calling Firebase or writing profiles."""
from email_validator import EmailNotValidError, validate_email


def normalize_email(value):
    if not isinstance(value, str) or len(value) > 320:
        raise ValueError('A valid email address is required')
    try:
        return validate_email(value.strip(), check_deliverability=False).normalized.casefold()
    except EmailNotValidError as error:
        raise ValueError('A valid email address is required') from error


def validate_name(value):
    if not isinstance(value, str) or not value.strip() or len(value.strip()) > 100:
        raise ValueError('Name must contain 1 to 100 characters')
    return value.strip()


def validate_bio(value):
    if not isinstance(value, str) or len(value) > 1000:
        raise ValueError('Bio must be text containing at most 1000 characters')
    return value.strip()


def validate_password(value):
    if not isinstance(value, str) or not 6 <= len(value) <= 128:
        raise ValueError('Password must contain 6 to 128 characters')
    return value
