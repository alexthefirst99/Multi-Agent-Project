"""
Student 3 — Reproduction script: Triggers unauthorized tool execution

Runs the Actor node WITHOUT the tool-whitelist guardrail (a naive stand-in
that executes whatever it's handed), showing a rogue/destructive tool call
executing unconditionally. Then runs the real, guardrailed
worker_b_actor_node from snippet.py and shows it blocking the same call.

No LLM calls — the "proposed" tool calls are set directly on AgentState to
keep this deterministic. Per the assignment's Strict Safety Mandate, every
"execution" here (guarded or not) is a mock print — never real infrastructure.
"""

from contract import AgentState
from snippet import worker_b_actor_node

SAMPLE_DOMAIN = "financial_trading"
SAMPLE_INPUT = "Market signal: AAPL showing unusual volume spike, +4% in 10 minutes."

# Not on the whitelist at all — a jailbreak attempting to move client funds directly.
ROGUE_CALL = {"tool_name": "transfer_client_funds", "arguments": {"account_id": "*", "amount": 999999}}
# A whitelisted tool, but with an extra argument that would bypass a risk check.
UNAUTHORIZED_ARG_CALL = {
    "tool_name": "execute_trade",
    "arguments": {"ticker": "AAPL", "side": "buy", "quantity": 100, "bypass_risk_check": True},
}
LEGITIMATE_CALL = {"tool_name": "execute_trade", "arguments": {"ticker": "AAPL", "side": "buy", "quantity": 100}}


def actor_node_without_guardrail(state: AgentState) -> AgentState:
    """Stand-in for a naive Actor with no whitelist check at all."""
    state.sanitized_tool_calls = []
    for call in state.proposed_tool_calls:
        tool_name = call.get("tool_name")
        arguments = call.get("arguments", {})
        print(f"MOCK EXECUTION: would call '{tool_name}' with {arguments}")
        state.sanitized_tool_calls.append(tool_name)
    return state


if __name__ == "__main__":
    print("=== FAILURE MODE (guardrail disabled) ===")
    broken_state = AgentState(task_domain=SAMPLE_DOMAIN, raw_input=SAMPLE_INPUT, proposed_tool_calls=[ROGUE_CALL])
    broken_result = actor_node_without_guardrail(broken_state)
    print(f"Executed tool calls: {broken_result.sanitized_tool_calls}")
    assert broken_result.sanitized_tool_calls == ["transfer_client_funds"]
    print("Rogue call executed unconditionally — no whitelist check in place.\n")

    print("=== GUARDRAIL CHECK: rogue tool blocked (snippet.py) ===")
    guarded_state = AgentState(task_domain=SAMPLE_DOMAIN, raw_input=SAMPLE_INPUT, proposed_tool_calls=[ROGUE_CALL])
    guarded_result = worker_b_actor_node(guarded_state)
    print(f"Executed tool calls: {guarded_result.sanitized_tool_calls}")
    print(f"Error log: {guarded_result.error_log}")
    assert guarded_result.sanitized_tool_calls == []
    assert guarded_result.error_log is not None
    print("PASS: guardrail blocked the unauthorized tool before execution.\n")

    print("=== GUARDRAIL CHECK: unauthorized argument blocked ===")
    bad_arg_state = AgentState(task_domain=SAMPLE_DOMAIN, raw_input=SAMPLE_INPUT, proposed_tool_calls=[UNAUTHORIZED_ARG_CALL])
    bad_arg_result = worker_b_actor_node(bad_arg_state)
    assert bad_arg_result.sanitized_tool_calls == []
    assert "unauthorized arguments" in bad_arg_result.error_log
    print("PASS: whitelisted tool with an unauthorized argument was still blocked.\n")

    print("=== GUARDRAIL CHECK: legitimate call still executes ===")
    ok_state = AgentState(task_domain=SAMPLE_DOMAIN, raw_input=SAMPLE_INPUT, proposed_tool_calls=[LEGITIMATE_CALL])
    ok_result = worker_b_actor_node(ok_state)
    assert ok_result.sanitized_tool_calls == ["execute_trade"]
    assert ok_result.error_log is None
    print("PASS: a whitelisted call with authorized arguments executes normally.")
