"""Deterministic context-window explosion reproduction, guardrail OFF vs ON.

Runs the context-management node across repeated Coordinator rounds in the
financial-trading domain and shows history growth with the guardrail disabled
against the same history with it enabled.

Safety and reproducibility properties, all verifiable by running this file:

* No network. The summarizer is a fixed local object and ``tiktoken`` is only
  touched for the optional estimator-validation section, which degrades cleanly.
* No external side effects. No trade, infrastructure, file, or database call.
* Worst-case API spend for one run: $0.00.
* Deterministic. Every reported number except the wall-clock timing block is
  identical across runs.
* Terminates on its own after ``ROUNDS`` iterations.

Known fidelity limitation: because each new summary absorbs the previous one,
summarization is recursive. By round 8 the summary is an 8th-generation
paraphrase, and with a real LLM detail would decay measurably each round.
``DeterministicSummarizer`` hides this entirely -- it regenerates a fixed
sentence from a message count, so the reproduction shows the token arithmetic
but says nothing about how well meaning survives eight compressions.

Modelling assumption, stated up front because it inflates the guardrail-OFF
curve: of the five message types this fixture emits per round, three are
observed and two are projected. The market-signal turn, the Level-2 snapshot,
and the analyst note correspond to messages the graph writes today
(``orchestrator/nodes/analyzer.py`` appends the analyst note). The coordinator
routing rationale currently lands in ``AgentState.routing_history`` rather than
``messages``, and no production worker writes ``tool_output`` messages at all,
so the Risk review is projected too. This models the graph as it is designed to
report, not as it currently reports.
"""

from __future__ import annotations

import sys
from pathlib import Path
from time import perf_counter
from typing import Sequence

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from contract import AgentState, MessageRecord
from snippet import ApproximateTokenCounter, TiktokenCounter, make_context_manager_node

ROUNDS = 8
TOKEN_LIMIT = 180
RETAIN_RECENT = 2

# Pricing assumption, printed below so the cost column stays auditable
# arithmetic rather than a hard-coded result. This rate moves: it fell ~12.5%
# over the ~90 days before the check date, so re-check before quoting it.
USD_PER_1M_INPUT = 0.07
# Summarizer completions are billed at the output rate, 4.9x the input rate.
# This is what makes the summarizer's own cost non-negligible.
USD_PER_1M_OUTPUT = 0.34
RATE_SOURCE = "DeepInfra, google/gemma-4-26B-A4B-it"
RATE_CHECKED = "2026-07-28"

# Published time-to-first-token band for this model on DeepInfra, used only for
# the clearly-labelled latency PROJECTION below. The measured timing in this
# script uses a local summarizer and therefore excludes all network time.
TTFT_SECONDS_LOW = 0.56
TTFT_SECONDS_HIGH = 0.68
TTFT_CHECKED = "2026-07-28"

# Prefill throughput, used only for the latency break-even projection.
#
# HONESTY NOTE: unlike the price and TTFT constants, this is NOT a vendor
# published figure. It is an order-of-magnitude band for a ~26B MoE with ~4B
# active parameters under batched serving. The break-even below is therefore
# reported as a sensitivity range across this band, not as a single number.
PREFILL_TOKENS_PER_SECOND_LOW = 10_000
PREFILL_TOKENS_PER_SECOND_HIGH = 20_000
PREFILL_BASIS = "unverified order-of-magnitude assumption, not a published benchmark"

SYSTEM_RULE = "Never execute real trades. Every action is mocked and audited."


class DeterministicSummarizer:
    """Fixed local summarizer. Makes no network call, so one run costs $0.00.

    Self-instrumenting: records the tokens a real summarizer would be billed
    for -- the history it reads (input) and the summary it returns (output) --
    so the guardrail's own cost can be subtracted from its savings.
    """

    def __init__(self, counter) -> None:
        self._counter = counter
        self.calls = 0
        self.input_tokens = 0
        self.output_tokens = 0

    def summarize(self, messages: Sequence[MessageRecord]) -> str:
        self.calls += 1
        self.input_tokens += self._counter.count_messages(messages)
        summary = f"Summary preserving {len(messages)} older decisions and errors."
        self.output_tokens += self._counter.count_messages(
            [MessageRecord(role="assistant", content=summary)]
        )
        return summary


