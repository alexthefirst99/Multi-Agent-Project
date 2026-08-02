# Metrics — Zainab — Telemetry Leak

Measured by `python student_5_trace/test_failure.py` using an in-memory trace sink.

| Metric | Without guardrail | With guardrail |
|---|---:|---:|
| Sensitive values leaked | 4 / 4 | 0 / 4 |
| Sensitive-value leak rate | 100% | 0% |
| Redactions applied | 0 | 4 |
| Authoritative payload mutations | 0 | 0 |
| Payload categories tested | Email, SSN, API key, production database identifier | Same |
