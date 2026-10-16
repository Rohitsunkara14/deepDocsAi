"""Explicitly index only the bundled fictional corpus into an isolated local store."""
import argparse
import json
from pathlib import Path

from app.core.config import Settings
from app.services.document_service import process_document
from app.services.indexing import create_resources


def main() -> None:
    cli = argparse.ArgumentParser(description="Prepare fictional evaluation documents in local Qdrant")
    cli.add_argument("--corpus", type=Path, default=Path("evaluation/examples/corpus.json"))
    cli.add_argument("--storage", type=Path, required=True)
    args = cli.parse_args()
    settings = Settings(qdrant_local_path=str(args.storage), qdrant_collection_name="deepdocs_eval_demo",
                        chunk_size=1000, chunk_overlap=150)
    documents = json.loads(args.corpus.read_text(encoding="utf-8"))["documents"]
    resources = create_resources(settings)
    try:
        for item in documents:
            response = process_document(item["text"].encode("utf-8"), item["filename"], "text/plain", settings, resources)
            print(response.model_dump_json())
    finally:
        resources.close()


if __name__ == "__main__":
    main()
