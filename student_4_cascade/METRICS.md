# Metrics — JN — Downstream Cascade Failure

Measured by `python student_4_cascade/test_failure.py` using malformed and safely coercible Actor outputs.

| Metric | Without guardrail | With guardrail |
|---|---:|---:|
| Downstream crashes from malformed quantity | 1 / 1 | 0 / 1 |
| Malformed results rejected before business logic | 0 / 1 | 1 / 1 |
| Crash rate | 100% | 0% |
| Safe string-to-integer normalization | No | Yes (`"10"` → `10`) |
| Safe ticker normalization | No | Yes (`" aapl "` → `AAPL`) |
