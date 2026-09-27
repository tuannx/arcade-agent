"""Invoice aggregate. REFACTORED: no longer imports the notifier;
it publishes an InvoiceIssued event instead (orchestrator sends it)."""
from shop.billing.events import InvoiceIssued
from shop.billing.pricing import subtotal, total


class Invoice:
    def __init__(self, order_id, items, customer_email):
        self.order_id = order_id
        self.items = items
        self.customer_email = customer_email
        self.amount = total(items)

    def issue(self):
        lines = [f"{i['price']} x {i['qty']}" for i in self.items]
        return InvoiceIssued(self.order_id, self.customer_email, self.amount, lines)
