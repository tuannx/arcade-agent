"""E-mail notifications. REFACTORED: depends only on the billing *event*,
never on the Invoice aggregate -> cycle is gone."""
from shop.billing.events import InvoiceIssued
from shop.notifications.sms import send_sms  # internal edge: stays in Notifications


def send_receipt(to_email, order_id, amount):
    print(f"receipt for order {order_id}: ${amount:.2f} -> {to_email}")


def send_issued(event: InvoiceIssued):
    send_receipt(event.customer_email, event.order_id, event.amount)
    send_sms(event.customer_email, f"receipt sent for order {event.order_id}")
    return event.lines
