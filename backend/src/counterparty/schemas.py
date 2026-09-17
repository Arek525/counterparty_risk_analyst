"""Strict public inputs: no executable rules or user-controlled authorization fields."""

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True, allow_inf_nan=False)


class Login(Input):
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=1, max_length=200)


class Relationship(Input):
    purpose: str = Field(default="", max_length=4000)
    data_shared: str = Field(default="", max_length=4000)
    system_access: str = Field(default="", max_length=4000)
    business_criticality: Literal["low", "medium", "high"] = "medium"
    personal_data: bool = False
    privileged_access: bool = False


class CaseCreate(Input):
    name: str = Field(min_length=1, max_length=200)
    counterparty_name: str = Field(min_length=1, max_length=200)
    relationship: Relationship = Field(default_factory=Relationship)


class CasePatch(Input):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    relationship: Relationship | None = None


class Source(Input):
    chunk_id: UUID
    document_id: UUID
    location: dict
    quote: str = Field(min_length=1, max_length=6000)


class Requirement(Input):
    id: str = Field(min_length=1, max_length=150)
    title: str = Field(min_length=1, max_length=500)
    field: str = Field(min_length=1, max_length=100, pattern=r"^[a-z][a-z0-9_]*$")
    operator: Literal["eq", "lte", "gte", "contains", "present", "manual"]
    expected: str | int | float | bool | list[str] | None = None
    severity: Literal["Low", "Medium", "High"]
    applicability: dict[str, str | bool | int] = Field(default_factory=dict)
    source: Source
    evaluation_method: Literal["deterministic", "llm", "manual"] = "deterministic"

    @field_validator("applicability")
    @classmethod
    def valid_context(cls, value):
        if not set(value).issubset(Relationship.model_fields):
            raise ValueError("Unsupported relationship context")
        return value

    @model_validator(mode="after")
    def valid_operator(self):
        if self.operator in {"lte", "gte"} and (
            isinstance(self.expected, bool) or not isinstance(self.expected, (int, float))
        ):
            raise ValueError("Numeric operator requires numeric expected value")
        if self.operator == "contains" and not isinstance(self.expected, str):
            raise ValueError("Contains requires a text value")
        if self.operator == "manual" and self.evaluation_method != "manual":
            raise ValueError("Manual rules require manual evaluation")
        return self


class NarrativeRequirement(Input):
    id: str = Field(min_length=1, max_length=100)
    title: str = Field(min_length=1, max_length=500)
    description: str = Field(min_length=1, max_length=12000)
    applicability_text: str = Field(default="All relationships", min_length=1, max_length=6000)
    severity: Literal["Low", "Medium", "High"]
    source: Source


class PolicyProposal(Input):
    name: str = Field(min_length=1, max_length=200)
    document_ids: list[UUID] = Field(min_length=1, max_length=30)
    regenerate: bool = False


class RunCreate(Input):
    policy_version_id: UUID
    retrieval_variant: Literal["hybrid"] = "hybrid"


class DecisionCreate(Input):
    decision: Literal["accepted", "rejected", "needs_information"]
    rationale: str = Field(min_length=5, max_length=10000)


class InformationRequestDraft(Input):
    text: str = Field(min_length=5, max_length=10000)
