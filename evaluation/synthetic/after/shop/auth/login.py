"""Login flow. REFACTORED: imports cohesive utils modules."""
from shop.auth.tokens import new_token
from shop.utils.crypto import sha256
from shop.utils.timex import utcnow


SESSIONS = {}


def current_user():
    return "demo-user"


def login(username, password):
    digest = sha256(f"{username}:{password}:{utcnow()}")
    token = new_token()
    SESSIONS[token] = (username, digest)
    return token
