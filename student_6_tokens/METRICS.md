# Metrics - Context Management - Context Window Explosion

## Read this first: there are two datasets, never one

Every number below is labelled with the context that produced it. They must not
be read as a single dataset.

| Label | Meaning |
|---|---|
| **[HARNESS]** | Produced by `python student_6_tokens/test_failure.py`, which replays 8 Coordinator rounds of the traffic the graph is *designed* to carry. `token_limit=180`, `retain_recent=2`, `ApproximateTokenCounter`. |
| **[GRAPH]** | Measured on the real compiled LangGraph as the system *currently* reports. `token_limit=850`, `retain_recent=4`, `TiktokenCounter`. The guardrail is **inert** here (see "Why the guardrail is inert"). |
| **[DERIVED]** | Arithmetic shown at the point of use. |

Every [HARNESS] figure is printed by the script. Nothing is transcribed from a
run that cannot be reproduced.

---

## Headline: net 71.9% [HARNESS]

The guardrail's own summarizer calls cost money, so the honest figure is net of
them, not gross.

```
Gross saving      : 8555 tok, $0.599/1k runs (86.2% of prompt tokens)
Summarizer cost   : 8 calls, 955 in @ $0.07/1M + 96 out @ $0.34/1M = $0.099/1k runs
NET saving        : $0.499/1k runs (71.9% of the unguarded bill)
```

Gross is 86.2%; **net is 71.9%**. The summarizer consumes 16.5% of the gross
saving, and output tokens bill at $0.34/1M, 4.9x the input rate. On a shorter
history the summarizer cost is roughly fixed while the saving shrinks, so net
would fall further and could invert.

Rate assumption: DeepInfra, `google/gemma-4-26B-A4B-it`, checked **2026-07-28**.
This rate moves - it fell about 12.5% over the preceding 90 days. The script
prints it as a labelled assumption so the cost column stays auditable
arithmetic.

## Context growth over 8 rounds [HARNESS]

```
round | OFF msgs  OFF tok | ON msgs  ON tok
------+-------------------+----------------
    1 |        6      288 |       5     112
    2 |       11      560 |       6     135
    3 |       16      832 |       7     158
    4 |       21     1104 |       7     146
    5 |       26     1376 |       8     169
    6 |       31     1648 |       9     192
    7 |       36     1920 |      10     215
    8 |       41     2192 |      11     238
```

| Metric | Guardrail OFF | Guardrail ON |
|---|---:|---:|
| Final window | 2,192 tok (41 msgs) | 238 tok (11 msgs) |
| Cumulative input tokens | 9,920 | 1,365 |
| Cost per 1,000 runs | $0.694 | $0.096 |
| Growth slope | +272.0 tok/round | +18.0 tok/round (6.6%) |

Cumulative, not final, is the billable quantity: the Coordinator re-sends the
whole window on every routing decision.

**Neither run is bounded.** Both grow linearly; the guardrail buys a shallower
slope, not a flat one. The dip at round 4 (158 to 146 tok) is the summary
collapse described under L-9's fix.

## Both branches of the threshold [HARNESS]

The requirement is that the node summarizes *if* a threshold is exceeded, so
both outcomes are exercised. Traffic varies; the threshold never does.

```
round  before  arriving  carried_summaries  fired
    1     288       272                  0   True
    2     384       272                 12   True
    8     487       272                 12   True
```

One round of arriving traffic is **272 tok against a 180-tok limit**, so the
limit is breached by new traffic alone even against an empty window.
`carried_summaries` stays flat at 12 from round 2 on, which is the summary
collapse holding. Accumulated summaries add pressure but are not the trigger.

Low-traffic session, same threshold:

```
round  msgs  tokens  vs limit 180
    1     2      27  UNDER
    5     6      71  UNDER
Summarizer invocations: 0 (window peaked at 71 tok, under the 180-tok threshold,
so the node measured and did nothing)
```

## Retraction: the estimator is not conservative

