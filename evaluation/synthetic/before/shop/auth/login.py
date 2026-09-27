"""Login flow. Reaches into the utils god-module."""
from shop.auth.tokens import new_token
from shop.utils.helpers import utcnow, sha256  # god-module edge


SESSIONS = {}


def current_user():
    return "demo-user"


def login(username, password):
    digest = sha256(f"{username}:{password}:{utcnow()}")
    token = new_token()
    SESSIONS[token] = (username, digest)
    return token
