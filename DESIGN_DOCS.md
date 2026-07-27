# Design Docs — Alternative Failure Risks Considered

> **TODO(domain):** this file is easiest to fill in *after* the domain is
> picked, since several risks are domain-flavored. The 6 primary failure
> modes (one per student) are listed first as reference; add the remaining
> 13 risks your team actually discussed, even ones you decided NOT to build
> a guardrail for — explain why not.

## 1. Architecture Recap

- **Coordinator + 4 Workers** topology (see `main_system.py` for the graph).
- State passed between every node exclusively through `contract.py`'s `AgentState`.
- 6 guardrail layers, one per student — see `README.md` ownership table.

## 2. Primary Failure Modes (one per student)

| # | Failure Mode | Node | Guardrail Summary |
|---|---|---|---|
| 1 | Infinite Graph Loops | Coordinator | Hard `round_number >= 5` circuit breaker → forced route to degraded report |
| 2 | Silent Hallucination | Worker A | `.with_structured_output()` + one automated self-correcting retry on schema error |
| 3 | Rogue Tool Execution | Worker B | Tool-call whitelist matrix checked before execution; throws `InvalidToolCallException` on violation |
| 4 | Downstream Cascade Failure | Validator node | Explicit sanitize/assert node between Worker B and Worker C; rejects + rolls back on invariant failure |
| 5 | Data Privacy Leak (Telemetry) | Global tracing layer | Redaction interceptor scrubs PII/secrets before LangSmith ingestion |
| 6 | Context Window Explosion | Global context layer | Token-threshold check + summarization/pruning before each loop transition |

## 3. Additional Failure Risks Considered (fill in ~13 more)

For each: what could go wrong, why it matters for **this domain**, and
whether the team built a guardrail for it or explicitly decided not to
(and why — usually "out of scope for this assignment" or "covered by an
existing guardrail" is a fine answer).

| # | Risk | Domain-Specific Manifestation | Mitigated? | Notes |
|---|---|---|---|---|
| 7 | TODO | TODO | Yes / No | TODO |
| 8 | TODO | TODO | Yes / No | TODO |
| 9 | TODO | TODO | Yes / No | TODO |
| 10 | TODO | TODO | Yes / No | TODO |
| 11 | TODO | TODO | Yes / No | TODO |
| 12 | TODO | TODO | Yes / No | TODO |
| 13 | TODO | TODO | Yes / No | TODO |
| 14 | TODO | TODO | Yes / No | TODO |
| 15 | TODO | TODO | Yes / No | TODO |
| 16 | TODO | TODO | Yes / No | TODO |
| 17 | TODO | TODO | Yes / No | TODO |
| 18 | TODO | TODO | Yes / No | TODO |
| 19 | TODO | TODO | Yes / No | TODO |

Ideas to consider pulling from (delete what doesn't apply once domain is picked):
- Prompt injection via untrusted tool/API output re-entering the LLM context
- Coordinator routing to a dead/removed node after refactor (graph integrity)
- Race conditions if any nodes are parallelized
- Stale/cached LLM structured-output schema drifting from `contract.py`
- Cost blowup from retries compounding with loop guardrail near the round limit
- Tool call with valid name but out-of-range/adversarial argument values
- Partial state corruption if a node crashes mid-write
- Non-determinism making `test_failure.py` repro scripts flaky
- Over-redaction in the privacy layer silently destroying legitimate data the report needs
- Human-in-the-loop bypass — no approval gate before a destructive-sounding action
- Model refusal / empty completion treated as a valid result downstream
- Versioning drift between `contract.py` and a node that wasn't updated after a team review
- Multi-tenant state bleed if the orchestrator is ever run concurrently for two users

## 4. Contract Design Rationale

TODO(team): document why `contract.py` is shaped the way it is once it's
extended and frozen — e.g. why domain-specific content should probably stay
inside `analysis_payload: Dict[str, Any]` rather than as typed top-level
fields, so the frozen contract doesn't need to change per domain.
