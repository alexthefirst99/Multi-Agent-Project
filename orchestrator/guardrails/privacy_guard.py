"""Privacy-safe tracing that never mutates authoritative graph state."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Protocol

from orchestrator.utils.redaction import RedactionResult, redact_payload


class TraceSink(Protocol):
    def record(
        self,
        name: str,
        *,
        inputs: Mapping[str, Any],
        outputs: Mapping[str, Any],
        metadata: Mapping[str, Any] | None = None,
    ) -> None: ...


@dataclass(frozen=True, slots=True)
class TraceRecord:
    name: str
    inputs: Mapping[str, Any]
    outputs: Mapping[str, Any]
    metadata: Mapping[str, Any]


class NullTraceSink:
    def record(
        self,
        name: str,
        *,
        inputs: Mapping[str, Any],
        outputs: Mapping[str, Any],
        metadata: Mapping[str, Any] | None = None,
    ) -> None:
        return None


class MemoryTraceSink:
    """Deterministic in-memory sink used by tests and failure demos."""

    def __init__(self) -> None:
        self.records: list[TraceRecord] = []

    def record(
        self,
        name: str,
        *,
        inputs: Mapping[str, Any],
        outputs: Mapping[str, Any],
        metadata: Mapping[str, Any] | None = None,
    ) -> None:
        self.records.append(TraceRecord(name, inputs, outputs, metadata or {}))


class LangSmithTraceSink:
    """Thin adapter around ``langsmith.Client.create_run``."""

    def __init__(self, client: Any, project_name: str) -> None:
        self._client = client
        self._project_name = project_name

    def record(
        self,
        name: str,
        *,
        inputs: Mapping[str, Any],
        outputs: Mapping[str, Any],
        metadata: Mapping[str, Any] | None = None,
    ) -> None:
        self._client.create_run(
            name=name,
            inputs=dict(inputs),
            outputs=dict(outputs),
            run_type="chain",
            project_name=self._project_name,
            extra={"metadata": dict(metadata or {})},
        )


@dataclass(frozen=True, slots=True)
class SafeTraceResult:
    redaction_count: int


class SafeTracer:
    """Redact both sides of a trace before handing them to any external sink."""

    def __init__(self, sink: TraceSink) -> None:
        self._sink = sink

    def record(
        self,
        name: str,
        *,
        inputs: Mapping[str, Any],
        outputs: Mapping[str, Any],
        metadata: Mapping[str, Any] | None = None,
    ) -> SafeTraceResult:
        clean_inputs: RedactionResult = redact_payload(inputs)
        clean_outputs: RedactionResult = redact_payload(outputs)
        clean_metadata: RedactionResult = redact_payload(metadata or {})
        self._sink.record(
            name,
            inputs=clean_inputs.payload,
            outputs=clean_outputs.payload,
            metadata=clean_metadata.payload,
        )
        return SafeTraceResult(
            clean_inputs.redaction_count
            + clean_outputs.redaction_count
            + clean_metadata.redaction_count
        )
