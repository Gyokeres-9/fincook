from __future__ import annotations

import math
from uuid import uuid4

from app.models.schemas import DecisionStatus


def clip01(x: float) -> float:
    return max(0.0, min(1.0, x))


def curve(x: float, cfg: dict) -> float:
    family = cfg.get("family", "logistic")
    if family == "exponential":
        k = cfg.get("k", 1.0)
        return clip01(1 - math.exp(-k * x))
    a = cfg.get("a", 6.0)
    b = cfg.get("b", 0.5)
    return clip01(1 / (1 + math.exp(-a * (x - b))))


def normalize_risk(signals: dict, policy: dict) -> tuple[float, dict]:
    def low_worse(x: float, p10: float, p50: float) -> float:
        return clip01((p50 - x) / max(1e-9, (p50 - p10)))

    def high_worse(x: float, p50: float, p90: float) -> float:
        return clip01((x - p50) / max(1e-9, (p90 - p50)))

    # cold-start defaults
    rc = {
        "cash_realization": low_worse(signals.get("cash_realization_ratio", 0), 0.5, 0.9),
        "inflow_volatility": high_worse(signals.get("inflow_volatility", 1), 0.2, 1.0),
        "buyer_concentration": high_worse(signals.get("buyer_concentration", 1), 0.3, 0.8),
        "supplier_concentration": high_worse(signals.get("supplier_concentration", 1), 0.3, 0.8),
        "reversal_rate_sales": high_worse(signals.get("reversal_rate_sales", 0), 0.02, 0.2),
        "registry": signals.get("encumbrance_severity", 0.5),
        "data_quality": low_worse(min(signals.get("invoice_months", 0), signals.get("bank_months", 0)), 1, 6),
    }
    weights = policy["risk_weights"]
    r = 0.0
    for k, w in weights.items():
        r += w * rc.get(k, 0.0)
    return clip01(r), rc


