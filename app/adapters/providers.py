from __future__ import annotations

from datetime import date, datetime, timedelta


class EInvoiceProvider:
    def fetch(self, connection_id: str, tax_id: str) -> list[dict]:
        today = date.today()
        return [
            {
                "invoice_id": f"sale-{i}",
                "kind": "sale",
                "issuer_id": tax_id,
                "receiver_id": f"buyer-{i%3}",
                "issue_date": (today - timedelta(days=i * 8)).isoformat(),
                "amount": 1000 + i * 25,
                "currency": "AOA",
                "status": "issued",
            }
            for i in range(1, 25)
        ] + [
            {
                "invoice_id": f"purchase-{i}",
                "kind": "purchase",
                "issuer_id": f"supplier-{i%2}",
                "receiver_id": tax_id,
                "issue_date": (today - timedelta(days=i * 10)).isoformat(),
                "amount": 700 + i * 20,
                "currency": "AOA",
                "status": "issued",
            }
            for i in range(1, 20)
        ]


class BankProvider:
    def fetch(self, connection_id: str) -> list[dict]:
        now = datetime.utcnow()
        items = []
        for i in range(1, 210, 7):
            items.append(
                {
                    "txn_id": f"in-{i}",
                    "timestamp": (now - timedelta(days=i)).isoformat(),
                    "amount": 600 + i * 5,
                    "currency": "AOA",
                    "direction": "in",
                    "reference": "invoice settlement",
                }
            )
            items.append(
                {
                    "txn_id": f"out-{i}",
                    "timestamp": (now - timedelta(days=i)).isoformat(),
                    "amount": 250 + i * 3,
                    "currency": "AOA",
                    "direction": "out",
                    "reference": "supplier payment",
                }
            )
        return items


class ProcessorProvider:
    def fetch(self, connection_id: str) -> list[dict]:
        return []


class RegistryProvider:
    def fetch(self, connection_id: str | None, tax_id: str) -> tuple[str, list[dict]]:
        if not connection_id:
            return "not_configured", []
        if connection_id == "unavailable":
            return "unavailable", []
        return (
            "ok",
            [
                {
                    "filing_id": "f-1",
                    "debtor_id": tax_id,
                    "collateral_type": "receivables",
                    "status": "active",
                }
            ],
        )
