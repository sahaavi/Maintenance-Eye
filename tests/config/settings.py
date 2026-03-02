from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class TestSettings:
    test_env: str
    app_env: str
    base_url: str
    ws_base_url: str
    coverage_fail_under: int
    e2e_timeout_ms: int


def _load_env_file() -> None:
    env_name = os.getenv("TEST_ENV", "dev")
    root = Path(__file__).resolve().parents[2]
    env_path = root / f".env.test.{env_name}"
    if not env_path.exists():
        return

    for line in env_path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip())


_load_env_file()

SETTINGS = TestSettings(
    test_env=os.getenv("TEST_ENV", "dev"),
    app_env=os.getenv("APP_ENV", "testing"),
    base_url=os.getenv("TEST_BASE_URL", "http://127.0.0.1:8080"),
    ws_base_url=os.getenv("TEST_WS_BASE_URL", "ws://127.0.0.1:8080"),
    coverage_fail_under=int(os.getenv("TEST_COVERAGE_FAIL_UNDER", "85")),
    e2e_timeout_ms=int(os.getenv("E2E_TIMEOUT_MS", "15000")),
)
