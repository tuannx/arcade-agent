"""Domain events decouple billing from notifications (cycle broken)."""
from dataclasses import dataclass


@dataclass
class InvoiceIssued:
    order_id: str
    customer_email: str
    amount: float
    lines: list