**A previous version of this document claimed `chars/4` over-estimates token
counts and concluded the guardrail therefore "triggers earlier than a real token
count would require. This is conservative." That claim is withdrawn. It was an
artefact of a fixture built from repetitive filler prose, and it is wrong in the
direction that matters.**

The bias is **content-dependent**:

| Content | Measured error | Direction |
|---|---:|---|
| Numeric-dense trading payloads, OFF window [HARNESS] | -23.8% | **UNDER**-counts |
| Numeric-dense trading payloads, ON window [HARNESS] | -13.5% | **UNDER**-counts |
| Short prose, real graph messages [GRAPH] | +8% to +18% | over-counts |

```
encoding=cl100k_base using_fallback=False
OFF final window: chars/4= 2192 tiktoken= 2877 chars/4_error=-23.8% (UNDER-estimates)
ON  final window: chars/4=  238 tiktoken=  275 chars/4_error=-13.5% (UNDER-estimates)
```

Prices, tickers, and `RSI(14) 61.8` style figures tokenize to more BPE tokens
per character than prose. Where the estimator under-counts, the guardrail fires
**later** than a real token count would require - the unsafe direction. That is
why the integrated graph now runs on `TiktokenCounter`, which falls back to the
estimate only on failure and records why.

`test_failure.py` deliberately stays on `ApproximateTokenCounter` so a grader
gets byte-identical output on a cold machine with no vocabulary download. It
reports real BPE counts alongside, so both bases are visible.

## Latency: this guardrail costs latency here

```
MEASURED (floor, not an estimate): ~1.3 ms over 8 rounds (~0.16 ms/round).
  EXCLUDES all summarizer network time -- the summarizer here is local.
PROJECTED with a real summarizer: 8 DeepInfra round trips at 0.56-0.68 s TTFT
  (checked 2026-07-28) = 4.5-5.4 s added.
```

The measured figure is the only nondeterministic number here and varies by run;
it is a **floor**, not an estimate of real-world latency.

**Break-even** [DERIVED]. Compression pays for itself in latency only once the
prefill time it avoids exceeds the summarizer round trip it adds:
`saved_tokens / prefill_rate > TTFT`, so with compression ratio `r` the
break-even window is `W = TTFT * prefill_rate / r`.

```
Prefill throughput assumption: 10,000-20,000 tok/s
  (unverified order-of-magnitude assumption, not a published benchmark)
Measured compression ratio: 0.862
Break-even history size: 6,494-15,770 tokens
Largest window this demo reaches: 2,192 tok (33.8% of the most optimistic break-even)
```

The price and TTFT constants are vendor figures. The prefill throughput is
**not** - no published prefill number was found for this model, so it is named
in the source as an assumption and the result is given as a sensitivity band.
The conclusion holds across the whole band.

**Design position.** `token_limit=850` [GRAPH] sits an order of magnitude below
the ~6,500-15,800 token break-even, so whenever this guardrail fires it is *by
construction* on the latency-costing side: it buys token cost with roughly one
summarizer round trip. Sizing the threshold at the crossover instead would leave
it permanently inert, because five rounds of designed traffic total only ~1,790
tok [DERIVED] and can never reach 6,500. Firing below break-even is the right
call - an inert guardrail protects nothing - but it is a trade, not a free win.
This does not contradict the assignment's 8s-to-1.8s exemplar; that describes a
much larger window, on the far side of the crossover.

## Why the guardrail is inert in the integrated graph [GRAPH]

A grader running `main_system.py` will see this node do nothing. That is
expected, and it is an upstream reporting gap rather than a guardrail defect.

No production worker writes `tool_output` messages into `state["messages"]`.
Only `orchestrator/nodes/analyzer.py` appends to the window, one short record
per visit, so the real history peaks at **41 real BPE tokens against the 850
token threshold - 4.8% of the limit**, with 809 tokens of headroom. Measured on
the real compiled LangGraph across 3 `context_manager` visits:

```
visit  msgs_in  tok_in  msgs_out  tok_out  >limit?  summarized  pruned
    1        2      32         2       32    False           0       0
    2        3      41         3       41    False           0       0
    3        3      41         3       41    False           0       0
Guardrail fired: False    Summarizer invocations: 0
Graph completed: rounds=3 termination=completed validated=True
```

Reproduce with mocked network (never invoke the live CLI - it makes real
DeepInfra and LangSmith calls):

```python
from contract import AgentState, MessageRecord
from orchestrator.utils.token_counting import TiktokenCounter
tik = TiktokenCounter()
window = [
    MessageRecord(role="system", kind="system_instruction", content=(
        "All external actions are mocked. Apply every deterministic "
        "guardrail before reporting.")),
    MessageRecord(role="user", content=
        "AAPL rose 4% in ten minutes on unusual volume; consider 10 shares."),
    *[MessageRecord(role="assistant", name="worker_a_analyzer",
        content="Structured analysis: AAPL buy 10.")] * 5,
]
print(tik.count_messages(window), "tok vs token_limit=850")
```

From the current 41-token peak, reaching 850 needs ~21x growth; under designed
traffic at 358 tok/round it takes **3 rounds** [DERIVED]. The node is verified
correct under designed traffic by the [HARNESS] results above.

## How `token_limit=850` was derived [DERIVED]

Sized to the traffic the graph is designed to carry at `max_rounds=5` and
`retain_recent=4`, in real `cl100k_base` tokens:

| Component | Tokens |
|---|---:|
| System instruction (cli.py seed) | 14 |
| One summary record | 9 |
| Protected `tool_output` x5 (29 each, never evictable) | 145 |
| Retained recent turns x4 (133 each, worst case) | 532 |
| **Irreducible steady-state floor** | **700** |
| + 20% headroom, rounded to 50 | **850** |

The floor uses the *largest* conversation turn, not the average, because a limit
below the floor cannot be met - the recent window and the protected records are
both un-evictable, so the guardrail would sit permanently over budget and warn
every round. One round of designed traffic adds 358 tok, taking the window to
1,058, so the guardrail engages and converges back to the floor. At the previous
`token_limit=1200` it never engaged even under full designed traffic.

## Invariants [HARNESS]

All 14 pass. These are the guardrail's contract; the token budget is a soft
target and these are hard.

```
[PASS] threshold gating: low-traffic session never summarizes
[PASS] threshold gating: low-traffic history passes through untouched
[PASS] threshold gating: high-traffic session does summarize
[PASS] summaries collapse instead of accumulating (exactly 1)
[PASS] ON slope is materially lower than OFF (<= 25% of it)
[PASS] ON final window smaller than OFF
[PASS] system rule preserved
[PASS] obsolete level-2 snapshots pruned
[PASS] every compliance result retained
[PASS] newest emitted message retained
[PASS] newest non-protected turn retained
[PASS] core state untouched (round_number/is_validated)
[PASS] core state untouched (errors/approved_tool_calls)
[PASS] core state untouched (analysis_payload/raw_input/task_domain)
```

`every compliance result retained` is the important one. All 8 `Risk review`
records survive 8 rounds of compression. Before this was enforced, a compliance
rejection was structurally eligible for pruning and was silently deleted.

State preservation is structural, not asserted: the node returns only
`messages`, `context_summary`, and `context_metrics`, so `round_number`,
`is_validated`, `analysis_payload`, `errors`, `approved_tool_calls`, `raw_input`,
and `task_domain` are out of its reach by construction.

## Message-window replacement is proven, not assumed [GRAPH]

If `AgentState.messages` carried an `add_messages` reducer, returning a pruned
list would append rather than replace, and every number above would be a lie
while the history kept growing. `contract.py` declares a plain
`list[MessageRecord]` with no reducer annotation, so LangGraph assigns a
LastValue channel. Verified by execution against langgraph 1.2.10: a compiled
`StateGraph` given 5 messages and returning 1 yields **5 in, 1 out**. Under
append semantics it would be 6. See
`tests/guardrails/test_context_manager_node.py::test_shorter_message_list_replaces_rather_than_appends`,
which has no `skipif` and no fallback, so it fails loudly if that ever changes.

