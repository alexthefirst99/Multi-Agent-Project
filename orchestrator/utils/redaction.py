"""Pure recursive redaction utilities."""

from __future__ import annotations

import re
from copy import deepcopy
from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from pydantic import BaseModel

REDACTED = "[REDACTED]"

_SENSITIVE_KEYS = {
    "api_key",
    "apikey",
    "authorization",
    "bearer",
    "credential",
    "database",
    "database_name",
    "db_name",
    "email",
    "password",
    "secret",
    "ssn",
    "system_identifier",
    "token",
}

_STRING_PATTERNS = (
    re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE),
    re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
    re.compile(r"\bBearer\s+[A-Za-z0-9._~+/=-]{8,}\b", re.IGNORECASE),
    re.compile(r"\b(?:sk|lsv2|di)[-_][A-Za-z0-9_-]{8,}\b", re.IGNORECASE),
    re.compile(
        r"\b(?:api[_ -]?key|token|password|secret)\s*[:=]\s*[^\s,;]+",
        re.IGNORECASE,
    ),
    re.compile(r"\b(?:prod|production)[-_](?:db|database)[-_][A-Za-z0-9_-]+\b", re.IGNORECASE),
)


@dataclass(frozen=True, slots=True)
class RedactionResult:
    payload: Any
    redaction_count: int


def _redact_string(value: str) -> tuple[str, int]:
    redacted = value
    count = 0
    for pattern in _STRING_PATTERNS:
        redacted, substitutions = pattern.subn(REDACTED, redacted)
        count += substitutions
    return redacted, count


def redact_payload(payload: Any) -> RedactionResult:
    """Return a redacted deep copy without mutating the authoritative payload."""
    source = (
        payload.model_dump(mode="json")
        if isinstance(payload, BaseModel)
        else deepcopy(payload)
    )

    def visit(value: Any) -> tuple[Any, int]:
        if isinstance(value, BaseModel):
            return visit(value.model_dump(mode="json"))
        if isinstance(value, Mapping):
            output: dict[str, Any] = {}
            total = 0
            for key, nested in value.items():
                key_text = str(key)
                if key_text.lower() in _SENSITIVE_KEYS:
                    output[key_text] = REDACTED
                    total += 1
                else:
                    output[key_text], nested_count = visit(nested)
                    total += nested_count
            return output, total
        if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
            output_items: list[Any] = []
            total = 0
            for item in value:
                clean_item, item_count = visit(item)
                output_items.append(clean_item)
                total += item_count
            return output_items, total
        if isinstance(value, str):
            return _redact_string(value)
        return value, 0

    clean, count = visit(source)
    return RedactionResult(clean, count)
