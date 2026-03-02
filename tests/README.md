# Maintenance-Eye Test System

## Goals
This test system enforces production-grade quality for backend services, API contracts, agent safety controls, frontend user journeys, and operational guardrails.

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
Test behavior is profile-driven through `.env.test.dev`, `.env.test.staging`, `.env.test.prod`.

- `TEST_ENV=dev`: fast local feedback
- `TEST_ENV=staging`: pre-release validation profile
- `TEST_ENV=prod`: production-like strict profile (auth enabled)

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
python -m pytest -m "unit or integration or api"
python -m pytest -m "security or ai or data"
python -m pytest -m "performance"
python -m pytest -m "e2e"
```

## Quality Gates
- Coverage threshold: `85%` minimum (hard fail)
- Linting: Ruff
- Formatting: Black (`--check` in CI)
- Type checks: MyPy
- SAST: Bandit
- Dependency vulnerability scan: pip-audit

## Determinism Strategy
- All tests isolate external dependencies by default through `FakeEAM` fixtures.
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

## Updating Drift Baseline
When seed data intentionally changes, refresh `tests/data/drift_baseline.json` with reviewed distributions and include rationale in PR notes.
