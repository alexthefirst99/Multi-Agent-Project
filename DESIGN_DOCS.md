# Design Docs — Nineteen Failure Risks Considered

## Architecture Summary

The system is a stateful LangGraph financial-trading orchestrator with one Coordinator and four Workers. The Context Manager runs before each Coordinator visit. The Coordinator routes to Worker A (Analyzer), Worker B (Actor), or Worker D (Reporter); Workers A and B both pass through Worker C (Validator), which returns control to the Context Manager. Worker D terminates the graph. Root-level `contract.py` is the frozen interface, production graph code lives under `orchestrator/`, and the presentation UI lives under `app/`. Student folders are grading views, and every external action is mocked.

## Risk Register

| # | Failure risk | Trading-domain manifestation | Decision and mitigation |
|---:|---|---|---|
| 1 | Infinite graph loop | Repeated Analyzer rollback consumes tokens without reaching a report | Implemented deterministic round counter and forced degraded report at visit 5 |
| 2 | Silent hallucination / structural failure | Analyzer omits ticker or emits invalid quantity while appearing confident | Implemented Pydantic structured output and exactly one correction retry |
| 3 | Rogue tool execution | Prompt injection requests fund transfer or bypasses risk checks | Implemented registered mock-tool whitelist, permission matrix, strict arguments, bounds, and atomic batch validation |
| 4 | Downstream cascade failure | String quantity or malformed result crashes Validator arithmetic | Implemented explicit boundary sanitization, typed parsing, rejection, and rollback flags |
| 5 | Privacy leak in telemetry | Email, SSN, API key, or production database identifier reaches LangSmith | Implemented recursive non-mutating redaction and disabled automatic raw tracing |
| 6 | Context-window explosion | Repeated tool outputs and history increase latency and token spend | Implemented token measurement, obsolete-output pruning, summarization, and recent-turn retention |
| 7 | Prompt injection in market text | News text instructs the model to ignore permissions | Tool permissions remain deterministic code; untrusted text cannot register tools |
| 8 | Valid tool name with adversarial values | `execute_trade` requests zero, negative, or oversized quantity | Pydantic bounds restrict quantity to 1–1,000 and reject extra arguments |
| 9 | Partial batch execution | First trade executes before a later rogue call is detected | Entire batch is validated before the first mocked handler runs |
| 10 | Stale market data | A valid-looking signal refers to an outdated price | Not implemented; external market-data freshness is outside this assignment and all data is mocked |
| 11 | Race condition between trades | Concurrent runs modify the same portfolio | Not implemented; no shared portfolio or live side effects exist in the assignment runtime |
| 12 | Contract version drift | A branch uses old field names after a schema change | Frozen contract version, strict extra-field rejection, and contract regression tests |
| 13 | Coordinator routes to a removed node | Refactor leaves a stale conditional-edge target | Central route literals and graph topology tests verify every destination exists |
| 14 | Model refusal or empty response | Empty output is treated as a usable analysis | Structured schema rejects missing fields; second failure becomes an explicit graph error |
| 15 | Telemetry outage | LangSmith failure silently hides observability loss | Trace wrapper converts the exception into a typed recoverable `tracing_error` without corrupting business state |
| 16 | Over-redaction | Privacy filter destroys legitimate ticker or quantity data | Redaction runs on a deep copy used only for telemetry; authoritative state is unchanged |
| 17 | Context summary loses critical instructions | Pruning removes the no-real-trades safety rule | System instructions and `essential=True` messages are always retained |
| 18 | Non-deterministic failure demos | Live model variability makes grading unreliable | Every individual demo uses scripted responses, adversarial fixtures, or pure mock handlers |
| 19 | Real destructive side effect in a failure demo | A demo accidentally calls a brokerage, shell, or database | Tool registry contains only pure mock handlers; safety checks and repository review ban destructive clients |

## Contract Rationale

Stable business structures use explicit Pydantic models. Only two fields remain intentionally untrusted: raw tool requests and raw Actor results. This preserves realistic boundary testing while preventing malformed data from entering authoritative fields. `strict=True`, `extra="forbid"`, assignment validation, discriminated tool unions, explicit error models, and `Literal[5]` for the round limit make violations visible early.

## Dependency Injection

The graph receives its chat model, tool registry, token counter, summarizer, and tracer through `OrchestratorDependencies`. Tests replace each network-facing dependency with deterministic fakes. Production clients are created lazily at startup, never during import.
