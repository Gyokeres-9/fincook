# AI Instructions

## Setup
- Create a virtual env and install dependencies: `pip install -e .[dev]`

## Run
- Start API: `uvicorn app.main:app --reload`

## Test
- Run unit + acceptance tests: `pytest -q`

## Notes
- Policy is configuration-first. Avoid hard-coding thresholds.
- Keep underwriting deterministic for same snapshots + policy version.