def worker_turns(round_number: int) -> list[MessageRecord]:
    """One Coordinator round's worth of trading-domain message growth.

    Message types are chosen to mirror what this graph actually produces, not
    to make any particular guardrail branch fire:

    * Market-signal turn -- the unstructured input the Analyzer consumes, the
      same shape as ``AgentState.raw_input`` seeded by ``orchestrator/cli.py``.
    * Analyst note -- ``orchestrator/nodes/analyzer.py`` appends exactly this
      kind of assistant ``MessageRecord`` ("Structured analysis: ...") to
      ``state.messages`` on every successful analysis.
    * Coordinator routing rationale -- the ``route_reason`` strings produced by
      ``orchestrator/nodes/coordinator.py``. Today those land in
      ``routing_history`` rather than ``messages``; included here as a
      representative conversation turn a routing narration would add.
    * Level-2 snapshot -- intermediate tool chatter, marked obsolete.
    * Risk review -- a compliance verdict, deliberately not marked obsolete.
    """
    return [
        MessageRecord(
            role="user",
            content=(
                f"Round {round_number}: NVDA 20-day SMA 118.42 above 50-day "
                f"114.87 on 2.3x volume, RSI(14) 61.8, MACD positive. " * 3
            ),
        ),
        MessageRecord(
            role="assistant",
            name="worker_a_analyzer",
            content=(
                f"Structured analysis (round {round_number}): NVDA buy 250, "
                "confidence 0.78, risk_level medium. Rationale: momentum "
                "confirmed by volume and sector breadth."
            ),
        ),
        MessageRecord(
            role="assistant",
            name="coordinator",
            content=(
                f"Routing round {round_number}: structured analysis is ready "
                "for guarded mock execution; dispatching to worker_b_actor."
            ),
        ),
        # Intermediate tool chatter, explicitly marked obsolete: safe to drop.
        MessageRecord(
            role="tool",
            kind="tool_output",
            obsolete=True,
            content=f"Level-2 snapshot seq {round_number} " * 20,
        ),
        # A compliance verdict. NOT marked obsolete, so it is a decision record
        # and must survive every round of compression.
        MessageRecord(
            role="tool",
            kind="tool_output",
            content=(
                f"Risk review round {round_number}: notional 29,605.00 USD "
                "against 250,000.00 buying power. Result: PASS."
            ),
        ),
    ]


def cost_per_1k_runs(tokens: int, usd_per_1m: float = USD_PER_1M_INPUT) -> float:
    return tokens * usd_per_1m / 1_000_000 * 1_000


def quiet_turns(round_number: int) -> list[MessageRecord]:
    """A low-traffic round: one short status turn, no tool output.

    Exists so the demo exercises the guardrail's OTHER branch -- the node runs,
    measures, finds the window under threshold, and correctly does nothing.
    The threshold is never adjusted to produce this; only the traffic varies.
    """
    return [
        MessageRecord(
            role="assistant",
            name="coordinator",
            content=f"Round {round_number}: market closed, no action required.",
        )
    ]


def run_quiet_session(counter) -> dict:
    """Replay low-traffic rounds and confirm the guardrail stays a no-op."""
    seed = [MessageRecord(role="system", content=SYSTEM_RULE)]
    state = AgentState(raw_input="Monitor NVDA overnight.", messages=list(seed))
    summarizer = DeterministicSummarizer(counter)
    node = make_context_manager_node(
        token_counter=counter,
        summarizer=summarizer,
        token_limit=TOKEN_LIMIT,
        retain_recent=RETAIN_RECENT,
    )
    rows: list[tuple[int, int, int]] = []
    for round_number in range(1, 6):
        state.messages = [*state.messages, *quiet_turns(round_number)]
        expected = list(state.messages)
        for field, value in node(state).items():
            setattr(state, field, value)
        rows.append((
            round_number,
            len(state.messages),
            counter.count_messages(state.messages),
        ))
        untouched = state.messages == expected
    return {
        "rows": rows,
        "state": state,
        "summarizer_calls": summarizer.calls,
        "untouched": untouched,
        "final_tokens": rows[-1][2],
    }


