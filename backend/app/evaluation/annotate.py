
"""Display candidates for human review; never generate relevance labels."""
import argparse
import json
from pathlib import Path

from app.evaluation.benchmark.corpus import settings_for, verify_store
from app.models.search import SearchRequest
from app.rag.retrieval import STRATEGIES
from app.services.indexing import create_resources
from app.services.search_service import search_documents


def format_candidates(question: str, results: list, preview_chars: int = 500) -> str:
    lines = [f"Question: {question}", "Candidate suggestions only — a human must review relevance."]
    for rank, item in enumerate(results, 1):
        lines.extend([f"Rank {rank} | chunk_id={item.chunk_id} | document_id={item.document_id}",
                      f"filename={item.source_filename} | page={item.page_number} | score={item.score:.6g}",
                      item.text[:preview_chars]])
    return "\n".join(lines) + "\n"



def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--question", required=True)
    parser.add_argument("--top-k", type=int, default=20, choices=range(1, 21))
    parser.add_argument("--strategy", choices=STRATEGIES, default="dense")
    parser.add_argument("--inventory", type=Path, required=True)
    args = parser.parse_args()
    inventory = json.loads(args.inventory.read_text())
    settings = settings_for(Path(inventory["storage"]), inventory.get("collection", "deepdocs_benchmark")).model_copy(update={"retrieval_strategy": args.strategy})
    if settings.embedding_model_name != inventory["configuration"]["embedding_model_name"]:
        parser.error("Embedding model differs from inventory")
    resources = create_resources(settings)
    try:
        verify_store(resources, inventory)
        response = search_documents(SearchRequest(query=args.question, top_k=args.top_k), resources)
        print(format_candidates(args.question, response.results))
    finally:
        resources.close()


if __name__ == "__main__":
    main()
