import json
from pathlib import Path

from pydantic import BaseModel, ConfigDict

from app.evaluation.backend import Trace
from app.evaluation.dataset import EvaluationError
from app.evaluation.models import EvaluationCase, JudgeInput, JudgeScores
from app.models.rag import AskResponse
from app.models.search import SearchResult


class ReplayCase(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    question: str
    retrieved: list[SearchResult]
    response: AskResponse
    judge: JudgeScores


def load_replay(path: Path) -> dict[str, ReplayCase]:
    try:
        items = [ReplayCase.model_validate(item) for item in json.loads(path.read_text())]
        if len({item.id for item in items}) != len(items):
            raise ValueError("Duplicate replay IDs")
        return {item.id: item for item in items}
    except Exception as exc:
        raise EvaluationError("Invalid replay fixture") from exc


class ReplayBackend:
    """Synthetic recorded outputs: never connects to models or a database."""
    def __init__(self, records: dict[str, ReplayCase]) -> None:
        self.records = records
        self.trace = Trace()

    async def retrieve(self, case: EvaluationCase, depth: int) -> list[SearchResult]:
        self.trace = Trace()
        record = self.records[case.id]
        if record.question != case.question:
            raise EvaluationError("Replay question does not match dataset")
        self.trace.retrieved = [chunk for chunk in record.retrieved if case.filter_document_id is None
            or chunk.document_id == str(case.filter_document_id)][:depth]
        return self.trace.retrieved

    async def ask(self, case: EvaluationCase, depth: int) -> AskResponse:
        await self.retrieve(case, depth)
        return self.records[case.id].response


class ReplayJudge:
    def __init__(self, records: dict[str, ReplayCase]) -> None:
        self.records = records

    async def evaluate(self, sample: JudgeInput) -> JudgeScores:
        matches = [item for item in self.records.values() if item.question == sample.question
                   and item.response.answer == sample.generated_answer]
        if len(matches) != 1:
            raise EvaluationError("No unique synthetic judge record")
        return matches[0].judge
