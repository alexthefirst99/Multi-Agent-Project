# Metrics — Quynh — Infinite Graph Loops

## Reproduction setup

`python student_1_loop/test_failure.py` uses a deterministic Validator fixture that always requests rollback. The unguarded path is observed for 25 rounds and then stopped by the demonstration harness so the script itself cannot hang. The guarded path imports the production Coordinator and loop guard from `orchestrator/`.

The token comparison uses the assignment's documented fixed estimate of 1,200 tokens per Coordinator cycle:

```text
estimated_tokens = observed_rounds × 1,200
```

## Measured before-and-after result

| Metric | Without guardrail | With guardrail |
|---|---:|---:|
| Observed Coordinator rounds | 25 and still active | 5 and terminated |
| Deterministic termination rate | 0% | 100% |
| Final route | Worker A / Analyzer | Worker D / Reporter |
| Degraded partial output | No | Yes |
| Typed `round_limit_reached` errors | 0 | 1 |
| Estimated tokens | 30,000 | 6,000 |
| Estimated token reduction | — | 80.0% |

The guarded run preserves existing state, records all five routing decisions, emits one explicit non-recoverable round-limit error, and routes to a partial Reporter output without executing a sixth worker cycle.
