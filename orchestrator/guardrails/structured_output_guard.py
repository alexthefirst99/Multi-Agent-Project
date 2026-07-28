"""Structured output enforcement with exactly one correction retry."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Generic, Protocol, TypeVar

from pydantic import BaseModel, ValidationError

SchemaT = TypeVar("SchemaT", bound=BaseModel)


class StructuredInvoker(Protocol):
    def invoke(self, input_value: object) -> object: ...


class StructuredOutputGuardError(RuntimeError):
    """Raised after the initial parse and exactly one correction retry fail."""

    def __init__(self, first_error: str, retry_error: str) -> None:
        super().__init__(
            "Structured output failed twice. "
            f"Initial error: {first_error}; retry error: {retry_error}"
        )
        self.first_error = first_error
        self.retry_error = retry_error


@dataclass(frozen=True, slots=True)
class StructuredOutputResult(Generic[SchemaT]):
    value: SchemaT
    retry_count: int


def _parsing_exceptions() -> tuple[type[BaseException], ...]:
    exceptions: list[type[BaseException]] = [ValidationError, ValueError, TypeError]
    try:
        from langchain_core.exceptions import OutputParserException
    except ModuleNotFoundError:
        return tuple(exceptions)
    exceptions.append(OutputParserException)
    return tuple(exceptions)


def invoke_with_one_retry(
    invoker: StructuredInvoker,
    schema: type[SchemaT],
    input_value: object,
    *,
    append_correction: Callable[[object, str], object],
) -> StructuredOutputResult[SchemaT]:
    """Validate the first response, then permit one and only one correction."""

    def invoke_and_validate(payload: object) -> SchemaT:
        response = invoker.invoke(payload)
        return response if isinstance(response, schema) else schema.model_validate(response)

    try:
        return StructuredOutputResult(invoke_and_validate(input_value), retry_count=0)
    except _parsing_exceptions() as first_error:
        retry_input = append_correction(input_value, str(first_error))
        try:
            return StructuredOutputResult(invoke_and_validate(retry_input), retry_count=1)
        except _parsing_exceptions() as retry_error:
            raise StructuredOutputGuardError(
                str(first_error), str(retry_error)
            ) from retry_error
