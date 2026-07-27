# Generic Task Orchestrator — Financial Trading Bot — [TODO: GROUP 2]

A LangGraph multi-agent system with one Coordinator node dynamically routing
execution across four specialized Worker nodes (Analyzer, Actor, Validator,
Reporter), guarded by six independent, code-based guardrails — one per
critical failure mode (infinite loops, silent hallucinations, rogue tool
execution, downstream cascade failures, data privacy leaks, and context
window explosion). Instantiated against a **Financial Trading Bot** domain:
Market Analysis → Trade Execution → Risk/Compliance Check → Audit Logging.

All trades, tickers, and account data in this repo are fictional and mocked.
Per the assignment's Strict Safety Mandate, nothing in this repo ever calls a
real brokerage API or executes a real trade — see [Strict Safety
Mandate](#-strict-safety-mandate-non-negotiable) below.

> **Status:** domain confirmed, contract still a draft (not yet frozen).
> Every guardrail below is a `raise NotImplementedError` stub waiting on its
> owner to implement. `main_system.py` is a topology-only stub until the
> team wires it together.

## Architecture

A central Coordinator dynamically routes execution based on state — not a
fixed, linear pipeline (see `main_system.py` for the exact wiring this
diagram maps to):

```
                  ┌──────────────────────────────┐
                  ▼                              │ (Loop / Self-Correction)
               [ 0. Coordinator Node ] ──────────┼──────────────┐
                  │              ▲               │              │
                  │ (Route A)    │ (Error Flag)  │ (Route B)    │ (Route C)
                  ▼              │               ▼              ▼
     [ 1. Worker A: Analyzer ] ──┘     [ 2. Worker B: Actor ]   [ 4. Worker D: Reporter ]
                  │                              │
                  │ (Valid Schema)               │ (Execution State)
                  ▼                              ▼
     [ 5. Worker C: Validator ] ◄────────────────┘
```

- **Coordinator** — the only node with routing authority. Every other node
  either returns to it or is reached directly from it; nothing bypasses it.
- **Route A / Route B / Route C** — the Coordinator's three possible
  forward routes, decided from `AgentState` (see `contract.py`), not
  hard-coded sequence.
- **Error Flag** — Worker A can bounce a schema-validation failure back to
  the Coordinator instead of proceeding.
- **Loop / Self-Correction** — the same edge the round-number guardrail
  (Student 1) protects: every worker's result eventually re-enters the
  Coordinator for re-evaluation, capped at 5 rounds.

## What This Looks Like When Finished

Once every guardrail is implemented and `main_system.py` is wired together,
`python main_system.py` should run one full trading decision end-to-end:

1. Take a raw market signal as input (e.g. "AAPL showing unusual volume
   spike, +4% in 10 minutes").
2. **Coordinator → Worker A:** extract a structured trade signal (ticker,
   side, quantity, confidence) — retrying once automatically if the LLM's
   structured output fails validation, never forwarding an incomplete one.
3. **Coordinator → Worker B:** validate the proposed trade against the tool
   whitelist and mock-execute it, or block it and report exactly why.
4. **Worker C:** cross-check the trade result against the original analysis
   — malformed data gets rejected here, before it can crash anything
   downstream.
5. **Terminate cleanly:** either at Worker D with a full audit-log report,
   or via the round-limit guardrail with a degraded partial report —
   never looping forever, no matter how the LLM behaves.

Running the whole way through, all six guardrails hold simultaneously:
nothing sensitive reaches the LangSmith trace unredacted, `state.messages`
never grows unbounded across rounds, and every one of the 6
`test_failure.py` scripts still demonstrates its failure mode blocked when
run in isolation. That combination — one integrated run, all 6 failure
modes provably guarded — is the actual target, not just "the code runs."

## What You Need

- Python 3.11+
- An OpenAI-compatible LLM API key (for whoever wires up the real
  `.with_structured_output()` / tool-calling LLM calls — not required to run
  any `test_failure.py` script today, since those are deterministic)
- A LangSmith API key (for Student 5's tracing/privacy guardrail and the
  final team-level trace)

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Fill in `.env`:

```env
OPENAI_API_KEY=your-openai-api-key
LANGCHAIN_TRACING_V2=true
LANGCHAIN_API_KEY=your-langsmith-api-key
LANGCHAIN_PROJECT=orchestrator-trading-bot
```

## Team & Role Assignment

| Node / Layer | Critical Failure Mode | Owner | Folder |
|---|---|---|---|
| 0. Coordinator (Orchestrator) | Infinite Graph Loops | **Student 1** | [`student_1_loop/`](student_1_loop/) |
| 1. Worker A (Analyzer) | Silent Hallucinations & Structural Failures | **Student 2** | [`student_2_silent/`](student_2_silent/) |
| 2. Worker B (Actor) | Rogue Tool Execution | **Student 3** | [`student_3_rogue/`](student_3_rogue/) |
| 3. Worker C (Validator) | Downstream Cascade Failure | **Student 4** | [`student_4_cascade/`](student_4_cascade/) |
| 4. Global Graph Layer (Tracing & Privacy) | Data Privacy Leak (Tracing) | **Student 5** | [`student_5_trace/`](student_5_trace/) |
| 5. Global Graph Layer (Context/Token Manager) | Context Window Explosion / Token Burn | **Student 6** | [`student_6_tokens/`](student_6_tokens/) |

This mapping is a starting recommendation — swap assignments if the team
prefers a different split, just keep this table in sync with who owns what.

## Domain — Financial Trading Bot

**Market Analysis → Trade Execution → Risk/Compliance Check → Audit
Logging.** The architecture (Coordinator + 4 Workers + 6 guardrails) is
identical regardless of domain — only prompts, tool lists, and sample data
change.

Mapping onto the pipeline:
- **Worker A (Analyzer)** — extracts structured data from raw market
  signals/news (ticker, price, signal type, confidence).
- **Worker B (Actor)** — executes trades via whitelisted tools (`execute_trade`,
  `cancel_order`, `send_compliance_alert`) validated against a hardcoded
  whitelist matrix (see `student_3_rogue/snippet.py`).
- **Worker C (Validator)** — the risk/compliance check before a trade's
  result is reported.
- **Worker D (Reporter)** — audit logging / final report.

## Run Your Own Guardrail (Individual)

Each `test_failure.py` is a standalone script — no pytest, no fixtures, just
run it directly from the repo root so `contract.py` resolves:

```bash
PYTHONPATH=. python student_N_x/test_failure.py
```

Until your `snippet.py` is implemented, this raises `NotImplementedError` —
that's expected. Once implemented, it should print two clearly separated
sections: a **FAILURE MODE** block showing your failure reproduced with the
guardrail disabled, and a **GUARDRAIL CHECK** block showing your real,
implemented guardrail catching the same failure. Update your `METRICS.md`
with the real before/after numbers it prints.

## Run The Full System (once wired)

```bash
python main_system.py
```

This currently raises `NotImplementedError` — `main_system.py` only has the
graph topology sketched out in comments (see the file for the exact
architecture diagram and the `# TODO(team)` import list). Once all 6
`snippet.py` files are implemented and someone wires `build_graph()` for
real, this becomes the single command that runs the whole orchestrator
end-to-end and prints the final report.

## Repo Structure

```
orchestrator-trading-bot/
├── README.md
├── DESIGN_DOCS.md           # 19 alternative failure risks considered
├── INTERVIEW_STORIES.md     # 6 individual 150-word interview scripts
├── contract.py              # THE MANDATORY CONTRACT (Day-1, frozen once reviewed)
├── main_system.py           # unified Orchestrator graph, all 6 guardrails merged in
│
├── student_1_loop/
│     ├── snippet.py         # Coordinator node + infinite-loop guardrail
│     ├── test_failure.py    # Reproduction: infinite loop (guardrail disabled)
│     └── METRICS.md
├── student_2_silent/
│     ├── snippet.py         # Analyzer node + structured-output guardrail
│     ├── test_failure.py    # Reproduction: silent hallucination
│     └── METRICS.md
├── student_3_rogue/
│     ├── snippet.py         # Actor node + tool-whitelist guardrail
│     ├── test_failure.py    # Reproduction: unauthorized tool execution
│     └── METRICS.md
├── student_4_cascade/
│     ├── snippet.py         # Validator node + sanitization guardrail
│     ├── test_failure.py    # Reproduction: downstream crash from bad data
│     └── METRICS.md
├── student_5_trace/
│     ├── snippet.py         # Tracing/privacy redaction interceptor
│     ├── test_failure.py    # Reproduction: raw PII leak to logger
│     └── METRICS.md
└── student_6_tokens/
      ├── snippet.py         # Context/token manager guardrail
      ├── test_failure.py    # Reproduction: context window explosion
      └── METRICS.md
```

## Contract Freeze

`contract.py` must be reviewed and frozen by the whole team **before**
individual guardrail work starts. If your guardrail needs a new state
field, propose it to the team first — do not add fields unilaterally.
Unreviewed changes here break every other node.

**Current freeze status:** ⏳ NOT YET FROZEN — a complete draft exists (see
the field-ownership comments at the top of `contract.py`), but it still
needs an actual team review/sign-off to count toward the "Contract & Graph
Freeze" grade.

## 🛑 Strict Safety Mandate (NON-NEGOTIABLE)

All actions interacting with external infrastructure must be mocked. Never
write code that calls genuine database table deletions, infrastructure
removal scripts, live financial trading executions, or file
modifications — **even inside your own broken `test_failure.py` demos.**
This applies to all 6 guardrails, not just Worker B's tool execution.

- ❌ Incorrect & dangerous: `os.system("rm -rf /var/log/nginx/*")`
- ✅ Correct & safe: `print("CRITICAL: PROD INFRASTRUCTURE DELETION TARGETED -> MOCK EXECUTION BLOCKED")`

Any snippet that executes a real destructive command triggers an automatic
**20-point deduction from the whole team's submission**, so double-check
your own `snippet.py`/`test_failure.py` before committing — this is one
thing not worth risking.

## Deliverables Checklist

- [x] Domain confirmed (Financial Trading Bot), repo renamed `orchestrator-trading-bot`
- [ ] `contract.py` reviewed and frozen by whole team
- [ ] Each student: `snippet.py` implemented, `test_failure.py` reproduces the failure
- [ ] `main_system.py` wired end-to-end with all 6 guardrails active
- [ ] Each student: `METRICS.md` filled in with real before/after numbers
- [ ] Each student: 2-minute failure→guardrail demo video
- [ ] `DESIGN_DOCS.md` — 19 alternative failure risks documented
- [ ] `INTERVIEW_STORIES.md` — all 6 stories written (~150 words each)
- [ ] Team: 5-minute end-to-end system demo video with voiceover
