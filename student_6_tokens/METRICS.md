# Metrics - Context Management - Context Window Explosion

Measured by `python student_6_tokens/test_failure.py` with the deterministic approximate token counter.

Config note: the fixture runs `token_limit=180`, `retain_recent=2`, a scaled-down version of the graph defaults (`1200`, `4`) so the failure reproduces deterministically in a 14-message history.

| Metric | Without guardrail | With guardrail |
|---|---:|---:|
| Messages retained | 14 | 3 |
| Estimated input tokens | 1,729 | 122 |
| Estimated token reduction | - | 92.9% |
| Older messages summarized | 0 | 10 |
| Net messages pruned | 0 | 11 |
| Obsolete tool outputs retained | 1 | 0 |
| System instructions preserved | Yes | Yes |
| Estimated input cost per 1,000 runs | $0.121 | $0.009 |

Input tokens only, at DeepInfra's published rate of $0.07/1M for google/gemma-4-26B-A4B-it (checked July 2026). Per-event cost at fixture scale is a fraction of a cent, so it is shown per 1,000 runs. Real savings compound beyond this: the Coordinator re-sends the full history on every routing decision, so unpruned history is paid for repeatedly within a single run.

## Where the reduction comes from

Per-stage measurements under the approximate counter, same fixture and same settings.

| Stage | Messages | Tokens | Delta tokens |
|---|---:|---:|---:|
| 0. Input history | 14 | 1,729 | - |
| 1. Obsolete tool outputs pruned | 13 | 1,519 | -210 |
| 2. Essential / recent partition | 3 | 169 | -1,350 |
| 3. Summary inserted | 4 | 182 | +13 |
| 4. Hard-cap eviction | 3 | 122 | -60 |

The partition step is the main win: it removes 1,350 of the 1,607 total tokens cut, or about 84.0% of the reduction. Obsolete tool-output pruning contributes another 210 tokens, while the final hard-cap pass trims the small overflow left after inserting the summary.

## Estimator validation

The same fixture measured with real BPE token counts, to show how far the chars/4 estimate is off.

| Counter | Messages retained | Input tokens | Reduction |
|---|---:|---:|---:|
| ApproximateTokenCounter (chars/4) | 14 -> 3 | 1,729 -> 122 | 92.9% |
| TiktokenCounter (cl100k_base) | 14 -> 4 | 1,423 -> 91 | 93.6% |

| Point | chars/4 | tiktoken | Absolute | Over-estimate |
|---|---:|---:|---:|---:|
| Before pruning | 1,729 | 1,423 | +306 | +21.5% |
| After pruning | 122 | 91 | +31 | +34.1% |

Measured with encoding `cl100k_base`, `using_fallback=False`, so these are real BPE counts and not a silent fallback to the estimate. Note that `cl100k_base` is an OpenAI tokenizer while the configured model is `google/gemma-4-26B-A4B-it` served through DeepInfra, so the tiktoken column is itself a proxy for the model's true tokenization rather than an exact match.

## Per-message drift

Raw fixture, before any pruning. The ten historical turns are byte-identical in length and drift, so they are collapsed into a single row.

| Message | Chars | chars/4 | tiktoken | Error |
|---|---:|---:|---:|---:|
| System instruction ("Never execute real trades.") | 26 | 7 | 5 | +40.0% |
| Obsolete tool output | 840 | 210 | 121 | +73.6% |
| Historical turn (x10) | 540 | 135 | 122 | +10.7% |
| Recent decision | 240 | 60 | 31 | +93.5% |
| Recent validation question | 405 | 102 | 46 | +121.7% |

The estimator's error runs about 11% on ordinary conversational turns but 74% on the tool payload and 122% on the repeated validation question. BPE tokenizers merge recurring substrings into single tokens whereas a character count can't see repetition at all. Because of this, chars/4 is least accurate on repetitive content that causes the bloat. Since chars/4 over estimates, the guardrail triggers earlier than what a real token count would require. This is conservative, but it also means token_limit=180 is really a character budget wearing a token label.

## Notes

**Why `test_failure.py` stays on the approximate counter.** The reproduction script must produce identical output on a cold machine. `cl100k_base` is cached locally here but may require a network download elsewhere, and `TiktokenCounter` falls back to the approximate counter on failure, which would make the script print different numbers than the recorded walkthrough. Verified by running `test_failure.py` with a `sys.meta_path` hook that raises `ImportError` on any `tiktoken` import: output was identical to the normal run, and `tiktoken` was absent from `sys.modules` both after importing `snippet` and after the full run. The `tiktoken` import lives inside the encoding loader, so it is never reached unless a `TiktokenCounter` actually counts.

**What "net messages pruned" counts.** It is a net length delta, `len(original) - len(final)`, not a count of records removed. Because the guardrail inserts one summary message, the delta trails the number of records physically dropped by one whenever summarization runs: under the approximate counter 12 records are removed and 1 summary is added, netting 11.

The two counters diverge on message count (3 vs 4) and net pruned (11 vs 10) for a single reason. After the summary is inserted at stage 3, the approximate counter measures 182 tokens against the 180 limit, so the hard-cap eviction loop fires and drops one more message to reach 122. The tiktoken counter measures 91 at the same stage, already under the limit, so the loop is a no-op and the fourth message survives. Same history, same settings, different measuring stick.

The hard cap eviction loop stops when every remaining message is marked essential, returning history that is still over the limit rather than dropping a system instruction. For this domain, the system message is the constraint that keeps the agent from executing real trades, and losing it fails without showing an exception or error. The agent just forgets its hard rule when the history gets too long and confusing. The token budget is a soft target but the invariants are hard.