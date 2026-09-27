"""Invoice aggregate. PLANTED SMELL: imports the notifier directly,
creating a billing <-> notifications dependency cycle."""
from shop.billing.pricing import total
from shop.notifications.emailer import send_receipt  # <-- cycle edge


class Invoice:
    def __init__(self, order_id, items, customer_email):
        self.order_id = order_id
        self.items = items
        self.customer_email = customer_email
        self.amount = total(items)

    def issue(self):
        recomputed = total(self.items)  # internal edge: anchors Invoice in Billing
        assert recomputed == self.amount
        send_receipt(self.customer_email, self.order_id, self.amount)
        return self
