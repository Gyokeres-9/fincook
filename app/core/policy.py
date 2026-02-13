from __future__ import annotations

import json
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[2]


def load_policy(country_code: str, product_type: str) -> dict:
    path = BASE_DIR / "policies" / f"{country_code}_{product_type}.json"
    if not path.exists():
        raise FileNotFoundError(f"policy not found for {country_code}/{product_type}")
    return json.loads(path.read_text())


def validate_policy(policy: dict) -> tuple[bool, list[str]]:
    errors: list[str] = []
    for key in ["policy_version", "country_code", "product_type", "windows", "bounds", "curves", "risk_weights"]:
        if key not in policy:
            errors.append(f"missing {key}")
    if "bounds" in policy and "rate_apr" in policy["bounds"]:
        r = policy["bounds"]["rate_apr"]
        if r["min"] > r["max"]:
            errors.append("bounds.rate_apr min > max")
    return len(errors) == 0, errors
