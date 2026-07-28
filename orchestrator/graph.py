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
from orchestrator.tools.mock_tools import build_default_tool_registry
from orchestrator.tools.registry import ToolRegistry
from orchestrator.utils.token_counting import ApproximateTokenCounter, TokenCounter

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
        token_counter=ApproximateTokenCounter(),
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
    token_limit: int = 1_200,
    retain_recent: int = 4,
) -> Any:
    """Construct and compile the integrated assignment-required LangGraph."""
    from langgraph.graph import END, START, StateGraph

    analyzer = make_analyzer_node(dependencies.chat_model)
    actor = make_actor_node(dependencies.tool_registry)
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
