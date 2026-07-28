from __future__ import annotations

import importlib
import sys
import types
from contextlib import contextmanager

from contract import AgentState, AnalysisPayload


class FakeMessage:
    def __init__(self, content: str) -> None:
        self.content = content


class FakeStructuredRunnable:
    def __init__(self, schema: type[AnalysisPayload]) -> None:
        self._schema = schema

    def invoke(self, input_value: object) -> AnalysisPayload:
        return self._schema(
            ticker="AAPL",
            side="buy",
            quantity=10,
            confidence=0.8,
            rationale="Unusual volume supports a small mocked position.",
            risk_level="medium",
        )


class FakeChatOpenAI:
    def __init__(self, **kwargs: object) -> None:
        self.kwargs = kwargs

    def with_structured_output(self, schema: type[AnalysisPayload]) -> FakeStructuredRunnable:
        return FakeStructuredRunnable(schema)

    def invoke(self, input_value: object) -> FakeMessage:
        return FakeMessage("Older context summarized.")


class FakeCompiledGraph:
    def __init__(self, builder: "FakeStateGraph") -> None:
        self._builder = builder

    @staticmethod
    def _apply(state: AgentState, updates: dict[str, object]) -> AgentState:
        data = state.model_dump(mode="python")
        data.update(updates)
        return AgentState.model_validate(data)

    def invoke(self, initial_state: AgentState) -> AgentState:
        state = initial_state
        current = self._builder.edges["__start__"]
        for _ in range(30):
            if current == "__end__":
                return state
            updates = self._builder.nodes[current](state)
            state = self._apply(state, updates)
            if current in self._builder.conditional:
                router, mapping = self._builder.conditional[current]
                current = mapping[router(state)]
            else:
                current = self._builder.edges[current]
        raise RuntimeError("Fake graph exceeded its deterministic safety limit.")


class FakeStateGraph:
    def __init__(self, schema: object) -> None:
        self.schema = schema
        self.nodes: dict[str, object] = {}
        self.edges: dict[object, object] = {}
        self.conditional: dict[str, tuple[object, dict[str, str]]] = {}

    def add_node(self, name: str, node: object) -> None:
        self.nodes[name] = node

    def add_edge(self, source: object, target: object) -> None:
        self.edges[source] = target

    def add_conditional_edges(
        self, source: str, router: object, mapping: dict[str, str]
    ) -> None:
        self.conditional[source] = (router, mapping)

    def compile(self) -> FakeCompiledGraph:
        return FakeCompiledGraph(self)


def install_fake_dependencies(monkeypatch) -> None:
    openai_module = types.ModuleType("langchain_openai")
    openai_module.ChatOpenAI = FakeChatOpenAI
    monkeypatch.setitem(sys.modules, "langchain_openai", openai_module)

    messages_module = types.ModuleType("langchain_core.messages")
    messages_module.HumanMessage = FakeMessage
    messages_module.SystemMessage = FakeMessage
    core_module = types.ModuleType("langchain_core")
    core_module.messages = messages_module
    exceptions_module = types.ModuleType("langchain_core.exceptions")

    class OutputParserException(ValueError):
        pass

    exceptions_module.OutputParserException = OutputParserException
    monkeypatch.setitem(sys.modules, "langchain_core", core_module)
    monkeypatch.setitem(sys.modules, "langchain_core.messages", messages_module)
    monkeypatch.setitem(sys.modules, "langchain_core.exceptions", exceptions_module)

    graph_module = types.ModuleType("langgraph.graph")
    graph_module.START = "__start__"
    graph_module.END = "__end__"
    graph_module.StateGraph = FakeStateGraph
    langgraph_module = types.ModuleType("langgraph")
    langgraph_module.graph = graph_module
    monkeypatch.setitem(sys.modules, "langgraph", langgraph_module)
    monkeypatch.setitem(sys.modules, "langgraph.graph", graph_module)

    class FakeLangSmithClient:
        def __init__(self, **kwargs: object) -> None:
            self.kwargs = kwargs
            self.runs: list[dict[str, object]] = []

        def create_run(self, **kwargs: object) -> None:
            self.runs.append(dict(kwargs))

    @contextmanager
    def fake_tracing_context(**kwargs: object):
        yield

    langsmith_module = types.ModuleType("langsmith")
    langsmith_module.Client = FakeLangSmithClient
    langsmith_module.tracing_context = fake_tracing_context
    monkeypatch.setitem(sys.modules, "langsmith", langsmith_module)


def test_main_system_runs_end_to_end_without_network(monkeypatch) -> None:
    install_fake_dependencies(monkeypatch)
    monkeypatch.setenv("DEEPINFRA_API_TOKEN", "test-token")
    monkeypatch.setenv("DEEPINFRA_MODEL", "test/model")
    monkeypatch.setenv(
        "DEEPINFRA_BASE_URL", "https://api.deepinfra.com/v1/openai"
    )
    monkeypatch.setenv("LANGSMITH_API_KEY", "test-langsmith-key")
    monkeypatch.setenv("LANGSMITH_PROJECT", "test-project")

    main_system = importlib.import_module("main_system")
    final_state = main_system.run_system("AAPL rose on unusual volume.")

    assert final_state.is_validated is True
    assert final_state.round_number == 3
    assert final_state.final_report is not None
    assert final_state.final_report.startswith("COMPLETE REPORT")
