"""
THE MANDATORY CONTRACT — frozen shared schema for the Generic Task Orchestrator.

This is the team's Day-1 deliverable per the assignment's Contract Rule.
Every node reads and writes state ONLY through this schema. Once the whole
team reviews and commits this file, it is FROZEN — extend it here, together,
before any individual guardrail work starts. Do not edit unilaterally.

TODO(team, Day 1): review this against all 6 guardrails and add whatever
fields are actually needed (e.g. state for tracking tool call proposals,
context/message history, per-node rejection reasons) before freezing.

ADDED BY ALEX (student_3_rogue) — needs team review before freeze:
  `proposed_tool_calls` — the raw, not-yet-validated tool call requests
  Worker B receives, each shaped like {"tool_name": str, "arguments": dict}.
  `sanitized_tool_calls` (already in the original example) holds only the
  tool *names* that passed the whitelist check.
"""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class AgentState(BaseModel):
    task_domain: str
    raw_input: str
    round_number: int = 0
    is_validated: bool = False
    error_log: Optional[str] = None
    analysis_payload: Dict[str, Any] = Field(default_factory=dict)
    proposed_tool_calls: List[Dict[str, Any]] = Field(default_factory=list)
    sanitized_tool_calls: List[str] = Field(default_factory=list)
