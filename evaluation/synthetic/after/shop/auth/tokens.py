"""Token helpers (pure)."""
import secrets


def new_token():
    return secrets.token_hex(16)
