"""Order orchestration. REFACTORED: owns the billing->notification flow,
so billing no longer depends on notifications (cycle broken)."""
from shop.auth.login import current_user
from shop.billing.invoice import Invoice
from shop.notifications.emailer import send_issued
from shop.notifications.sms import send_sms
from shop.orders.validators import valid_items
from shop.utils.text import slugify
from shop.utils.timex import utcnow


class OrderService:
    def place(self, items, email, phone):
        if not valid_items(items):
            raise ValueError("bad items")
        user = current_user()
        ref = slugify(f"order-{utcnow()}-{user}")
        event = Invoice(ref, items, email).issue()
        send_issued(event)
        send_sms(phone, f"order {ref} placed")
        return ref
