"""Authenticated credential encryption; keys are external to the database."""
import json
from cryptography.fernet import Fernet, MultiFernet, InvalidToken
from .core import Blocked


def validate_keys(value):
    if not value:
        raise ValueError('CREDENTIAL_KEYS must contain an external Fernet key')
    for key in value.split(','):
        Fernet(key.strip().encode())


def cipher():
    from .config import settings
    try:
        value=settings().credential_keys
        validate_keys(value)
        return MultiFernet([Fernet(k.strip().encode()) for k in value.split(',')])
    except (ValueError, TypeError):
        raise Blocked('Credential storage unavailable; configure the external encryption key') from None


def encrypt(value):
    return cipher().encrypt(json.dumps(value,separators=(',',':')).encode()).decode()


def decrypt(value):
    try:
        return json.loads(cipher().decrypt(value.encode()))
    except (InvalidToken, ValueError, TypeError, KeyError):
        raise Blocked('Credential decryption failed; reconnect after restoring the correct key') from None


def rotate(value):
    try:
        return cipher().rotate(value.encode()).decode()
    except InvalidToken:
        raise Blocked('Credential rotation failed; retain the old key') from None
