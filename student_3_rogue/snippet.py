"""
Student 3 — Worker B (Actor)
Critical Failure Mode: Rogue Tool Execution

The Failure: Worker B receives a prompt that triggers a jailbreak or an
un-vetted tool invocation parameter, generating a destructive call payload.

The Guardrail: Build a functional, dynamic tool runtime execution
middleware. Intercept the LLM's requested tool call array before execution.
Validate the request against a hardcoded lookup configuration matrix. If the
tool or argument parameters violate the runtime permissions, throw an
InvalidToolCallException and abort execution.
"""

from contract import AgentState

# Hardcoded lookup configuration matrix: tool name -> the argument keys it
# accepts. Anything not listed here is rejected before execution, not after.
# TODO(domain): replace with the real tool surface once the domain is chosen.
TOOL_WHITELIST: dict[str, set[str]] = {
    "send_notification": {"channel", "message"},
    "restart_service": {"service_name"},
    "create_report_draft": {"title", "body"},
}


class InvalidToolCallException(Exception):
    """Raised when a proposed tool call violates the runtime whitelist."""


def validate_tool_call(tool_name: str, arguments: dict) -> None:
    """Raise InvalidToolCallException if `tool_name`/`arguments` isn't authorized."""
    if tool_name not in TOOL_WHITELIST:
        raise InvalidToolCallException(f"Tool '{tool_name}' is not in the runtime whitelist.")

    allowed_arguments = TOOL_WHITELIST[tool_name]
    unexpected_arguments = set(arguments) - allowed_arguments
    if unexpected_arguments:
        raise InvalidToolCallException(
            f"Tool '{tool_name}' called with unauthorized arguments: {unexpected_arguments}"
        )


def mock_execute_tool(tool_name: str, arguments: dict) -> dict:
    """
    Every 'execution' here is a mock print — per the assignment's Strict
    Safety Mandate, this must never touch real infrastructure.
    TODO(domain): swap the print for whatever safe mock behavior fits the
    chosen domain, but never call a real destructive command.
    """
    print(f"MOCK EXECUTION: would call '{tool_name}' with {arguments}")
    return {"tool_name": tool_name, "status": "mock_success"}


def worker_b_actor_node(state: AgentState) -> AgentState:
    state.sanitized_tool_calls = []
    state.tool_execution_results = []
    state.error_log = None

    for call in state.proposed_tool_calls:
        tool_name = call.get("tool_name")
        arguments = call.get("arguments", {})

        try:
            validate_tool_call(tool_name, arguments)
        except InvalidToolCallException as exc:
            # THE GUARDRAIL: abort execution entirely on the first violation —
            # nothing in this batch partially executes.
            state.error_log = f"Rogue tool execution blocked: {exc}"
            state.sanitized_tool_calls = []
            state.tool_execution_results = []
            return state

        result = mock_execute_tool(tool_name, arguments)
        state.sanitized_tool_calls.append(tool_name)
        # Handed off to Worker C (Student 4) — see contract.py's field
        # ownership notes. The exact shape here (tool_name + status) is what
        # Student 4's sanitize node is expected to assert invariants on.
        state.tool_execution_results.append(result)

    return state
