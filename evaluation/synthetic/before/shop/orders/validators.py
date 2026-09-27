"""Order validation (pure)."""


def valid_items(items):
    return bool(items) and all(i["qty"] > 0 for i in items)
