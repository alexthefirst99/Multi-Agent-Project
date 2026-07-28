# Metrics — Context Management — Context Window Explosion

Measured by `python student_6_tokens/test_failure.py` with the deterministic approximate token counter.

| Metric | Without guardrail | With guardrail |
|---|---:|---:|
| Messages retained | 14 | 3 |
| Estimated input tokens | 1,729 | 122 |
| Estimated token reduction | — | 92.9% |
| Older messages summarized | 0 | 10 |
| Net messages pruned | 0 | 11 |
| Obsolete tool outputs retained | 1 | 0 |
| System instructions preserved | Yes | Yes |
