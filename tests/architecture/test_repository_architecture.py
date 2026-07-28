from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
EXPECTED_ENV = [
    "DEEPINFRA_API_TOKEN=",
    "DEEPINFRA_MODEL=",
    "DEEPINFRA_BASE_URL=",
    "LANGSMITH_API_KEY=",
    "LANGSMITH_PROJECT=",
]
DELIVERABLE_FOLDERS = [
    "student_1_loop",
    "student_2_silent",
    "student_3_rogue",
    "student_4_cascade",
    "student_5_trace",
    "student_6_tokens",
]
TEST_GROUPS = {
    "architecture",
    "configuration",
    "contract",
    "guardrails",
    "integration",
    "ui",
}


def test_env_example_is_exact_and_has_no_defaults() -> None:
    lines = ROOT.joinpath(".env.example").read_text().splitlines()
    assert lines == EXPECTED_ENV
    repository_text = "\n".join(
        path.read_text(errors="ignore")
        for path in [
            ROOT / ".env.example",
            ROOT / "README.md",
            *ROOT.joinpath("orchestrator").rglob("*.py"),
        ]
    )
    for legacy in (
        "OPENAI_API_KEY",
        "LANGCHAIN_API_KEY",
        "LANGCHAIN_TRACING_V2",
    ):
        assert legacy not in repository_text


def test_environment_access_and_chat_model_creation_are_centralized() -> None:
    env_readers: list[Path] = []
    chat_model_importers: list[Path] = []
    for path in ROOT.joinpath("orchestrator").rglob("*.py"):
        text = path.read_text()
        if "os.getenv" in text or "load_dotenv" in text:
            env_readers.append(path.relative_to(ROOT))
        if "from langchain_openai import ChatOpenAI" in text:
            chat_model_importers.append(path.relative_to(ROOT))
    assert env_readers == [Path("orchestrator/config.py")]
    assert chat_model_importers == [Path("orchestrator/config.py")]


def test_required_root_deliverables_exist() -> None:
    required = {
        "README.md",
        "DESIGN_DOCS.md",
        "INTERVIEW_STORIES.md",
        "contract.py",
        "main_system.py",
    }
    assert required.issubset({path.name for path in ROOT.iterdir() if path.is_file()})


def test_ui_is_isolated_under_app() -> None:
    assert ROOT.joinpath("app/app.py").is_file()
    assert not ROOT.joinpath("orchestrator/ui").exists()
    assert "streamlit run app/app.py" in ROOT.joinpath("README.md").read_text()


def test_student_deliverables_are_root_level_and_complete() -> None:
    actual = {
        path.name
        for path in ROOT.iterdir()
        if path.is_dir() and path.name.startswith("student_")
    }
    assert actual == set(DELIVERABLE_FOLDERS)
    for folder in DELIVERABLE_FOLDERS:
        directory = ROOT / folder
        assert {path.name for path in directory.iterdir() if path.is_file()} == {
            "snippet.py",
            "test_failure.py",
            "METRICS.md",
        }


def test_individual_snippets_are_import_only_views() -> None:
    for folder in DELIVERABLE_FOLDERS:
        tree = ast.parse(ROOT.joinpath(folder, "snippet.py").read_text())
        assert not any(
            isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
            for node in ast.walk(tree)
        )


def test_readme_and_project_guidance_use_conda() -> None:
    readme = ROOT.joinpath("README.md").read_text().lower()
    assert "conda create -n multi-agent" in readme
    for label in ("student_1", "student_2", "student_3", "student_4", "student_5", "student_6"):
        assert label in readme


def test_test_suite_is_grouped_by_responsibility() -> None:
    tests_root = ROOT / "tests"
    groups = {path.name for path in tests_root.iterdir() if path.is_dir()}
    assert TEST_GROUPS.issubset(groups)
    assert not list(tests_root.glob("test_*.py"))


def test_root_contains_only_required_python_entry_files() -> None:
    root_python_files = {path.name for path in ROOT.glob("*.py")}
    assert root_python_files == {"contract.py", "main_system.py"}
    main_source = ROOT.joinpath("main_system.py").read_text()
    assert "from orchestrator.cli import main, run_system" in main_source


def test_contract_models_are_not_redefined_in_production_package() -> None:
    forbidden = {
        "AgentState",
        "AnalysisPayload",
        "ToolExecutionResult",
        "ValidationResult",
        "GraphError",
    }
    for path in ROOT.joinpath("orchestrator").rglob("*.py"):
        tree = ast.parse(path.read_text())
        defined = {
            node.name
            for node in ast.walk(tree)
            if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef))
        }
        assert not (forbidden & defined), f"Contract model redefined in {path}"


def test_project_targets_python_312() -> None:
    pyproject = ROOT.joinpath("pyproject.toml").read_text()
    readme = ROOT.joinpath("README.md").read_text()
    assert 'requires-python = ">=3.12,<3.13"' in pyproject
    assert 'target-version = "py312"' in pyproject
    assert "conda create -n multi-agent python=3.12 -y" in readme


def test_only_completed_guardrails_are_marked_live_in_ui() -> None:
    mock_data = ROOT.joinpath("app/mock_data.py").read_text()
    assert mock_data.count('"Live backend"') == 2
    assert mock_data.count('"Mock UI state"') == 4
