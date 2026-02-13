from app.main import create_underwrite, get_underwrite
from app.models.schemas import UnderwriteRequest
from app.services import underwriting


def _payload(product="RBF", requested=50000, registry_id="registry-ok"):
    return {
        "application_id": "app-1",
        "borrower": {"legal_name": "Demo", "tax_id": "TAX-1", "country_code": "AO"},
        "product_type": product,
        "requested_amount": requested,
        "currency": "AOA",
        "connections": {
            "einvoice_connection_id": "einv",
            "bank_connection_id": "bank",
            "processor_connection_id": None,
            "registry_connection_id": registry_id,
        },
        "time_window": {"months_invoices": 12, "months_bank": 6},
    }


def test_rbf_happy_path():
    run = create_underwrite(_payload("RBF", 20000))
    decision = get_underwrite(run.underwrite_run_id)
    assert decision["status"] in {"recommendation", "manual_review_required"}
    assert decision["risk"]["R"] >= 0
    assert "recommended_limit" in decision["terms"]


def test_ibf_happy_path():
    run = create_underwrite(_payload("IBF", 30000))
    decision = get_underwrite(run.underwrite_run_id)
    assert decision["terms"]["recommended_ltv"] > 0
    assert decision["terms"]["recommended_facility_size"] >= 0


def test_registry_lien_tightens_terms_and_control_required():
    run = create_underwrite(_payload("RBF", 20000, "registry-ok"))
    decision = get_underwrite(run.underwrite_run_id)
    assert decision["controls"]["requires_controlled_account"] is True
    assert "registry_limit_multiplier" in decision["policy"]["multipliers_applied"]


def test_registry_unavailable_manual_review_over_threshold():
    run = create_underwrite(_payload("RBF", 60000, "unavailable"))
    decision = get_underwrite(run.underwrite_run_id)
    assert decision["status"] == "manual_review_required"
    assert "manual_review_registry_unavailable" in decision["flags"]


def test_low_data_reject(monkeypatch):
    class LowBank:
        def fetch(self, connection_id: str):
            return [{"txn_id": "t1", "timestamp": "2026-01-01T00:00:00", "amount": 10, "currency": "AOA", "direction": "in"}]

    monkeypatch.setattr(underwriting, "BankProvider", lambda: LowBank())
    run = create_underwrite(_payload("RBF", 20000))
    decision = get_underwrite(run.underwrite_run_id)
    assert decision["status"] == "reject"
    assert "insufficient_data_months" in decision["flags"]


def test_identity_mismatch_reject(monkeypatch):
    class BadEInvoice:
        def fetch(self, connection_id: str, tax_id: str):
            return [{"invoice_id": "x1", "kind": "sale", "issuer_id": "OTHER", "receiver_id": "buyer", "issue_date": "2026-01-01", "amount": 100, "currency": "AOA", "status": "issued"}]

    monkeypatch.setattr(underwriting, "EInvoiceProvider", lambda: BadEInvoice())
    run = create_underwrite(_payload("RBF", 20000))
    decision = get_underwrite(run.underwrite_run_id)
    assert decision["status"] == "reject"
    assert "identity_mismatch" in decision["flags"]


def test_determinism_same_inputs_same_output(monkeypatch):
    monkeypatch.setattr("app.core.engine.uuid4", lambda: "fixed-run-id")
    req = UnderwriteRequest.model_validate(_payload("RBF", 20000))
    r1 = underwriting.run_underwriting(req)
    r2 = underwriting.run_underwriting(req)
    assert r1 == r2
