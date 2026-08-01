"""LangGraph construction and dependency wiring."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from contract import AgentState, GraphError, NodeName
from orchestrator.config import (
    AppSettings,
    build_chat_model,
    build_langsmith_client,
)
from orchestrator.guardrails.context_guard import ContextSummarizer
from orchestrator.guardrails.privacy_guard import (
    LangSmithTraceSink,
    SafeTracer,
)
from orchestrator.nodes.actor import make_actor_node
from orchestrator.nodes.analyzer import make_analyzer_node
from orchestrator.nodes.context_manager import LangChainContextSummarizer, make_context_manager_node
from orchestrator.nodes.coordinator import coordinator_node
from orchestrator.nodes.reporter import reporter_node
from orchestrator.nodes.validator import validator_node
from orchestrator.routing import route_from_coordinator
from orchestrator.tools.mock_tools import (
    build_default_tool_permissions,
    build_default_tool_registry,
)
from orchestrator.tools.registry import ToolRegistry
from orchestrator.utils.token_counting import TiktokenCounter, TokenCounter

NodeCallable = Callable[[AgentState], dict[str, object]]


@dataclass(frozen=True, slots=True)
class OrchestratorDependencies:
    chat_model: Any
    tool_registry: ToolRegistry
    token_counter: TokenCounter
    summarizer: ContextSummarizer
    tracer: SafeTracer


def build_runtime_dependencies(settings: AppSettings) -> OrchestratorDependencies:
    model = build_chat_model(settings)
    client = build_langsmith_client(settings)
    sink = LangSmithTraceSink(client, settings.langsmith.project)
    return OrchestratorDependencies(
        chat_model=model,
        tool_registry=build_default_tool_registry(),
        # Real BPE counts. chars/4 is biased LOW on numeric-dense trading text
        # (prices, tickers, RSI figures), so it under-triggers the guardrail.
        # TiktokenCounter degrades to the approximate counter on any failure.
        token_counter=TiktokenCounter(),
        summarizer=LangChainContextSummarizer(model),
        tracer=SafeTracer(sink),
    )


def _trace_node(name: NodeName, node: NodeCallable, tracer: SafeTracer) -> NodeCallable:
    def wrapped(state: AgentState) -> dict[str, object]:
        updates = dict(node(state))
        try:
            trace_result = tracer.record(
                name,
                inputs={"state": state.model_dump(mode="json")},
                outputs={"updates": updates},
                metadata={"round_number": state.round_number},
            )
        except Exception as exc:
            # External telemetry must not silently fail or corrupt core execution.
            errors = list(updates.get("errors", state.errors))
            errors.append(
                GraphError(
                    code="tracing_error",
                    message=f"Privacy-safe tracing failed: {exc}",
                    node=name,
                    recoverable=True,
                )
            )
            updates["errors"] = errors
            return updates
        updates["privacy_redaction_count"] = (
            state.privacy_redaction_count + trace_result.redaction_count
        )
        return updates

    return wrapped


def build_graph(
    dependencies: OrchestratorDependencies,
    *,
    # Sized to the traffic the graph is DESIGNED to carry at max_rounds=5 and
    # retain_recent=4, measured in real cl100k_base tokens:
    #
    #   system instruction (cli.py seed)                     14
    #   one summary record                                    9
    #   protected tool_output x5 (29 each, never evictable)  145
    #   retained recent turns x4 (133 each, worst case)      532
    #   ------------------------------------------------------
    #   irreducible steady-state floor                       700
    #   + 20% headroom, rounded to 50                        850
    #
    # The floor uses the LARGEST conversation turn, not the average, because a
    # limit below the floor cannot be met: the recent window and the protected
    # records are both un-evictable, so the guardrail would sit permanently over
    # budget and warn every round. One round of designed traffic adds 358 tok,
    # so the window reaches 1,058 and the guardrail engages and converges back
    # to the floor. At the previous 1,200 it never engaged even under full
    # designed traffic.
    #
    # DESIGN POSITION, stated because the two numbers must not sit unconnected:
    # the latency break-even for compression on this model is ~6,700-16,300
    # tokens of history (see student_6_tokens/METRICS.md). 850 is an order of
    # magnitude below that, so whenever this guardrail fires it is BY
    # CONSTRUCTION on the latency-costing side of the envelope: it buys token
    # cost with roughly one summarizer round trip of added latency. Sizing the
    # threshold at the crossover instead would leave it permanently inert,
    # because five rounds of designed traffic total only ~1,790 tokens and can
    # never reach 6,700. Given that choice, firing below break-even is the
    # correct one -- an inert guardrail protects nothing -- but it is a trade,
    # not a free win, and it is recorded here as such.
    token_limit: int = 850,
    retain_recent: int = 4,
) -> Any:
    """Construct and compile the integrated assignment-required LangGraph."""
    from langgraph.graph import END, START, StateGraph

    analyzer = make_analyzer_node(dependencies.chat_model)
    # Explicit permission matrix: any tool registered later that is not also
    # added to build_default_tool_permissions() is denied by default, rather
    # than silently allowed just because it exists in the registry.
    actor = make_actor_node(
        dependencies.tool_registry,
        permissions=build_default_tool_permissions(),
    )
    context_manager = make_context_manager_node(
        token_counter=dependencies.token_counter,
        summarizer=dependencies.summarizer,
        token_limit=token_limit,
        retain_recent=retain_recent,
    )

    builder = StateGraph(AgentState)
    builder.add_node(
        "context_manager",
        _trace_node("context_manager", context_manager, dependencies.tracer),
    )
    builder.add_node(
        "coordinator",
        _trace_node("coordinator", coordinator_node, dependencies.tracer),
    )
    builder.add_node(
        "worker_a_analyzer",
        _trace_node("worker_a_analyzer", analyzer, dependencies.tracer),
    )
    builder.add_node(
        "worker_b_actor",
        _trace_node("worker_b_actor", actor, dependencies.tracer),
    )
    builder.add_node(
        "worker_c_validator",
        _trace_node("worker_c_validator", validator_node, dependencies.tracer),
    )
    builder.add_node(
        "worker_d_reporter",
        _trace_node("worker_d_reporter", reporter_node, dependencies.tracer),
    )

    builder.add_edge(START, "context_manager")
    builder.add_edge("context_manager", "coordinator")
    builder.add_conditional_edges(
        "coordinator",
        route_from_coordinator,
        {
            "worker_a_analyzer": "worker_a_analyzer",
            "worker_b_actor": "worker_b_actor",
            "worker_d_reporter": "worker_d_reporter",
        },
    )
    builder.add_edge("worker_a_analyzer", "worker_c_validator")
    builder.add_edge("worker_b_actor", "worker_c_validator")
    builder.add_edge("worker_c_validator", "context_manager")
    builder.add_edge("worker_d_reporter", END)
    return builder.compile()
