"""Static UI copy and presentation-only fixture data."""

from __future__ import annotations

EXAMPLE_PROMPTS = (
    "Buy 10 AAPL shares because volume increased rapidly.",
    "Review AAPL momentum and decide whether a 10-share mock order fits risk limits.",
    "Compare MSFT and NVDA volume trends before selecting one simulated trade.",
    "Cancel mock order ORD-1042 if AAPL falls below the configured stop threshold.",
    "Analyze a simulated TSLA position and recommend a low-risk rebalance.",
)

FAILURES = (
    "Infinite Loop",
    "Structured Output Failure",
    "Rogue Tool Call",
    "Cascade Failure",
    "Privacy Leak",
    "Context Explosion",
)

SCENARIOS = (*FAILURES, "Multiple Failures", "Happy Path")

GUARDRAILS = (
    "Infinite Loop Guardrail",
    "Structured Output Guardrail",
    "Tool Authorization Guardrail",
    "Rollback Guardrail",
    "Privacy Guardrail",
    "Context Window Guardrail",
)

INDIVIDUAL_GUARDRAILS = (*GUARDRAILS, "No Injected Failure")

SCENARIO_GUARDRAIL = dict(zip(FAILURES, GUARDRAILS, strict=True)) | {
    "Happy Path": "No Injected Failure"
}

DEFAULT_INJECTED_FAILURES = (
    "Infinite Loop",
    "Rogue Tool Call",
    "Cascade Failure",
)

PIPELINE_NODES = (
    "Coordinator",
    "Analyzer",
    "Actor",
    "Validator",
    "Reporter",
)

GUARDRAIL_COPY = {
    "Infinite Loop": (
        "∞",
        "Infinite Loop Guardrail",
        "Stops the Coordinator after five visits and routes to a degraded report.",
        "Live backend",
    ),
    "Structured Output Failure": (
        "{}",
        "Structured Output Guardrail",
        "Validates Analyzer output and permits one correction retry.",
        "Mock UI state",
    ),
    "Rogue Tool Call": (
        "⌁",
        "Tool Authorization Guardrail",
        "Validates tool name, schema, permissions, and bounds before execution.",
        "Live backend",
    ),
    "Cascade Failure": (
        "↩",
        "Rollback Guardrail",
        "Rejects malformed Actor output before downstream business validation.",
        "Mock UI state",
    ),
    "Privacy Leak": (
        "◉",
        "Privacy Guardrail",
        "Redacts sensitive telemetry without mutating authoritative state.",
        "Mock UI state",
    ),
    "Context Explosion": (
        "≋",
        "Context Window Guardrail",
        "Prunes obsolete history and preserves essential instructions.",
        "Mock UI state",
    ),
}