def run(*, guardrail: bool, counter) -> dict:
    """Replay ROUNDS Coordinator rounds with the guardrail on or off."""
    state = AgentState(
        raw_input="Evaluate a 250 share NVDA long.",
        messages=[MessageRecord(role="system", content=SYSTEM_RULE)],
    )
    summarizer = DeterministicSummarizer(counter)
    node = make_context_manager_node(
        token_counter=counter,
        summarizer=summarizer,
        token_limit=TOKEN_LIMIT,
        retain_recent=RETAIN_RECENT,
    )
    rows: list[tuple[int, int, int]] = []
    diagnostics: list[dict] = []
    cumulative_tokens = 0
    guardrail_seconds = 0.0

    for round_number in range(1, ROUNDS + 1):
        arriving = worker_turns(round_number)
        # Why the guardrail fires: separate the tokens that arrived this round
        # from the summaries left over by previous rounds (M1's accumulation).
        carried_summary_tokens = counter.count_messages(
            [m for m in state.messages if m.kind == "summary"]
        )
        arriving_tokens = counter.count_messages(arriving)
        state.messages = [*state.messages, *arriving]
        before_tokens = counter.count_messages(state.messages)

        calls_before = summarizer.calls
        started = perf_counter()
        if guardrail:
            for field, value in node(state).items():
                setattr(state, field, value)
        guardrail_seconds += perf_counter() - started
        tokens = counter.count_messages(state.messages)

        diagnostics.append({
            "round": round_number,
            "before": before_tokens,
            "arriving": arriving_tokens,
            "carried_summaries": carried_summary_tokens,
            "fired": summarizer.calls > calls_before,
        })
        # The Coordinator re-sends the whole window on every routing decision,
        # so spend is the running sum of per-round window sizes, not the size
        # of the final window.
        cumulative_tokens += tokens
        rows.append((round_number, len(state.messages), tokens))

    return {
        "rows": rows,
        "diagnostics": diagnostics,
        "state": state,
        "guardrail_seconds": guardrail_seconds,
        "summarizer_calls": summarizer.calls,
        "summarizer_input_tokens": summarizer.input_tokens,
        "summarizer_output_tokens": summarizer.output_tokens,
        "final_tokens": rows[-1][2],
        "final_messages": rows[-1][1],
        "cumulative_tokens": cumulative_tokens,
    }


