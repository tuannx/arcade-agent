"""String utilities (kept: actually used by orders)."""


def slugify(text):
    return text.lower().replace(" ", "-")


def truncate(text, n=80):
    return text[:n]
