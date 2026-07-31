# Anh — Structured-Output Guardrail Metrics

Measured with `python student_2_silent/test_failure.py`. The fixture uses
scripted in-memory model responses and the production Worker A node; it makes no
network request and performs no real trade.

| Metric | Without guardrail | With guardrail |
|---|---:|---:|
| Required `AnalysisPayload` schema requested | 0 / 1 | 1 / 1 |
| Missing-ticker payloads accepted | 1 / 1 (100%) | 0 / 1 (0%) |
| Validation error returned to the model | 0 / 1 | 1 / 1 |
| Automated self-correction attempts | 0 | 1 maximum |
| Model calls before the Analyzer returns | 1 | 2 maximum |
| Invalid model outputs returned as `analysis_payload` | 1 / 1 | 0 / 2 |
| Explicit `analysis_schema_error` flags after both attempts fail | 0 / 1 | 1 / 1 |
| Stale downstream payload groups retained after an invalid response | 2 / 2 | 0 / 2 |

The guarded recovery fixture receives an invalid response first and a valid
response second. It recovers ticker `AAPL` after one retry. A separate fixture
returns two invalid responses plus an unused third valid response; the third is
never called, proving the retry cap.

## Two-minute recording runbook

1. Show that `INVALID` omits `ticker`, then run the command above.
2. Explain the unguarded `1/1` acceptance result.
3. Point to `.with_structured_output(AnalysisPayload)` in Worker A and the
   exactly-one-retry wrapper.
4. Show recovery after one retry, then the double-failure
   `analysis_schema_error=True` result with `analysis_payload=None`.
5. Close on the measured `100% -> 0%` invalid-payload acceptance change.