def main() -> None:
    counter = ApproximateTokenCounter()
    off = run(guardrail=False, counter=counter)
    on = run(guardrail=True, counter=counter)

    print("=== ASSUMPTIONS ===")
    print(f"Rounds simulated      : {ROUNDS}")
    print(f"Token limit           : {TOKEN_LIMIT}")
    print(f"Recent turns retained : {RETAIN_RECENT}")
    print(f"Token counter         : ApproximateTokenCounter (chars/4)")
    print(f"Input token rate      : ${USD_PER_1M_INPUT:.2f}/1M")
    print(f"Rate source           : {RATE_SOURCE}")
    print(f"Rate checked          : {RATE_CHECKED} (moves over time; re-check)")
    print(f"Summarizer            : local, deterministic, 0 network calls")
    print(f"Worst-case API spend  : $0.00 per run")

    print(f"\n=== CONTEXT GROWTH OVER {ROUNDS} COORDINATOR ROUNDS ===")
    print(f"{'round':>5} | {'OFF msgs':>8} {'OFF tok':>8} | {'ON msgs':>7} {'ON tok':>7}")
    print(f"{'-' * 5:>5}-+-{'-' * 8:>8}-{'-' * 8:>8}-+-{'-' * 7:>7}-{'-' * 7:>7}")
    for (rnd, off_msgs, off_tok), (_, on_msgs, on_tok) in zip(off["rows"], on["rows"]):
        print(f"{rnd:>5} | {off_msgs:>8} {off_tok:>8} | {on_msgs:>7} {on_tok:>7}")

    print("\n=== TOTALS (input tokens re-sent every round) ===")
    for label, data in (("guardrail OFF", off), ("guardrail ON ", on)):
        print(
            f"{label}: final_window={data['final_tokens']:>6} tok "
            f"({data['final_messages']:>2} msgs)  "
            f"cumulative={data['cumulative_tokens']:>6} tok  "
            f"cost/1k_runs=${cost_per_1k_runs(data['cumulative_tokens']):.3f}"
        )
    print("\n=== NET SAVINGS AFTER THE GUARDRAIL'S OWN COST ===")
    saved = off["cumulative_tokens"] - on["cumulative_tokens"]
    gross_usd = cost_per_1k_runs(saved)
    summ_in_usd = cost_per_1k_runs(on["summarizer_input_tokens"], USD_PER_1M_INPUT)
    summ_out_usd = cost_per_1k_runs(on["summarizer_output_tokens"], USD_PER_1M_OUTPUT)
    summarizer_usd = summ_in_usd + summ_out_usd
    net_usd = gross_usd - summarizer_usd
    off_usd = cost_per_1k_runs(off["cumulative_tokens"])
    print(
        f"Gross saving      : {saved} tok, ${gross_usd:.3f}/1k runs "
        f"({100 * saved / off['cumulative_tokens']:.1f}% of prompt tokens)"
    )
    print(
        f"Summarizer cost   : {on['summarizer_calls']} calls, "
        f"{on['summarizer_input_tokens']} in @ ${USD_PER_1M_INPUT:.2f}/1M + "
        f"{on['summarizer_output_tokens']} out @ ${USD_PER_1M_OUTPUT:.2f}/1M "
        f"= ${summarizer_usd:.3f}/1k runs"
    )
    print(
        f"NET saving        : ${net_usd:.3f}/1k runs "
        f"({100 * net_usd / off_usd:.1f}% of the unguarded bill)"
    )
    if net_usd <= 0:
        print("  >>> NET NEGATIVE: the guardrail costs more than it saves here.")

    print("\n=== WHY THE GUARDRAIL FIRES (per round) ===")
    print(f"{'round':>5} {'before':>7} {'arriving':>9} {'carried_summaries':>18} {'fired':>6}")
    for diag in on["diagnostics"]:
        print(
            f"{diag['round']:>5} {diag['before']:>7} {diag['arriving']:>9} "
            f"{diag['carried_summaries']:>18} {str(diag['fired']):>6}"
        )
    first = on["diagnostics"][0]
    print(
        f"One round of arriving messages is {first['arriving']} tok against a "
        f"{TOKEN_LIMIT}-tok limit, so the limit is breached by new traffic "
        f"alone even with an empty window. Accumulated summaries add to the "
        f"pressure but are not what triggers it."
    )

    print("\n=== ESTIMATOR VALIDATION (real BPE; skipped if unavailable) ===")
    tik = TiktokenCounter()
    if tik.using_fallback:
        print(f"tiktoken unavailable ({tik.fallback_reason}); approximate counts only.")
    else:
        print(f"encoding={tik.encoding_name} using_fallback=False")
        for label, data in (("OFF", off), ("ON ", on)):
            msgs = data["state"].messages
            approx_tokens = counter.count_messages(msgs)
            real_tokens = tik.count_messages(msgs)
            error_pct = 100 * (approx_tokens - real_tokens) / real_tokens
            direction = "over" if error_pct > 0 else "UNDER"
            print(
                f"{label} final window: chars/4={approx_tokens:>5} "
                f"tiktoken={real_tokens:>5} "
                f"chars/4_error={error_pct:+.1f}% ({direction}-estimates)"
            )
        print(
            "Note: on numeric-dense trading text (prices, tickers, RSI/MACD "
            "figures) chars/4 UNDER-estimates, so the guardrail fires LATER "
            "than a real token count would require. That is the opposite of "
            "conservative -- see METRICS.md."
        )

    # Wall clock. Reported separately because it is the only nondeterministic
    # figure here. With a local summarizer there is no network round trip to
    # measure, so this is guardrail CPU overhead, not end-to-end turn latency.
    # Token count is the quantity that drives real latency and spend, and the
    # table above measures that directly.
    print("\n=== LATENCY ===")
    print(
        f"MEASURED (floor, not an estimate): "
        f"{on['guardrail_seconds'] * 1000:.2f} ms over {ROUNDS} rounds "
        f"({on['guardrail_seconds'] * 1000 / ROUNDS:.3f} ms/round). "
        f"EXCLUDES all summarizer network time -- the summarizer here is local."
    )
    low = on["summarizer_calls"] * TTFT_SECONDS_LOW
    high = on["summarizer_calls"] * TTFT_SECONDS_HIGH
    print(
        f"PROJECTED with a real summarizer: {on['summarizer_calls']} DeepInfra "
        f"round trips at {TTFT_SECONDS_LOW:.2f}-{TTFT_SECONDS_HIGH:.2f} s TTFT "
        f"({RATE_SOURCE}, checked {TTFT_CHECKED}) = {low:.1f}-{high:.1f} s added."
    )
    print(
        f"  >>> Against prefill savings measured in tens of ms, this guardrail "
        f"likely INCREASES end-to-end latency while decreasing token cost."
    )

    # Break-even: compression only pays for itself in latency once the prefill
    # time it avoids exceeds the summarizer round trip it adds.
    #   saved_tokens / prefill_rate  >  TTFT
    # With a compression ratio r, saved_tokens = r * window, so the break-even
    # window is  W = TTFT * prefill_rate / r.
    print("\n=== LATENCY BREAK-EVEN (projection) ===")
    ratio = saved / off["cumulative_tokens"]
    print(
        f"Prefill throughput assumption: "
        f"{PREFILL_TOKENS_PER_SECOND_LOW:,}-{PREFILL_TOKENS_PER_SECOND_HIGH:,} tok/s "
        f"({PREFILL_BASIS})"
    )
    print(f"Measured compression ratio: {ratio:.3f}")
    breakevens = [
        TTFT * rate / ratio
        for TTFT in (TTFT_SECONDS_LOW, TTFT_SECONDS_HIGH)
        for rate in (PREFILL_TOKENS_PER_SECOND_LOW, PREFILL_TOKENS_PER_SECOND_HIGH)
    ]
    low_w, high_w = min(breakevens), max(breakevens)
    print(
        f"Break-even history size: {low_w:,.0f}-{high_w:,.0f} tokens "
        f"(below this the guardrail costs latency; above it, it saves latency)"
    )
    reached = off["rows"][-1][2]
    print(
        f"Largest window this demo reaches: {reached:,} tok "
        f"({100 * reached / low_w:.1f}% of the most optimistic break-even)"
    )
    if reached < low_w:
        print(
            f"  >>> This system never reaches the break-even window. With "
            f"max_rounds=5 the real graph reaches far less still, so in THIS "
            f"configuration the guardrail is a cost optimisation that costs "
            f"latency. The assignment's 8s->1.8s exemplar is not contradicted: "
            f"it describes a much larger window, above the crossover."
        )

    # Per-round token slope. Neither run is bounded: OFF and ON both grow
    # linearly. What the guardrail buys is a materially shallower slope, so
    # that is what gets measured and asserted -- not "bounded", which the
    # growth table above would immediately contradict.
    off_slope = (off["rows"][-1][2] - off["rows"][0][2]) / (ROUNDS - 1)
    on_slope = (on["rows"][-1][2] - on["rows"][0][2]) / (ROUNDS - 1)
    print("\n=== GROWTH SLOPE (tokens per additional round) ===")
    print(f"guardrail OFF: {off_slope:+.1f} tok/round")
    print(f"guardrail ON : {on_slope:+.1f} tok/round "
          f"({100 * on_slope / off_slope:.1f}% of the OFF slope)")
    print(
        "Both are linear. The guardrail reduces the slope; it does not flatten "
        "it, because protected compliance records accumulate (see METRICS.md)."
    )

    # The requirement is that the node summarizes IF a threshold is exceeded.
    # The busy session above only ever exercises the "exceeded" branch, so a
    # low-traffic session is replayed here to exercise the other one.
    quiet = run_quiet_session(counter)
    print("\n=== THRESHOLD GATING: LOW-TRAFFIC SESSION (same limit) ===")
    print(f"{'round':>5} {'msgs':>5} {'tokens':>7}  vs limit {TOKEN_LIMIT}")
    for rnd, msgs, toks in quiet["rows"]:
        print(f"{rnd:>5} {msgs:>5} {toks:>7}  {'UNDER' if toks <= TOKEN_LIMIT else 'OVER'}")
    print(
        f"Summarizer invocations: {quiet['summarizer_calls']} "
        f"(window peaked at {quiet['final_tokens']} tok, under the "
        f"{TOKEN_LIMIT}-tok threshold, so the node measured and did nothing)"
    )

    print("\n=== INVARIANTS ===")
    final_state = on["state"]
    final = final_state.messages
    checks = {
        "threshold gating: low-traffic session never summarizes":
            quiet["summarizer_calls"] == 0,
        "threshold gating: low-traffic history passes through untouched":
            quiet["untouched"] is True,
        "threshold gating: high-traffic session does summarize":
            on["summarizer_calls"] == ROUNDS,
        # Prior summaries are folded into each new one, so the window holds
        # exactly one no matter how many rounds run. Before this fix the count
        # grew once per round and summaries became 44% of the surviving window.
        "summaries collapse instead of accumulating (exactly 1)":
            sum(1 for message in final if message.kind == "summary") == 1,
        "ON slope is materially lower than OFF (<= 25% of it)":
            on_slope <= 0.25 * off_slope,
        "ON final window smaller than OFF":
            on["final_messages"] < off["final_messages"],
        "system rule preserved":
            any(message.content == SYSTEM_RULE for message in final),
        "obsolete level-2 snapshots pruned":
            all("Level-2 snapshot" not in message.content for message in final),
        "every compliance result retained":
            sum("Risk review" in message.content for message in final) == ROUNDS,
        # C1's invariant is that the newest turn survives eviction. It is NOT
        # that every round-N message survives: the market-signal turn is the
        # third-newest conversation turn, so RETAIN_RECENT=2 summarizes it, and
        # that is correct compression rather than a loss.
        "newest emitted message retained":
            any(f"Risk review round {ROUNDS}" in message.content for message in final),
        "newest non-protected turn retained":
            any(f"Routing round {ROUNDS}" in message.content for message in final),
        "core state untouched (round_number/is_validated)":
            final_state.round_number == 0 and final_state.is_validated is False,
        "core state untouched (errors/approved_tool_calls)":
            final_state.errors == [] and final_state.approved_tool_calls == [],
        "core state untouched (analysis_payload/raw_input/task_domain)":
            final_state.analysis_payload is None
            and final_state.raw_input == "Evaluate a 250 share NVDA long."
            and final_state.task_domain == "financial_trading_bot",
    }
    for name, passed in checks.items():
        print(f"  [{'PASS' if passed else 'FAIL'}] {name}")

    # An explicit raise, not `assert`: `python -O` strips assert statements and
    # would turn a failing guardrail into a silent success.
    failed = [name for name, passed in checks.items() if not passed]
    if failed:
        raise SystemExit("Guardrail invariant violated: " + "; ".join(failed))


if __name__ == "__main__":
    main()
