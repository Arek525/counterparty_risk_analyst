"""Validated data contracts. Model output can never provide executable rules."""

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

Scalar = str | int | float | bool


class Source(BaseModel):
    model_config = ConfigDict(extra="forbid")
    chunk_id: str
    document_id: str
    location: str | dict
    quote: str = Field(min_length=1, max_length=6000)


class Requirement(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str = Field(min_length=1, max_length=100)
    title: str = Field(min_length=1, max_length=500)
    field: str = Field(min_length=1, max_length=100)
    operator: Literal["eq", "lte", "gte", "contains", "present", "manual"]
    expected: Any
    severity: Literal["Low", "Medium", "High"]
    applicability: dict[str, Scalar] = Field(default_factory=dict)
    source: Source
    evaluation_method: Literal["deterministic", "llm", "manual"]

    @model_validator(mode="after")
    def check_comparison(self):
        supported = {
            "retention_days",
            "notification_hours",
            "hosting_region",
            "subprocessors_region",
            "mfa",
            "encryption_at_rest",
            "dpa_signed",
        }
        if self.field not in supported and (
            self.operator != "manual"
            or self.evaluation_method != "manual"
            or self.expected is not None
        ):
            raise ValueError("Unsupported fields require manual evaluation with expected null")
        if self.operator in {"lte", "gte"} and (
            isinstance(self.expected, bool) or not isinstance(self.expected, (int, float))
        ):
            raise ValueError("Numeric operator requires numeric expected value")
        if not isinstance(self.expected, (str, int, float, bool, list, type(None))):
            raise ValueError("Expected value must be a scalar or list")
        return self


class Fact(BaseModel):
    model_config = ConfigDict(extra="forbid")
    field: str
    value: Scalar
    scope: str = "unspecified"
    period: str = "unspecified"
    source: Source
    evidence_type: Literal["declaration", "independent"] = "declaration"


class FactBatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    facts: list[Fact] = Field(max_length=200)


class RequirementBatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    requirements: list[Requirement] = Field(max_length=100)


def validate_source(source: dict, chunks: list[dict]) -> None:
    """Reject hallucinated, cross-document or modified citations."""
    item = Source.model_validate(source)
    eligible = {str(c["id"]): c for c in chunks}
    chunk = eligible.get(item.chunk_id)
    if not chunk or (
        str(chunk["document_id"]) != item.document_id
        or chunk["location"] != item.location
        or item.quote not in chunk["text"]
    ):
        raise ValueError("Source quote does not resolve to an eligible chunk")


def validate_requirements(requirements: list[dict], chunks: list[dict]) -> list[dict]:
    batch = RequirementBatch.model_validate({"requirements": requirements})
    ids = [r.id for r in batch.requirements]
    if len(set(ids)) != len(ids) or not ids:
        raise ValueError("Requirements must have unique IDs and cannot be empty")
    result = batch.model_dump()["requirements"]
    for requirement in result:
        validate_source(requirement["source"], [c for c in chunks if c.get("kind") == "policy"])
    return result
