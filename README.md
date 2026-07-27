# Generic Task Orchestrator — [TODO: TEAM NAME]

> **Status: PLACEHOLDER SCAFFOLD.** Domain not yet confirmed. `contract.py`
> is the Day-1 starting schema (still needs team review before it's frozen).
> Every guardrail file below is an empty stub — `raise NotImplementedError`
> — for its owner to fill in. `main_system.py` is also a placeholder until
> the team wires the graph together.

## Course

Introductory Agentic AI (Master's Level) — Multi-Agent Failure Modes & Guardrails
Group Assignment (6 students)

## Team & Role Assignment

| Node / Layer | Critical Failure Mode | Student Owner | Folder |
|---|---|---|---|
| 0. Coordinator (Orchestrator) | Infinite Graph Loops | **JN** | [`student_1_loop/`](student_1_loop/) |
| 1. Worker A (Analyzer) | Silent Hallucinations & Structural Failures | **Rodney** | [`student_2_silent/`](student_2_silent/) |
| 2. Worker B (Actor) | Rogue Tool Execution | **Alex** | [`student_3_rogue/`](student_3_rogue/) |
| 3. Worker C (Validator) | Downstream Cascade Failure | **Anh** | [`student_4_cascade/`](student_4_cascade/) |
| 4. Global Graph Layer (Tracing & Privacy) | Data Privacy Leak (Tracing) | **Zainab** | [`student_5_trace/`](student_5_trace/) |
| 5. Global Graph Layer (Context/Token Manager) | Context Window Explosion / Token Burn | **Quynh** | [`student_6_tokens/`](student_6_tokens/) |

This mapping is a starting recommendation — swap names if the team prefers
a different split, just keep this table in sync with who owns what.

## Domain Decision — NOT YET MADE

Pick **one** domain to instantiate the orchestrator (architecture stays
identical; only prompts, tool lists, and sample data change):

1. 🛡️ Autonomous Incident Response — Monitor → Diagnose → Patch → Report
2. 📈 Financial Trading Bot — Market Analysis → Trade Execution → Risk/Compliance → Audit Logging
3. ⚖️ Legal Contract Review — Clause Extraction → Risk Analysis → Redline → Counter-Party Verification
4. 🧬 Bioinformatics Pipeline — Sequence Alignment → Variant Annotation → Validation → Synthesis Report
5. 📚 Academic Research Assistant — Lit Review Search → Synthesis → Critique → Draft Compilation

Once decided: rename this repo from `orchestrator-placeholder` to
`orchestrator-{domain}`.

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
thing not worth risking. (`student_3_rogue/snippet.py`'s `mock_execute_tool`
is a working example of doing this correctly.)

## Stack

- **Language:** Python 3.11+
- **Framework:** LangGraph + LangChain Core
- **Structured output:** Pydantic (`contract.py`)
- **Observability:** LangSmith
- **Zero-tolerance rule:** single-language repo. No mixed Python/TypeScript.

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # fill in real keys locally, never commit .env
```

## Repo Structure

```
orchestrator-placeholder/
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

**Current freeze status:** ⏳ NOT YET FROZEN.

## Deliverables Checklist

- [ ] Domain confirmed, repo renamed `orchestrator-{domain}`
- [ ] `contract.py` reviewed and extended (if needed) and frozen by whole team
- [ ] Each student: `snippet.py` implemented, `test_failure.py` reproduces the failure
- [ ] `main_system.py` wired end-to-end with all 6 guardrails active
- [ ] Each student: `METRICS.md` filled in with real before/after numbers
- [ ] Each student: 2-minute failure→guardrail demo video
- [ ] `DESIGN_DOCS.md` — 19 alternative failure risks documented
- [ ] `INTERVIEW_STORIES.md` — all 6 stories written (~150 words each)
- [ ] Team: 5-minute end-to-end system demo video with voiceover