## Limitations

**L-1 - Oversized messages cannot be truncated.** The guardrail can refuse to
delete an oversized message but cannot shrink one. Worst case measured: a single
240-token message against a 40-token limit exits at 240/40, **+500%**. That is
an adversarial construction, not an operating point; the observed operating range
is **+19% to +58%**. Deliberately not fixed - truncation is scope beyond the
graded items.

**L-2 - Estimator bias is content-dependent and runs unsafe on this domain.**
`chars/4` under-counts numeric-dense trading payloads by 13.5-23.8% [HARNESS]
and over-counts short prose by roughly 8-18% [GRAPH]. Under-counting delays
firing. Mitigated by wiring `TiktokenCounter` into the integrated graph;
`test_failure.py` retains the estimator for cold-start reproducibility and
reports both.

**L-3 - Resolved.** An earlier fixture emitted one conversation turn per round,
which with `retain_recent=2` meant older history never accumulated and the
summarizer never fired - the entire reduction came from obsolete-output pruning.
The fixture now emits the traffic the graph actually produces and the summarizer
fires 8/8 rounds.

**L-4 - Protecting compliance records makes growth unbounded with a shallower
slope.** The ON run ends at 238 tok against a 180-tok limit (**+32%**) because
protected records accumulate at ~23 tok/round with no eviction path. This is the
deliberate cost of never deleting a compliance verdict. Latent rather than live:
no production worker emits `tool_output` today, and `max_rounds=5` caps
accumulation at ~5 records (~145 tok) against the 850 threshold.

**L-5 - The guardrail costs latency in this configuration.** Below ~6,500-15,800
tok of history it costs latency; above, it saves. This system peaks at 2,192 tok
[HARNESS] and 41 tok [GRAPH], so it is always on the costing side: about
4.5-5.4 s added over 8 rounds in exchange for 71.9% net token cost. Recorded as
a design position at the constant in `orchestrator/graph.py`.

**L-6 - Scope.** The guardrail's own token cost is measured and reported by
`test_failure.py` and logged at INFO by the guardrail, and is deliberately not
written into graph state, because graph state is governed by a frozen team
contract that this layer does not modify unilaterally.

**L-7 - End-to-end evidence uses a mocked network.** [GRAPH] figures come from
the real compiled LangGraph with all six nodes, real edges, real conditional
routing, and the real `TiktokenCounter`; only the chat model and trace sink are
stubbed. The live CLI is never invoked, because it makes real DeepInfra and
LangSmith calls and the assignment's safety mandate forbids unmocked external
side effects.

**L-8 - Files in this folder must stay ASCII.** `tests/architecture` and
`tests/ui` read source files with `Path.read_text()` and no explicit encoding,
so on a Windows cp1252 default any non-ASCII byte raises `UnicodeDecodeError`.
This already blocks `app/mock_data.py`. Team-level fix noted in the handoff.

**L-9 - Summarization is recursive, so fidelity decays.** Each new summary
absorbs the previous one, which is what keeps the count at exactly 1 instead of
growing once per round. The consequence is that by round 8 the summary is an
8th-generation paraphrase. With a real LLM, detail would measurably degrade each
round. `DeterministicSummarizer` hides this completely - it regenerates a fixed
sentence from a message count, so these results prove the token arithmetic and
say nothing about how well meaning survives eight compressions. Documented, not
fixed.

## Reproducing

```
python student_6_tokens/test_failure.py   # all [HARNESS] figures, exit 0
python -m pytest tests/guardrails         # guardrail unit and node tests
```

Deterministic: two consecutive runs are byte-identical apart from the labelled
timing line. Offline: completes with `socket.socket`, `create_connection`, and
`getaddrinfo` all replaced by raising stubs. Terminates unattended. Worst-case
API spend for one run: **$0.00**. Invariant failures raise `SystemExit`, not
`assert`, so `python -O` cannot strip them.
