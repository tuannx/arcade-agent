"""Order orchestration. Depends on many packages (link-overload prone)."""
from shop.auth.login import current_user
from shop.billing.invoice import Invoice
from shop.notifications.emailer import send_receipt
from shop.notifications.sms import send_sms
from shop.orders.validators import valid_items
from shop.utils.helpers import slugify, utcnow


class OrderService:
    def place(self, items, email, phone):
        if not valid_items(items):
            raise ValueError("bad items")
        user = current_user()
        ref = slugify(f"order-{utcnow()}-{user}")
        inv = Invoice(ref, items, email).issue()
        send_receipt(email, ref, inv.amount)
        send_sms(phone, f"order {ref} placed")
        return ref
