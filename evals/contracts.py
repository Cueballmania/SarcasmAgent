"""Dataset and explicit approved evaluation-run contracts."""

import hashlib
import json
from pathlib import Path
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.contracts import INSTRUCTION, Label, ModelLabel


class StrictModel(BaseModel):
    """Reject extra configuration and non-finite values."""

    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class Case(StrictModel):
    """A caller-curated row, never generated gold."""

    case_id: str = Field(pattern=r"^[A-Za-z0-9_-]{1,64}$")
    message: str = Field(min_length=1, max_length=2000)
    expected: Label
    group_id: str = Field(pattern=r"^[A-Za-z0-9_-]{1,64}$")
    split: Literal["pilot", "holdout"]
    tags: list[str] = Field(default_factory=list, max_length=20)
    provenance: Literal["synthetic", "licensed", "consented"]
    reviewed: bool = False


class Dataset(StrictModel):
    """Versioned scope and human review claims supplied by the operator."""

    version: str = Field(min_length=1, max_length=64)
    language: Literal["en"]
    annotation: Literal["intended", "perceived", "fixture"]
    review_reference: str | None = None
    fixture: bool = False
    cases: list[Case] = Field(min_length=1, max_length=2000)

    @model_validator(mode="after")
    def prevent_leakage(self) -> Self:
        """Reject duplicates and group leakage across pilot/holdout."""
        ids = [case.case_id for case in self.cases]
        if len(ids) != len(set(ids)):
            raise ValueError("Dataset case IDs must be unique")
        groups: dict[str, str] = {}
        for case in self.cases:
            if case.group_id in groups and groups[case.group_id] != case.split:
                raise ValueError("Related groups cannot cross pilot and holdout")
            groups[case.group_id] = case.split
        return self

    def reviewed_cases(self, split: str) -> list[Case]:
        """Fail closed before live dispatch; never treat fixtures as reviewed quality."""
        cases = [case for case in self.cases if case.split == split]
        if (
            self.fixture
            or self.annotation == "fixture"
            or not self.review_reference
            or not cases
            or not all(case.reviewed for case in cases)
        ):
            raise ValueError("Live evaluation requires reviewed non-fixture data and scope")
        return cases


class Thresholds(StrictModel):
    """No invented industry default thresholds."""

    macro_f1: float = Field(gt=0, le=1)
    coverage: float = Field(gt=0, le=1)
    per_class_precision: float = Field(ge=0, le=1)
    per_class_recall: float = Field(gt=0, le=1)
    max_failure_rate: float = Field(ge=0, lt=1)
    p95_ms: float = Field(gt=0)


class RunConfig(StrictModel):
    """Explicit authority, spend bounds and pre-holdout quality bars."""

    approval_reference: str = Field(min_length=1, max_length=128)
    revision: str = Field(pattern=r"^[a-f0-9]{40,64}$")
    max_requests: int = Field(ge=1, le=2000)
    max_concurrency: int = Field(ge=1, le=4)
    max_input_tokens: int = Field(ge=1, le=32000)
    max_output_tokens: int = Field(ge=32, le=512)
    max_cost_usd: float = Field(gt=0)
    input_usd_per_million: float = Field(gt=0)
    output_usd_per_million: float = Field(gt=0)
    thresholds: Thresholds


def file_hash(path: Path) -> str:
    """Hash artifact bytes, not paths or mutable display names."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def input_token_reserve(message: str) -> int:
    """Conservative byte-based text/schema reserve; not an exact tokenizer estimate."""
    return (
        len(message.encode())
        + len(INSTRUCTION.encode())
        + len(json.dumps(ModelLabel.model_json_schema()).encode())
        + 4096
    )


class Budget:
    """Reserve call/token/cost capacity synchronously before each provider dispatch."""

    def __init__(self, config: RunConfig) -> None:
        self.config = config
        self.requests = 0
        self.reserved_usd = 0.0

    def reserve(self, message: str) -> None:
        """Reject exhausted capacity without refunds for uncertain provider attempts."""
        tokens = input_token_reserve(message)
        config = self.config
        cost = (
            tokens * config.input_usd_per_million
            + config.max_output_tokens * config.output_usd_per_million
        ) / 1_000_000
        if (
            tokens > config.max_input_tokens
            or self.requests >= config.max_requests
            or self.reserved_usd + cost > config.max_cost_usd
        ):
            raise ValueError("Approved evaluation request/token/cost reservation cap reached")
        self.requests += 1
        self.reserved_usd += cost
