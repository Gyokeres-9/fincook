from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from enum import Enum
from typing import Any


class ProductType(str, Enum):
    RBF = "RBF"
    IBF = "IBF"


class DecisionStatus(str, Enum):
    recommendation = "recommendation"
    manual_review_required = "manual_review_required"
    reject = "reject"


@dataclass
class ConnectionRequest:
    einvoice_connection_id: str
    bank_connection_id: str
    processor_connection_id: str | None = None
    registry_connection_id: str | None = None


@dataclass
class TimeWindowRequest:
    months_invoices: int = 12
    months_bank: int = 6


@dataclass
class BorrowerRequest:
    legal_name: str
    tax_id: str
    country_code: str


@dataclass
class UnderwriteRequest:
    application_id: str
    borrower: BorrowerRequest
    product_type: ProductType
    requested_amount: float
    currency: str
    connections: ConnectionRequest
    time_window: TimeWindowRequest

    @classmethod
    def model_validate(cls, payload: dict[str, Any]) -> "UnderwriteRequest":
        return cls(
            application_id=payload["application_id"],
            borrower=BorrowerRequest(**payload["borrower"]),
            product_type=ProductType(payload["product_type"]),
            requested_amount=float(payload["requested_amount"]),
            currency=payload["currency"],
            connections=ConnectionRequest(**payload["connections"]),
            time_window=TimeWindowRequest(**payload.get("time_window", {})),
        )


@dataclass
class UnderwriteRunResponse:
    underwrite_run_id: str
    status: str


@dataclass
class Invoice:
    invoice_id: str
    kind: str
    issuer_id: str
    receiver_id: str
    issue_date: date
    due_date: date | None = None
    amount: float = 0
    currency: str = ""
    status: str = "unknown"
    linked_invoice_id: str | None = None
    raw_ref: str = ""


@dataclass
class BankTransaction:
    txn_id: str
    timestamp: datetime
    amount: float
    currency: str
    direction: str
    counterparty: str | None = None
    reference: str | None = None
    balance_after: float | None = None
    raw_ref: str = ""


@dataclass
class RegistryFiling:
    filing_id: str
    debtor_id: str
    collateral_type: str
    status: str
    filing_date: date | None = None
    expiry_date: date | None = None
    secured_party: str | None = None
    raw_ref: str = ""
