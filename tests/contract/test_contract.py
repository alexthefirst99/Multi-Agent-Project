from __future__ import annotations

import pytest
from pydantic import ValidationError

from contract import (
    CONTRACT_FROZEN,
    CONTRACT_VERSION,
    MAX_COORDINATOR_ROUNDS,
    AgentState,
    AnalysisPayload,
    MessageRecord,
)


def test_contract_is_frozen_and_strict() -> None:
    assert CONTRACT_FROZEN is True
    assert CONTRACT_VERSION == "2.0.0"
    assert MAX_COORDINATOR_ROUNDS == 5
    with pytest.raises(ValidationError):
        AgentState(raw_input="signal", unknown_field=True)
    with pytest.raises(ValidationError):
        AgentState(raw_input="signal", max_rounds=6)


def test_typed_analysis_normalizes_ticker_and_rejects_missing_fields() -> None:
    payload = AnalysisPayload(
        ticker="aapl",
        side="buy",
        quantity=10,
        confidence=0.8,
        rationale="Unusual volume with a controlled mock position.",
        risk_level="medium",
    )
    assert payload.ticker == "AAPL"
    with pytest.raises(ValidationError):
        AnalysisPayload.model_validate(
            {
                "side": "buy",
                "quantity": 10,
                "confidence": 0.8,
                "rationale": "Missing the critical ticker identifier.",
                "risk_level": "medium",
            }
        )


def test_system_messages_are_essential() -> None:
    message = MessageRecord(role="system", content="Do not execute real trades.")
    assert message.essential is True
    assert message.kind == "system_instruction"
