"""
Student 5 — Global Graph Layer (Tracing & Privacy)
Critical Failure Mode: Data Privacy Leak via Telemetry

The Failure: The system correctly streams executions to LangSmith for
tracking, but unintentionally leaks raw API keys, corporate database names,
or user PII to cloud telemetry storage.

The Guardrail: Build a centralized State Redaction Interceptor.
Programmatically scrub sensitive keys or match regular expressions for
high-risk strings within the graph payload metadata before sending tracing
logs to LangSmith or alternative external logging endpoints.

TODO: implement the redaction interceptor here.
"""


def redact_payload(payload):
    raise NotImplementedError("TODO: recursively scrub PII/secrets from `payload` before it reaches tracing.")
