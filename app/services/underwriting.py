from __future__ import annotations

from app.adapters.providers import BankProvider, EInvoiceProvider, RegistryProvider
from app.core.engine import underwrite
from app.core.normalization import normalize_bank, normalize_invoices, normalize_registry
from app.core.policy import load_policy
from app.core.signals import build_signals


def run_underwriting(req) -> dict:
    e = EInvoiceProvider()
    b = BankProvider()
    r = RegistryProvider()

    raw_inv = e.fetch(req.connections.einvoice_connection_id, req.borrower.tax_id)
    raw_bank = b.fetch(req.connections.bank_connection_id)
    registry_status, raw_registry = r.fetch(req.connections.registry_connection_id, req.borrower.tax_id)

    invoices = normalize_invoices(raw_inv)
    txns = normalize_bank(raw_bank)
    filings = normalize_registry(raw_registry)

    policy = load_policy(req.borrower.country_code, req.product_type.value)
    signals = build_signals(req.product_type.value, invoices, txns, filings, registry_status, req.borrower.tax_id, policy.get("inventory_freshness_half_life_days", 60))

    findings = [{"filing_id": f.filing_id, "collateral_type": f.collateral_type, "status": f.status} for f in filings]

    return underwrite(
        req.application_id,
        req.product_type.value,
        req.currency,
        req.requested_amount,
        signals,
        policy,
        registry_status,
        findings,
    )
