
from hashlib import sha256
import json
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.core.config import Settings
from app.services.document_service import process_document
from app.services.indexing import create_resources

COLLECTION = "deepdocs_benchmark"


class ManifestDocument(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str = Field(min_length=1, max_length=100)
    filename: str = Field(min_length=1, max_length=250)
    category: str = Field(min_length=1, max_length=100)

    @field_validator("id", "filename", "category")
    @classmethod
    def nonblank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Blank manifest field")
        return value.strip()

    @field_validator("filename")
    @classmethod
    def filename_only(cls, value: str) -> str:
        if Path(value).name != value or "\\" in value or Path(value).suffix.lower() not in {".pdf", ".txt"}:
            raise ValueError("Use a plain PDF/TXT filename, without directories")
        return value


class CorpusManifest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    documents: list[ManifestDocument] = Field(min_length=1, max_length=1000)

    @model_validator(mode="after")
    def unique(self) -> "CorpusManifest":
        for field in ("id", "filename"):
            values = [getattr(item, field) for item in self.documents]
            if len(set(values)) != len(values):
                raise ValueError(f"Duplicate manifest {field}")
        return self


def manifest_files(path: Path, max_mb: int) -> tuple[CorpusManifest, list[tuple[ManifestDocument, Path]]]:
    if path.stat().st_size > 1024 * 1024:
        raise ValueError("Manifest exceeds 1 MiB")
    manifest = CorpusManifest.model_validate_json(path.read_text())
    files = []
    for item in manifest.documents:
        file = path.parent / item.filename
        if not file.is_file() or file.resolve().parent != path.parent.resolve():
            raise ValueError(f"Missing or out-of-directory corpus document: {item.filename}")
        if not 0 < file.stat().st_size <= max_mb * 1024 * 1024:
            raise ValueError(f"Empty or oversized document: {item.filename}")
        files.append((item, file))
    return manifest, files


def settings_for(storage: Path, collection: str = COLLECTION) -> Settings:
    return Settings(qdrant_local_path=str(storage.resolve()), qdrant_collection_name=collection)


def ingest(manifest_path: Path, storage: Path, output: Path, collection: str = COLLECTION) -> dict:
    config = settings_for(storage, collection)
    manifest, files = manifest_files(manifest_path, config.max_upload_size_mb)
    # A fresh isolated store prevents stale or unrelated corpus chunks affecting rankings.
    if storage.exists() and any(storage.iterdir()):
        raise ValueError("Use a new empty benchmark storage directory")
    if output.exists():
        raise ValueError("Inventory already exists; use a new output path")
    resources = create_resources(config)
    documents = []
    failures = []
    manifest_ids = {}
    try:
        for item, file in files:
            try:
                with file.open("rb") as source:
                    data = source.read(config.max_upload_size_mb * 1024 * 1024 + 1)
                if len(data) > config.max_upload_size_mb * 1024 * 1024:
                    raise ValueError("Document exceeds the configured upload limit")
                from uuid import uuid5, NAMESPACE_URL
                application_id = str(uuid5(NAMESPACE_URL, item.filename + ":" + sha256(data).hexdigest()))
                manifest_ids[application_id] = item.id
                mime = "application/pdf" if file.suffix.lower() == ".pdf" else "text/plain"
                result = process_document(data, item.filename, mime, config, resources)
                entry = {**item.model_dump(), **result.model_dump(mode="json"),
                         "manifest_document_id": item.id, "sha256": sha256(data).hexdigest()}
                documents.append(entry)
                print(json.dumps({"status": "success", **entry}), flush=True)
            except Exception as exc:
                from app.services.document_service import DocumentProcessingError
                from app.core.errors import IndexingError
                reason = str(exc) if isinstance(exc, (DocumentProcessingError, IndexingError, ValueError)) else "Document processing failed; inspect file validity and available resources"
                failure = {"manifest_document_id": item.id, "filename": item.filename, "reason": reason}
                failures.append(failure)
                print(json.dumps({"status": "failed", **failure}), flush=True)
        chunks = [item.model_dump(mode="json") for item in resources.store.list_chunks()]
        for chunk in chunks:
            chunk["manifest_document_id"] = manifest_ids.get(chunk["document_id"])
        inventory = {"failures": failures, "manifest": manifest.model_dump(), "documents": documents, "chunks": chunks,
                     "storage": str(storage.resolve()), "collection": collection,
                     "configuration": {name: getattr(config, name) for name in (
                         "embedding_model_name", "chunking_strategy", "chunk_size", "chunk_overlap",
                         "token_chunk_size", "token_chunk_overlap")}}
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(inventory, indent=2) + "\n")
        return inventory
    finally:
        resources.close()


def verify_store(resources, inventory: dict) -> None:
    live = {item.chunk_id: item.model_dump(mode="json") for item in resources.store.list_chunks()}
    expected = {item["chunk_id"]: {k: v for k, v in item.items() if k != "manifest_document_id"} for item in inventory["chunks"]}
    if live != expected:
        raise ValueError("Store differs from annotation inventory; regenerate inventory and review labels")
