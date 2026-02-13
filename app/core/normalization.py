from __future__ import annotations

from datetime import date, datetime

from app.models.schemas import BankTransaction, Invoice, RegistryFiling


def normalize_invoices(raw: list[dict]) -> list[Invoice]:
    seen: set[str] = set()
    out: list[Invoice] = []
    for row in raw:
        if row["invoice_id"] in seen:
            continue
        seen.add(row["invoice_id"])
        out.append(
            Invoice(
                invoice_id=row["invoice_id"],
                kind=row["kind"],
                issuer_id=row["issuer_id"],
                receiver_id=row["receiver_id"],
                issue_date=date.fromisoformat(row["issue_date"]) if isinstance(row["issue_date"], str) else row["issue_date"],
                due_date=date.fromisoformat(row["due_date"]) if row.get("due_date") else None,
                amount=float(row["amount"]),
                currency=row["currency"],
                status=row.get("status", "unknown"),
                linked_invoice_id=row.get("credit_note_ref"),
                raw_ref=f"raw:einvoice:{row['invoice_id']}",
            )
        )
    return out


def normalize_bank(raw: list[dict]) -> list[BankTransaction]:
    seen: set[str] = set()
    out: list[BankTransaction] = []
    for row in raw:
        if row["txn_id"] in seen:
            continue
        seen.add(row["txn_id"])
        out.append(
            BankTransaction(
                txn_id=row["txn_id"],
                timestamp=datetime.fromisoformat(row["timestamp"]),
                amount=float(row["amount"]),
                currency=row["currency"],
                direction=row["direction"],
                counterparty=row.get("counterparty"),
                reference=row.get("reference"),
                balance_after=row.get("balance_after"),
                raw_ref=f"raw:bank:{row['txn_id']}",
            )
        )
    return out


def normalize_registry(raw: list[dict]) -> list[RegistryFiling]:
    return [
        RegistryFiling(
            filing_id=r["filing_id"],
            debtor_id=r["debtor_id"],
            collateral_type=r.get("collateral_type", "unknown"),
            status=r.get("status", "unknown"),
            filing_date=r.get("filing_date"),
            expiry_date=r.get("expiry_date"),
            secured_party=r.get("secured_party"),
            raw_ref=f"raw:registry:{r['filing_id']}",
        )
        for r in raw
    ]
