from __future__ import annotations

from app.core.policy import validate_policy
from app.data.store import STORE
from app.models.schemas import UnderwriteRequest, UnderwriteRunResponse
from app.services.underwriting import run_underwriting


def health() -> dict:
    return {"status": "ok"}


def create_underwrite(req_payload: dict) -> UnderwriteRunResponse:
    req = UnderwriteRequest.model_validate(req_payload)
    result = run_underwriting(req)
    STORE.runs[result["underwrite_run_id"]] = result
    return UnderwriteRunResponse(underwrite_run_id=result["underwrite_run_id"], status="complete")


def get_underwrite(underwrite_run_id: str) -> dict:
    if underwrite_run_id not in STORE.runs:
        raise KeyError("underwrite_run_id not found")
    return STORE.runs[underwrite_run_id]


def policy_validate(policy: dict) -> dict:
    ok, errors = validate_policy(policy)
    return {"valid": ok, "errors": errors}