def underwrite(application_id: str, product_type: str, currency: str, requested_amount: float, signals: dict, policy: dict, registry_status: str, findings: list[dict]) -> dict:
    run_id = str(uuid4())
    min_data_months = policy["windows"]["min_data_months"]
    flags: list[str] = []

    if signals.get("identity_match_ratio", 0) < 0.6:
        return {
            "underwrite_run_id": run_id,
            "application_id": application_id,
            "product_type": product_type,
            "status": DecisionStatus.reject.value,
            "terms": {},
            "controls": {"requires_controlled_account": False, "requires_payment_redirection": False, "lock_parameters": {}},
            "risk": {"R": 1.0, "components": {}, "signals": signals},
            "policy": {"policy_version": policy["policy_version"], "curves": {}, "clamps_applied": [], "multipliers_applied": []},
            "flags": ["identity_mismatch"],
            "registry": {"status": registry_status, "findings_summary": findings},
            "top_drivers": [],
            "data_coverage": {"invoice_months": signals["invoice_months"], "bank_months": signals["bank_months"], "processor_connected": False, "registry_checked": registry_status == "ok"},
            "audit_refs": {"raw_snapshot_refs": [], "normalized_dataset_ref": "norm:in-memory"},
        }

    if signals["invoice_months"] < min_data_months or signals["bank_months"] < min_data_months:
        return {
            "underwrite_run_id": run_id,
            "application_id": application_id,
            "product_type": product_type,
            "status": DecisionStatus.reject.value,
            "terms": {},
            "controls": {"requires_controlled_account": False, "requires_payment_redirection": False, "lock_parameters": {}},
            "risk": {"R": 1.0, "components": {}, "signals": signals},
            "policy": {"policy_version": policy["policy_version"], "curves": {}, "clamps_applied": [], "multipliers_applied": []},
            "flags": ["insufficient_data_months"],
            "registry": {"status": registry_status, "findings_summary": findings},
            "top_drivers": [],
            "data_coverage": {"invoice_months": signals["invoice_months"], "bank_months": signals["bank_months"], "processor_connected": False, "registry_checked": registry_status == "ok"},
            "audit_refs": {"raw_snapshot_refs": [], "normalized_dataset_ref": "norm:in-memory"},
        }

    R, comps = normalize_risk(signals, policy)
    bounds = policy["bounds"]
    curves = policy["curves"]

    h_vol = 1 - curve(signals["inflow_volatility"], policy["capacity"]["volatility_haircut_curve"])
    capacity = signals["capacity_base"] * max(0.2, h_vol)

    clamped = []
    multipliers = []
    if product_type == "RBF":
        limit_base = capacity * policy["capacity"]["limit_capacity_multiplier_max"]
        rec_limit = limit_base * (1 - curve(R, curves["limit"]))
        rec_limit = max(bounds["limit"]["min"], min(bounds["limit"]["max"], rec_limit))
        rec_tenor = int(bounds["tenor_days"]["max"] - (bounds["tenor_days"]["max"] - bounds["tenor_days"]["min"]) * curve(R, curves["tenor"]))
        sweep_input = curves["sweep"].get("alpha", 0.7) * R + curves["sweep"].get("beta", 0.3) * comps["inflow_volatility"]
        rec_sweep = bounds["sweep_pct"]["min"] + (bounds["sweep_pct"]["max"] - bounds["sweep_pct"]["min"]) * curve(sweep_input, curves["sweep"])
        rec_rate = bounds["rate_apr"]["min"] + (bounds["rate_apr"]["max"] - bounds["rate_apr"]["min"]) * curve(R, curves["rate"])
        ltv = 0.0
        fac = 0.0
    else:
        ltv = bounds["ltv_pct"]["max"] - (bounds["ltv_pct"]["max"] - bounds["ltv_pct"]["min"]) * curve(R, curves["ltv"])
        fac = signals["inventory_freshness_score"] * ltv
        rec_limit = 0.0
        rec_tenor = int(bounds["tenor_days"]["max"] - (bounds["tenor_days"]["max"] - bounds["tenor_days"]["min"]) * curve(R, curves["tenor"]))
        rec_sweep = bounds["sweep_pct"]["min"] + (bounds["sweep_pct"]["max"] - bounds["sweep_pct"]["min"]) * curve(R, curves["sweep"])
        rec_rate = bounds["rate_apr"]["min"] + (bounds["rate_apr"]["max"] - bounds["rate_apr"]["min"]) * curve(R, curves["rate"])

    severity = signals["encumbrance_severity"]
    lcfg = policy.get("registry", {})
    if severity > 0:
        lm = lcfg.get("multipliers", {}).get("limit", {"min": 0.5, "max": 1.0})
        mul = lm["max"] - (lm["max"] - lm["min"]) * severity
        rec_limit *= mul
        fac *= mul
        multipliers.append("registry_limit_multiplier")

    min_sweep = 0.0
    for item in lcfg.get("min_sweep_by_severity", []):
        if severity >= item["severity_gte"]:
            min_sweep = max(min_sweep, item["min_sweep"])
    if rec_sweep < min_sweep:
        rec_sweep = min_sweep
        clamped.append("min_sweep_by_registry")

    status = DecisionStatus.recommendation
    if requested_amount > policy.get("manual_review", {}).get("exposure_over", 10**18):
        status = DecisionStatus.manual_review_required
        flags.append("manual_review_exposure")
    if registry_status in {"unavailable", "error"} and requested_amount > policy.get("manual_review", {}).get("registry_unavailable_over", 10**18):
        status = DecisionStatus.manual_review_required
        flags.append("manual_review_registry_unavailable")

    if lcfg.get("hard_reject_conflict") and any(f.get("collateral_type") == "receivables" and f.get("status") == "active" and f.get("notes") == "same_receivable_conflict" for f in findings):
        status = DecisionStatus.reject
        flags.append("hard_reject_registry_conflict")

    components = {
        "cashflow": comps.get("cash_realization", 0.0),
        "concentration": max(comps.get("buyer_concentration", 0.0), comps.get("supplier_concentration", 0.0)),
        "reversals": comps.get("reversal_rate_sales", 0.0),
        "registry": comps.get("registry", 0.0),
        "data_quality": comps.get("data_quality", 0.0),
    }

    return {
        "underwrite_run_id": run_id,
        "application_id": application_id,
        "product_type": product_type,
        "status": status.value,
        "terms": {
            "currency": currency,
            "recommended_limit": round(rec_limit, 2),
            "recommended_facility_size": round(fac, 2),
            "recommended_ltv": round(ltv, 4),
            "recommended_tenor_days": rec_tenor,
            "recommended_rate_apr": round(rec_rate, 4),
            "recommended_repayment_cycle": "weekly",
            "recommended_sweep_pct": round(rec_sweep, 4),
            "recommended_reserve_buffer_days": 7,
        },
        "controls": {
            "requires_controlled_account": severity > 0 or registry_status != "ok",
            "requires_payment_redirection": severity >= 0.7,
            "lock_parameters": {"max_daily_draw_pct": 0.2},
        },
        "risk": {"R": round(R, 4), "components": components, "signals": signals},
        "policy": {
            "policy_version": policy["policy_version"],
            "curves": {
                "g_limit": curve(R, curves.get("limit", curves.get("ltv", {"family": "logistic"}))),
                "g_ltv": curve(R, curves.get("ltv", {"family": "logistic"})),
                "g_tenor": curve(R, curves.get("tenor", {"family": "logistic"})),
                "g_sweep": curve(R, curves.get("sweep", {"family": "logistic"})),
                "g_rate": curve(R, curves.get("rate", {"family": "logistic"})),
            },
            "clamps_applied": clamped,
            "multipliers_applied": multipliers,
        },
        "flags": flags,
        "registry": {"status": registry_status, "findings_summary": findings},
        "top_drivers": [
            {"name": "inflow_volatility", "direction": "worsens", "impact": "high", "evidence": f"{signals['inflow_volatility']:.2f}"},
            {"name": "encumbrance_severity", "direction": "worsens", "impact": "med", "evidence": f"{severity:.2f}"},
        ],
        "data_coverage": {
            "invoice_months": signals["invoice_months"],
            "bank_months": signals["bank_months"],
            "processor_connected": False,
            "registry_checked": registry_status == "ok",
        },
        "audit_refs": {
            "raw_snapshot_refs": ["raw:einvoice", "raw:bank", "raw:registry"],
            "normalized_dataset_ref": "norm:in-memory",
        },
    }
