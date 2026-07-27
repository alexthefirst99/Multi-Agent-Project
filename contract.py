"""
THE MANDATORY CONTRACT — frozen shared schema for the Generic Task Orchestrator.

This is the team's Day-1 deliverable per the assignment's Contract Rule.
Every node reads and writes state ONLY through this schema. Once the whole
team reviews and commits this file, it is FROZEN — extend it here, together,
before any individual guardrail work starts. Do not edit unilaterally.

STATUS: DRAFT, NOT YET FROZEN. Below is a proposed complete version, worked
out by reasoning through what each of the 6 guardrails needs to read/write —
but per the Contract Rule this still needs an actual team review/sign-off
before it counts as frozen. If anyone finds a gap once they start coding,
raise it with the team rather than editing this file solo.

Field ownership (who needs what, and why):
  - task_domain, raw_input        — shared task framing (all nodes)
  - round_number                  — Student 1 (Coordinator): compared against
                                     a hardcoded `5` in the routing guardrail,
                                     per the assignment's literal wording
                                     ("if round_number >= 5") — no separate
                                     max_rounds field needed.
  - error_log                     — SHARED, reused by every guardrail as the
                                     "what went wrong last" channel (Student 2's
                                     schema-validation error text, Student 3's
                                     blocked-tool message, Student 4's cascade
                                     rejection reason). Kept singular and
                                     generic to match the original example
                                     rather than adding a dedicated field per
                                     student.
  - analysis_payload              — Student 2 (Analyzer): the validated,
                                     structured-output result.
  - analysis_retry_count           — Student 2: tracks the single automated
                                     self-correcting retry budget.
  - proposed_tool_calls            — Student 3 (Actor): raw, not-yet-validated
                                     tool call requests, each shaped like
                                     {"tool_name": str, "arguments": dict}.
  - sanitized_tool_calls           — Student 3: tool *names* that passed the
                                     whitelist check (matches the original
                                     example's List[str] type).
  - tool_execution_results         — Student 3 writes it (result of executing
                                     each sanitized call), Student 4 (Validator)
                                     reads it to assert structural invariants
                                     before Worker C uses it.
  - is_validated                   — Student 4: whether Worker C's cross-check
                                     passed.
  - messages                       — Student 6 (Context/Token Manager): the
                                     running conversation/tool-output history
                                     it prunes.
  - messages_pruned_count          — Student 6: how many messages were dropped,
                                     for the before/after metrics table.

Student 5 (Tracing & Privacy) needs no dedicated field — its redaction
interceptor operates on the LangSmith callback payload at emit time, not on
AgentState directly.
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
    analysis_retry_count: int = 0
    proposed_tool_calls: List[Dict[str, Any]] = Field(default_factory=list)
    sanitized_tool_calls: List[str] = Field(default_factory=list)
    tool_execution_results: List[Dict[str, Any]] = Field(default_factory=list)
    messages: List[Dict[str, Any]] = Field(default_factory=list)
    messages_pruned_count: int = 0
