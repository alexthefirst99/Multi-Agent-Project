"""Deterministic telemetry privacy-leak failure reproduction."""

from __future__ import annotations

import sys
from copy import deepcopy
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from snippet import MemoryTraceSink, SafeTracer

PAYLOAD = {
    "email": "alice@example.com",
    "ssn": "123-45-6789",
    "metadata": {
        "api_key": "sk-super-secret-value",
        "database": "production-db-payments",
    },
}


def main() -> None:
    unsafe_sink = MemoryTraceSink()
    unsafe_sink.record("unsafe", inputs=PAYLOAD, outputs={})
    unsafe_serialized = repr(unsafe_sink.records)
    unsafe_leaks = sum(
        secret in unsafe_serialized
        for secret in (
            "alice@example.com",
            "123-45-6789",
            "sk-super-secret-value",
            "production-db-payments",
        )
    )

    original = deepcopy(PAYLOAD)
    safe_sink = MemoryTraceSink()
    result = SafeTracer(safe_sink).record("safe", inputs=PAYLOAD, outputs={})
    safe_serialized = repr(safe_sink.records)
    safe_leaks = sum(
        secret in safe_serialized
        for secret in (
            "alice@example.com",
            "123-45-6789",
            "sk-super-secret-value",
            "production-db-payments",
        )
    )

    print("=== WITHOUT GUARDRAIL ===")
    print(f"Sensitive values leaked to telemetry: {unsafe_leaks}/4")

    print("\n=== WITH GUARDRAIL ===")
    print(f"Sensitive values leaked to telemetry: {safe_leaks}/4")
    print(f"Redactions applied: {result.redaction_count}")
    print(f"Authoritative payload mutated: {PAYLOAD != original}")

    print("\n=== METRICS ===")
    print("Sensitive-value leak rate: 100% -> 0%")
    print("Authoritative-state mutation: 0")

    assert unsafe_leaks == 4
    assert safe_leaks == 0
    assert PAYLOAD == original


if __name__ == "__main__":
    main()
