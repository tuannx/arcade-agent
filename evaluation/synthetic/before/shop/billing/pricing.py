"""Pure pricing calculations (no dependencies)."""


def subtotal(items):
    return sum(i["price"] * i["qty"] for i in items)


def tax_amount(subtotal_value, rate=0.1):
    return subtotal_value * rate


def total(items, rate=0.1):
    st = subtotal(items)
    return st + tax_amount(st, rate)
