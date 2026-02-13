# Underwriting Engine (RBF + IBF)

Config-driven underwriting API with deterministic runs and audit-oriented outputs.

## Repo structure

- `app/main.py` - FastAPI endpoints
- `app/services/underwriting.py` - orchestration pipeline
- `app/adapters/providers.py` - provider interfaces + stubs
- `app/core/normalization.py` - canonical normalization
- `app/core/signals.py` - signal computation for RBF/IBF
- `app/core/engine.py` - risk normalization + policy-driven terms
- `policies/*.json` - country/product policy configs
- `tests/test_acceptance.py` - acceptance tests
- `AGENTS.md` - AI instructions

## Commands

```bash
pip install -e .[dev]
pytest -q
uvicorn app.main:app --reload
```
