from __future__ import annotations

import math
from collections import Counter, defaultdict
from datetime import date
from statistics import median

from app.models.schemas import BankTransaction, Invoice, RegistryFiling


def _monthly_sum(values: list[tuple[date, float]]) -> list[float]:
    by_month = defaultdict(float)
    for d, amount in values:
        by_month[(d.year, d.month)] += amount
    return sorted(by_month.values())


def _cv(nums: list[float]) -> float:
    if not nums:
        return 1.0
    m = sum(nums) / len(nums)
    if m == 0:
        return 1.0
    variance = sum((x - m) ** 2 for x in nums) / len(nums)
    return (variance**0.5) / m


def _hhi(counter: Counter) -> float:
    total = sum(counter.values())
    if total == 0:
        return 1.0
    return sum((v / total) ** 2 for v in counter.values())


def build_signals(product: str, invoices: list[Invoice], txns: list[BankTransaction], registry: list[RegistryFiling], registry_status: str, borrower_tax_id: str, half_life_days: int = 60) -> dict:
    sales = [i for i in invoices if i.kind == "sale"]
    purchases = [i for i in invoices if i.kind == "purchase"]
    credits = [i for i in invoices if i.kind == "credit_note"]
    inflows = [t for t in txns if t.direction == "in"]

    sales_total = sum(i.amount for i in sales)
    inflow_total = sum(t.amount for t in inflows)
    sales_monthly = _monthly_sum([(i.issue_date, i.amount) for i in sales])
    inflow_monthly = _monthly_sum([(t.timestamp.date(), t.amount) for t in inflows])

    buyer_counter = Counter(i.receiver_id for i in sales)
    supplier_counter = Counter(i.issuer_id for i in purchases)

    now = date.today()
    eligible_purchases = sum(i.amount * math.exp(-((now - i.issue_date).days) / half_life_days) for i in purchases)

    sev_map = {"none": 0.0, "unknown": 0.5, "receivables": 0.7, "inventory": 0.7, "all_assets": 0.9}
    severity = 0.0
    if registry_status != "ok":
        severity = 0.5
    for filing in registry:
        severity = max(severity, sev_map.get(filing.collateral_type, 0.5))

    sales_match = [i for i in sales if i.issuer_id == borrower_tax_id]
    purchase_match = [i for i in purchases if i.receiver_id == borrower_tax_id]

    signals = {
        "sales_total_window": sales_total,
        "inflows_total_window": inflow_total,
        "cash_realization_ratio": (inflow_total / sales_total) if sales_total > 0 else 0.0,
        "sales_volatility": _cv(sales_monthly),
        "inflow_volatility": _cv(inflow_monthly),
        "buyer_concentration": _hhi(buyer_counter),
        "supplier_concentration": _hhi(supplier_counter),
        "reversal_rate_sales": (sum(c.amount for c in credits) / sales_total) if sales_total else 0.0,
        "reversal_rate_purchases": (sum(c.amount for c in credits) / sum(i.amount for i in purchases)) if purchases else 0.0,
        "inventory_freshness_score": eligible_purchases,
        "encumbrance_severity": min(1.0, max(0.0, severity)),
        "invoice_months": len(set((i.issue_date.year, i.issue_date.month) for i in invoices)),
        "bank_months": len(set((t.timestamp.year, t.timestamp.month) for t in txns)),
        "identity_match_ratio": ((len(sales_match) + len(purchase_match)) / max(1, len(sales) + len(purchases))),
    }

    if product == "RBF":
        signals["capacity_base"] = median(inflow_monthly) if inflow_monthly else 0.0
    else:
        signals["capacity_base"] = min(eligible_purchases, (median(inflow_monthly) if inflow_monthly else 0.0) * 3)
    return signals
