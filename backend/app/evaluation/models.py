from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class EvaluationCase(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str = Field(min_length=1, max_length=100)
    question: str = Field(min_length=1, max_length=2000)
    expected_document_id: UUID | None = None
    expected_chunk_ids: list[UUID]
    reference_answer: str = Field(min_length=1, max_length=10000)
    expects_no_answer: bool = False
    filter_document_id: UUID | None = None
    tags: list[str] = Field(default_factory=list)
    difficulty: str | None = None
    category: str | None = None

    @field_validator("id", "question", "reference_answer")
    @classmethod
    def nonblank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Must not be blank")
        return value.strip()

    @model_validator(mode="after")
    def labels(self) -> "EvaluationCase":
        if len(set(self.expected_chunk_ids)) != len(self.expected_chunk_ids):
            raise ValueError("Relevant chunk IDs must be unique")
        if not self.expected_chunk_ids and not self.expects_no_answer:
            raise ValueError("Provide relevant chunk IDs or explicitly expect no answer")
        return self


class JudgeInput(BaseModel):
    question: str
    generated_answer: str
    retrieved_context: list[dict[str, object]]
    reference_answer: str


class JudgeScores(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    faithfulness: float = Field(ge=0, le=1, allow_inf_nan=False)
    answer_relevance: float = Field(ge=0, le=1, allow_inf_nan=False)
    correctness: float = Field(ge=0, le=1, allow_inf_nan=False)
    reason: str = Field(min_length=1, max_length=2000)


class CaseResult(BaseModel):
    id: str
    status: Literal["ok", "error", "judge_error"] = "ok"
    retrieval_scorable: bool
    retrieved_chunk_ids: list[str] = Field(default_factory=list)
    retrieved_chunks: list[dict[str, object]] = Field(default_factory=list)
    retrieval: dict[str, float] | None = None
    generation: dict[str, float | bool | None] | None = None
    judge: JudgeScores | None = None
    latency_ms: dict[str, float | None] = Field(default_factory=dict)
    error: str | None = None


class EvaluationReport(BaseModel):
    schema_version: str = "1.0"
    dataset: str
    dataset_sha256: str
    mode: str
    execution: str
    judge_mode: str
    num_queries: int
    num_succeeded: int
    num_errors: int
    num_retrieval_scored: int
    num_generation_scored: int
    num_judge_scored: int
    configuration: dict[str, str | int | list[int]]
    retrieval: dict[str, float | None]
    generation: dict[str, float | None]
    judge: dict[str, float | None]
    latency_ms: dict[str, dict[str, float | int | None]]
    cases: list[CaseResult]
