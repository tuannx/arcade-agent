"""E-mail notifications. PLANTED SMELL: reaches back into billing to
rebuild receipt lines, closing the billing <-> notifications cycle."""
from shop.billing.invoice import Invoice  # <-- cycle edge
from shop.billing.pricing import subtotal
from shop.notifications.sms import send_sms  # internal edge: anchors emailer in Notifications


def render_lines(invoice: Invoice):
    return [f"{i['price']} x {i['qty']}" for i in invoice.items]


def send_receipt(to_email, order_id, amount):
    print(f"receipt for order {order_id}: ${amount:.2f} -> {to_email}")


def resend_last_receipt(invoice: Invoice):
    lines = render_lines(invoice)
    send_receipt("n/a", invoice.order_id, subtotal(invoice.items))
    send_sms("n/a", f"receipt resent for order {invoice.order_id}")
    return lines
