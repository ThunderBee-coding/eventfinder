import os
import hashlib
import base64
import warnings
from cryptography.fernet import Fernet


def get_fernet() -> Fernet:
    secret = os.getenv("SECRET_KEY")
    if not secret:
        warnings.warn("SECRET_KEY nicht gesetzt — unsicherer Fallback aktiv", RuntimeWarning, stacklevel=2)
        secret = "fallback-insecure-key"
    key = base64.urlsafe_b64encode(hashlib.sha256(secret.encode()).digest())
    return Fernet(key)


def encrypt_value(value: str) -> str:
    return get_fernet().encrypt(value.encode()).decode()


def decrypt_value(encrypted: str) -> str:
    return get_fernet().decrypt(encrypted.encode()).decode()
