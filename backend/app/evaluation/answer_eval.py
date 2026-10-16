import re

from app.evaluation.models import EvaluationCase
from app.services.rag_service import map_citations
from app.core.errors import LLMError
from app.models.rag import AskResponse
from app.rag.prompt_builder import BuiltPrompt, NO_RESULTS_ANSWER, INSUFFICIENT_CONTEXT_ANSWER

FALLBACKS = {NO_RESULTS_ANSWER, INSUFFICIENT_CONTEXT_ANSWER}
GENERATION_KEYS = ["citation_validity", "citation_markers_valid", "citation_sentence_coverage_proxy",
                   "no_answer_correct", "question_token_recall_proxy", "context_token_support_proxy",
                   "reference_token_f1_proxy"]
STOPWORDS = set("a an the is are was were be of to in and or for on with what how did do does it by from this that".split())


def tokens(text: str) -> set[str]:
    text = re.sub(r"\[[0-9]+\]", "", text)
    return set(re.findall(r"\w+", text.lower())) - STOPWORDS


def evaluate_answer(case: EvaluationCase, response: AskResponse,
                    prompt: BuiltPrompt) -> dict[str, float | bool | None]:
    import json

    expected = {c.source_number: c for c in prompt.citations}
    returned = {c.source_number: c for c in response.citations}
    fallback = response.answer.strip() in FALLBACKS
    valid = sum(c == expected.get(c.source_number) for c in response.citations)
    citation_validity = valid / len(response.citations) if response.citations else float(fallback)
    markers = re.findall(r"\[([0-9]+)\]", response.answer)
    unique_markers = set(markers)
    marker_validity = (len(returned) == len(response.citations)
        and unique_markers == {str(n) for n in returned}
        and all(c == expected.get(n) for n, c in returned.items())
        and (bool(markers) or fallback))
    if not fallback:
        try:
            map_citations(response.answer, prompt.citations)
        except LLMError:
            marker_validity = False
    sentences = [part for part in re.split(r"(?<=[.!?])\s+|\n+", response.answer) if tokens(part)]
    coverage = (sum(bool(re.search(r"\[[0-9]+\]", s)) for s in sentences) / len(sentences)
                if sentences and not fallback else None)
    answer_tokens = tokens(response.answer)
    question_tokens = tokens(case.question)
    reference_tokens = tokens(case.reference_answer)
    context_tokens = tokens(" ".join(str(item["text"]) for item in json.loads(prompt.user_prompt)["sources"]))
    shared = len(answer_tokens & reference_tokens)
    reference_f1 = (2 * shared / (len(answer_tokens) + len(reference_tokens))
                    if answer_tokens or reference_tokens else 0.0)
    return {
        "citation_validity": citation_validity,
        "citation_markers_valid": marker_validity,
        "citation_sentence_coverage_proxy": coverage,
        "no_answer_correct": (fallback and not response.citations) if case.expects_no_answer else not fallback,
        "question_token_recall_proxy": len(answer_tokens & question_tokens) / len(question_tokens) if question_tokens and not fallback else None,
        "context_token_support_proxy": len(answer_tokens & context_tokens) / len(answer_tokens) if answer_tokens and not fallback else None,
        "reference_token_f1_proxy": reference_f1 if not fallback else None,
    }
