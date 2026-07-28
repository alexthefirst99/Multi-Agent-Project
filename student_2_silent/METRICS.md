# Metrics — Structured Output — Silent Hallucination

Measured by `python student_2_silent/test_failure.py` using scripted model responses, not live LLM behavior.

| Metric | Without guardrail | With guardrail |
|---|---:|---:|
| Missing-ticker payloads accepted | 1 / 1 | 0 / 1 |
| Invalid payload acceptance rate | 100% | 0% |
| Correction retries | Undefined | Exactly 1 |
| Double schema failure surfaced explicitly | No | Yes |
| Model calls on double failure | Unbounded/undefined | 2 maximum |
