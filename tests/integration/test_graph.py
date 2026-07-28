from __future__ import annotations

import sys
import types
from typing import Sequence

from contract import AgentState, AnalysisPayload, MessageRecord
from orchestrator.graph import OrchestratorDependencies, build_graph
from orchestrator.guardrails.privacy_guard import NullTraceSink, SafeTracer
from orchestrator.nodes.actor import make_actor_node
from orchestrator.nodes.analyzer import make_analyzer_node
from orchestrator.nodes.context_manager import make_context_manager_node
from orchestrator.nodes.coordinator import coordinator_node
from orchestrator.nodes.reporter import reporter_node
from orchestrator.nodes.validator import validator_node
from orchestrator.tools.mock_tools import build_default_tool_registry
from orchestrator.utils.token_counting import ApproximateTokenCounter

VALID_ANALYSIS = AnalysisPayload(
    ticker="AAPL",
    side="buy",
    quantity=10,
    confidence=0.8,
    rationale="Unusual volume supports a small mocked position.",
    risk_level="medium",
)


class FakeStructuredModel:
    def invoke(self, input_value: object) -> AnalysisPayload:
        return VALID_ANALYSIS


class FakeChatModel:
    def with_structured_output(self, schema: object) -> FakeStructuredModel:
        return FakeStructuredModel()


class FakeSummarizer:
    def summarize(self, messages: Sequence[MessageRecord]) -> str:
        return "Older context summarized."


class FakeStateGraph:
    last_instance: "FakeStateGraph | None" = None

    def __init__(self, schema: object) -> None:
        self.schema = schema
        self.nodes: dict[str, object] = {}
        self.edges: list[tuple[object, object]] = []
        self.conditional: list[tuple[str, object, dict[str, str]]] = []
        FakeStateGraph.last_instance = self

    def add_node(self, name: str, node: object) -> None:
        self.nodes[name] = node

    def add_edge(self, source: object, target: object) -> None:
        self.edges.append((source, target))

    def add_conditional_edges(
        self, source: str, router: object, mapping: dict[str, str]
    ) -> None:
        self.conditional.append((source, router, mapping))

    def compile(self) -> "FakeStateGraph":
        return self


def dependencies() -> OrchestratorDependencies:
    return OrchestratorDependencies(
        chat_model=FakeChatModel(),
        tool_registry=build_default_tool_registry(),
        token_counter=ApproximateTokenCounter(),
        summarizer=FakeSummarizer(),
        tracer=SafeTracer(NullTraceSink()),
    )


def apply(state: AgentState, updates: dict[str, object]) -> AgentState:
    data = state.model_dump(mode="python")
    data.update(updates)
    return AgentState.model_validate(data)


def test_graph_declares_required_nodes_and_edges(monkeypatch) -> None:
    graph_module = types.ModuleType("langgraph.graph")
    graph_module.START = "__start__"
    graph_module.END = "__end__"
    graph_module.StateGraph = FakeStateGraph
    package = types.ModuleType("langgraph")
    package.graph = graph_module
    monkeypatch.setitem(sys.modules, "langgraph", package)
    monkeypatch.setitem(sys.modules, "langgraph.graph", graph_module)

    compiled = build_graph(dependencies())
    assert compiled is FakeStateGraph.last_instance
    assert set(compiled.nodes) == {
        "context_manager",
        "coordinator",
        "worker_a_analyzer",
        "worker_b_actor",
        "worker_c_validator",
        "worker_d_reporter",
    }
    assert ("__start__", "context_manager") in compiled.edges
    assert ("worker_d_reporter", "__end__") in compiled.edges
    assert compiled.conditional[0][0] == "coordinator"


def test_integrated_deterministic_flow_reaches_complete_report() -> None:
    state = AgentState(
        raw_input="AAPL rose on unusual volume.",
        messages=[MessageRecord(role="user", content="AAPL rose on unusual volume.")],
    )
    context_node = make_context_manager_node(
        token_counter=ApproximateTokenCounter(),
        summarizer=FakeSummarizer(),
        token_limit=1_200,
        retain_recent=4,
    )
    analyzer = make_analyzer_node(
        FakeChatModel(),
        message_builder=lambda state: [state.raw_input],
        correction_builder=lambda value, error: [value, error],
    )
    actor = make_actor_node(build_default_tool_registry())

    state = apply(state, context_node(state))
    state = apply(state, coordinator_node(state))
    assert state.next_route == "worker_a_analyzer"
    state = apply(state, analyzer(state))
    state = apply(state, validator_node(state))

    state = apply(state, context_node(state))
    state = apply(state, coordinator_node(state))
    assert state.next_route == "worker_b_actor"
    state = apply(state, actor(state))
    state = apply(state, validator_node(state))
    assert state.is_validated is True

    state = apply(state, context_node(state))
    state = apply(state, coordinator_node(state))
    assert state.next_route == "worker_d_reporter"
    state = apply(state, reporter_node(state))
    assert state.final_report is not None
    assert state.final_report.startswith("COMPLETE REPORT")
    assert state.round_number == 3
