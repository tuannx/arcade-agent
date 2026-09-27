"""PLANTED SMELL: god module. String utils, crypto, dates, http, files and
money formatting live side by side with no internal cohesion."""
import hashlib
import json
import os
from datetime import datetime, timezone


# --- strings ---
def slugify(text):
    return text.lower().replace(" ", "-")


def truncate(text, n=80):
    return text[:n]


def camel_to_snake(name):
    return "".join("_" + c.lower() if c.isupper() else c for c in name)


# --- crypto ---
def sha256(text):
    return hashlib.sha256(text.encode()).hexdigest()


def md5(text):
    return hashlib.md5(text.encode()).hexdigest()


# --- dates ---
def utcnow():
    return datetime.now(timezone.utc).isoformat()


def days_ago(n):
    return (datetime.now(timezone.utc).timestamp() - n * 86400)


# --- http ---
def build_url(base, path):
    return base.rstrip("/") + "/" + path.lstrip("/")


def parse_query(qs):
    return dict(p.split("=") for p in qs.split("&") if "=" in p)


# --- files ---
def read_text(path):
    with open(path) as f:
        return f.read()


def write_text(path, text):
    with open(path, "w") as f:
        f.write(text)


def file_size(path):
    return os.path.getsize(path)


# --- money ---
def cents_to_dollars(cents):
    return cents / 100.0


def format_money(amount, currency="$"):
    return f"{currency}{amount:,.2f}"


# --- json ---
def to_json(obj):
    return json.dumps(obj)


def from_json(text):
    return json.loads(text)


# --- misc ---
def chunked(seq, n):
    return [seq[i:i + n] for i in range(0, len(seq), n)]


def flatten(lists):
    return [x for sub in lists for x in sub]


def is_even(n):
    return n % 2 == 0


class Cache:
    def __init__(self):
        self._d = {}

    def get(self, k):
        return self._d.get(k)

    def put(self, k, v):
        self._d[k] = v
