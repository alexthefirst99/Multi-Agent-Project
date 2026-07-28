from __future__ import annotations

from copy import deepcopy

from orchestrator.guardrails.privacy_guard import MemoryTraceSink, SafeTracer


def test_recursive_redaction_scrubs_keys_and_patterns_without_mutation() -> None:
    payload = {
        "user": {
            "email": "alice@example.com",
            "notes": "SSN 123-45-6789 and Bearer abcdefghijklmnop",
        },
        "metadata": [
            {"api_key": "sk-super-secret-value"},
            "production-db-payments",
        ],
    }
    snapshot = deepcopy(payload)
    sink = MemoryTraceSink()
    result = SafeTracer(sink).record(
        "test",
        inputs=payload,
        outputs={"token": "di-secret-token-value"},
    )

    assert payload == snapshot
    assert result.redaction_count >= 5
    serialized = repr(sink.records[0])
    assert "alice@example.com" not in serialized
    assert "123-45-6789" not in serialized
    assert "production-db-payments" not in serialized
    assert "[REDACTED]" in serialized


def test_clean_payload_is_preserved() -> None:
    sink = MemoryTraceSink()
    payload = {"ticker": "AAPL", "quantity": 10}
    result = SafeTracer(sink).record("clean", inputs=payload, outputs={})
    assert result.redaction_count == 0
    assert sink.records[0].inputs == payload
