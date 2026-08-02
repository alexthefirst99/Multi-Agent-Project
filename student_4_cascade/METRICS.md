# Metrics — JN (Student 4) — Downstream Cascade Failure

Measured by `python student_4_cascade/test_failure.py`, a deterministic,
offline reproduction using two malformed Worker B outputs (one missing its
required `status` and `reference_id` keys, one with the prose quantity
`"ten"`) and one well-formed output.

| Metric | Without guardrail | With guardrail |
|---|---:|---:|
| Downstream Worker C crashes (`KeyError` / `TypeError`) | 2 / 2 | 0 / 2 |
| Crash rate on malformed input | 100% | 0% |
| Malformed results promoted into authoritative state | 2 / 2 | 0 / 2 |
| Graceful rollbacks (Coordinator re-routes to Analyzer) | 0 / 2 | 2 / 2 |
| Typed `malformed_actor_output` audit errors per rejection | 0 | 1 |
| Well-formed results validated and routed to the Reporter | n/a | 1 / 1 |

The guardrail is two explicit node functions at the Worker B → Worker C
boundary: `validate_sanitize_node` asserts structural invariants derived from
the frozen contract (required keys present, `status` and `tool_name` inside
the contract's allowed literal sets), then promotes survivors through the
typed `ToolExecutionResult` model; `worker_c_validator_node` cross-checks
ticker, side, and quantity against the original analysis before reporting.
