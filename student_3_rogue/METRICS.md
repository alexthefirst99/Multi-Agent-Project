# Metrics — Student 3 — Rogue Tool Execution

Measured by running `test_failure.py` (see repo for the exact script) against
one rogue call (`transfer_client_funds`, not on the whitelist at all), one
whitelisted-tool-but-bad-argument call (`execute_trade` with an unauthorized
`bypass_risk_check` flag), and one legitimate call (`execute_trade` with only
`ticker`/`side`/`quantity`).

| Metric | Before (guardrail disabled) | After (guardrail enabled) |
|---|---|---|
| Unauthorized tool calls executed | 1 / 1 (100%) | 0 / 1 (0%) |
| Unauthorized argument calls executed | 1 / 1 (100%, not even checked) | 0 / 1 (0%) |
| Legitimate calls still executed | 1 / 1 | 1 / 1 (unaffected) |
| `InvalidToolCallException` raised on violation | Never (no check exists) | Every time |

TODO once a real domain/LLM is wired in: replace `TOOL_WHITELIST` in
`snippet.py` with the real tool surface, re-run against realistic
jailbreak-style prompts, and update the counts above with real (non-synthetic)
attack attempts if the numbers differ.
