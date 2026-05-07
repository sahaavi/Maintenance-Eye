# Maintenance-Eye Test System

## Goals
This test system covers backend services, API contracts, agent safety controls, frontend user journeys, and operational guardrails.

Current suite size: 140 collected tests, including 92 tests under `tests/unit` and 18 browser-driven E2E tests.

## Test Architecture
- `tests/unit`: deterministic unit tests for local logic and tool behavior
- `tests/integration`: cross-module behavior (routes + managers + fakes)
- `tests/api`: API contract and regression tests
- `tests/system`: system-level boot and baseline availability checks
- `tests/e2e`: browser-driven end-to-end tests with Playwright
- `tests/performance`: latency and throughput guardrails
- `tests/security`: input hardening and controlled failure behavior
- `tests/ai`: AI quality checks (prompt robustness, consistency, bias coverage, failure modes)
- `tests/data`: referential integrity and drift-detection checks
- `tests/config`: environment-aware test runtime settings
- `tests/fixtures`: reusable deterministic factories and fakes

## Environment Profiles
`scripts/run_test_suite.sh` accepts `TEST_ENV=dev`, `TEST_ENV=staging`, or `TEST_ENV=prod` and optionally loads `.env.test.<profile>` when that file exists. Those local override files are not committed; absent files fall back to `pytest.ini`, `tests/conftest.py`, and the current shell environment.

- `TEST_ENV=dev`: fast local feedback
- `TEST_ENV=staging`: pre-release validation profile when a matching env file is provided
- `TEST_ENV=prod`: production-like local profile when a matching env file is provided

The committed automated tests force auth off so local and CI runs do not require Firebase credentials. Production auth is implemented in the backend, but it is not exercised by the default automated suite.

## Setup
```bash
./scripts/setup_test_env.sh
source .venv/bin/activate
```

## Local Execution
Run complete enterprise gate:
```bash
TEST_ENV=dev ./scripts/run_test_suite.sh
```

Run selected layers:
```bash
python -m pytest tests/unit -o "addopts="
python -m pytest -m "integration or api"
python -m pytest -m "security or ai or data"
python -m pytest -m "performance"
python -m pytest -m "e2e" --no-cov
```

## Quality Gates
- Coverage threshold: `85%` minimum for the core pytest run (hard fail)
- Linting: Ruff
- Formatting: Black (`--check` in CI)
- Type checks: MyPy
- SAST: Bandit
- Dependency vulnerability scan: pip-audit

## Determinism Strategy
- Tests isolate external dependencies by default through fakes, fixtures, JSON seed data, and mocked browser network responses.
- No live Firestore, Gemini, or Cloud Storage calls are required for standard suites.
- E2E tests mock `/api/*` network responses to avoid backend flakiness in UI smoke coverage.

## AI QA Strategy
The `tests/ai` layer validates:
- Model behavior constraints encoded in prompts
- Human-in-the-loop confirmation gating requirements
- Output consistency for repeated identical tool proposals
- Prompt robustness and short-response constraints
- Failure-mode handling for unsupported action types
- Monitoring visibility through pending-action telemetry

## Data Integrity and Drift
- Referential integrity across assets, work orders, and inspections
- Domain-value enforcement for priority and status fields
- Drift baseline checks for department and priority distributions in `seed_data.json`

## CI/CD Integration
GitHub Actions workflow: `.github/workflows/test-suite.yml`

Pipeline behavior:
- test gating on every PR and push to `main`
- quality and security auto-fail rules
- coverage + junit + security reports uploaded as build artifacts
- E2E runs with `--no-cov` because browser-only tests should not be evaluated against backend coverage.

## Updating Drift Baseline
When seed data intentionally changes, refresh `tests/data/drift_baseline.json` with reviewed distributions and include rationale in PR notes.
