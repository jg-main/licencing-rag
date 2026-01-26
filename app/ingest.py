# app/ingest.py
"""Document ingestion pipeline for the License Intelligence System."""

from pathlib import Path
from typing import Any

import chromadb
from tqdm import tqdm

from app.chunking import Chunk
from app.chunking import chunk_document
from app.chunking import save_chunks_artifacts
from app.config import CHROMA_DIR
from app.config import CHUNKS_DATA_DIR
from app.config import PROVIDERS
from app.config import RAW_DATA_DIR
from app.config import TEXT_DATA_DIR
from app.embed import OllamaEmbeddingFunction
from app.extract import ExtractionError
from app.extract import detect_document_version
from app.extract import extract_document
from app.extract import save_extraction_artifacts
from app.extract import validate_extraction
from app.logging import get_logger

log = get_logger(__name__)


def get_provider_raw_dir(provider: str) -> Path:
    """Get the raw documents directory for a provider.

    Args:
        provider: Provider identifier (e.g., "cme").

    Returns:
        Path to the provider's raw documents directory.
    """
    return RAW_DATA_DIR / provider


def get_provider_text_dir(provider: str) -> Path:
    """Get the extracted text directory for a provider.

    Args:
        provider: Provider identifier (e.g., "cme").

    Returns:
        Path to the provider's text output directory.
    """
    return TEXT_DATA_DIR / provider


def get_provider_chunks_dir(provider: str) -> Path:
    """Get the chunks directory for a provider.

    Args:
        provider: Provider identifier (e.g., "cme").

    Returns:
        Path to the provider's chunks output directory.
    """
    return CHUNKS_DATA_DIR / provider


def get_collection_name(provider: str) -> str:
    """Get the ChromaDB collection name for a provider.

    Args:
        provider: Provider identifier.

    Returns:
        Collection name.
    """
    return PROVIDERS.get(provider, {}).get("collection", f"{provider}_docs")


def chunks_to_chroma_format(
    chunks: list[Chunk],
) -> tuple[list[str], list[dict[str, Any]], list[str]]:
    """Convert chunks to ChromaDB format.

    Args:
        chunks: List of Chunk objects.

    Returns:
        Tuple of (documents, metadatas, ids).
    """
    documents: list[str] = []
    metadatas: list[dict[str, Any]] = []
    ids: list[str] = []

    for chunk in chunks:
        documents.append(chunk.text)
        metadatas.append(
            {
                "chunk_id": chunk.chunk_id,
                "provider": chunk.provider,
                "document_name": chunk.document_name,
                "section_heading": chunk.section_heading,
                "page_start": chunk.page_start,
                "page_end": chunk.page_end,
                "chunk_index": chunk.chunk_index,
                "word_count": chunk.word_count,
                "is_definitions": chunk.is_definitions,
                "document_version": chunk.document_version,
            }
        )
        ids.append(chunk.chunk_id)

    return documents, metadatas, ids


def ingest_provider(provider: str, force: bool = False) -> dict[str, int | list[str]]:
    """Ingest all documents for a provider.

    Args:
        provider: Provider identifier (e.g., "cme").
        force: If True, delete existing collection before ingesting.

    Returns:
        Dictionary with ingestion statistics.

    Raises:
        ValueError: If provider is not configured.
        FileNotFoundError: If provider directory doesn't exist.
    """
    if provider not in PROVIDERS:
        log.error(
            "unknown_provider", provider=provider, available=list(PROVIDERS.keys())
        )
        raise ValueError(
            f"Unknown provider: {provider}. Available: {list(PROVIDERS.keys())}"
        )

    raw_dir = get_provider_raw_dir(provider)
    if not raw_dir.exists():
        log.error("provider_directory_not_found", provider=provider, path=str(raw_dir))
        raise FileNotFoundError(f"Provider directory not found: {raw_dir}")

    # Initialize ChromaDB
    CHROMA_DIR.mkdir(parents=True, exist_ok=True)
    client = chromadb.PersistentClient(path=str(CHROMA_DIR))
    embed_fn = OllamaEmbeddingFunction()

    collection_name = get_collection_name(provider)

    # Delete existing collection if force=True
    if force:
        try:
            client.delete_collection(collection_name)
            log.info("collection_deleted", collection=collection_name)
        except ValueError:
            log.debug("collection_not_found_for_deletion", collection=collection_name)

    collection = client.get_or_create_collection(
        name=collection_name,
        embedding_function=embed_fn,  # type: ignore[arg-type]
        metadata={"provider": provider},
    )
    log.info("collection_ready", collection=collection_name, provider=provider)

    # Find all supported documents (sorted for deterministic ordering)
    supported_extensions = {".pdf", ".docx"}
    doc_files = sorted(
        [f for f in raw_dir.iterdir() if f.suffix.lower() in supported_extensions],
        key=lambda p: p.name.lower(),
    )

    if not doc_files:
        log.warning("no_documents_found", provider=provider, path=str(raw_dir))
        return {"documents": 0, "chunks": 0, "errors": []}

    doc_count = 0
    chunk_count = 0
    errors: list[str] = []

    log.info(
        "ingestion_started",
        provider=provider,
        document_count=len(doc_files),
        force=force,
    )
    print(f"Ingesting {len(doc_files)} documents for provider: {provider}")

    # Get text output directory for extraction artifacts
    text_dir = get_provider_text_dir(provider)

    for doc_path in tqdm(doc_files, desc=f"Processing {provider}"):
        try:
            # Extract document
            log.debug("extracting_document", filename=doc_path.name)
            extracted = extract_document(doc_path)

            # Validate extraction quality and log any warnings
            extraction_warnings = validate_extraction(extracted)
            if extraction_warnings:
                errors.extend(extraction_warnings)

            # Detect document version for chunk metadata
            doc_version = detect_document_version(extracted.full_text)

            # Save extraction artifacts (.txt and .meta.json) per spec
            save_extraction_artifacts(extracted, text_dir, provider)

            # Chunk document with version info
            chunks = chunk_document(extracted, provider, document_version=doc_version)

            if not chunks:
                log.warning("no_chunks_generated", filename=doc_path.name)
                continue

            # Save chunk artifacts for visibility into chunking process
            chunks_dir = get_provider_chunks_dir(provider)
            save_chunks_artifacts(chunks, doc_path.name, chunks_dir)

            # Convert to ChromaDB format
            documents, metadatas, ids = chunks_to_chroma_format(chunks)

            # Delete existing chunks for this document before adding (upsert behavior)
            # This prevents duplicates when re-ingesting without --force
            if not force:
                try:
                    existing = collection.get(
                        where={"document_name": doc_path.name},
                        include=[],
                    )
                    if existing and existing.get("ids"):
                        collection.delete(ids=existing["ids"])
                        log.debug(
                            "deleted_existing_chunks",
                            filename=doc_path.name,
                            count=len(existing["ids"]),
                        )
                except Exception:
                    pass  # Ignore errors during cleanup

            # Add to collection
            collection.add(
                documents=documents,
                metadatas=metadatas,  # type: ignore[arg-type]
                ids=ids,
            )

            doc_count += 1
            chunk_count += len(chunks)
            log.debug(
                "document_ingested",
                filename=doc_path.name,
                chunks=len(chunks),
                pages=extracted.page_count,
            )

        except ExtractionError as e:
            error_msg = f"Extraction failed for {doc_path.name}: {e}"
            errors.append(error_msg)
            log.error("extraction_failed", filename=doc_path.name, error=str(e))
        except Exception as e:
            error_msg = f"Error processing {doc_path.name}: {e}"
            errors.append(error_msg)
            log.error(
                "document_processing_failed", filename=doc_path.name, error=str(e)
            )

    log.info(
        "ingestion_complete",
        provider=provider,
        documents=doc_count,
        chunks=chunk_count,
        errors=len(errors),
    )
    print("\nIngestion complete:")
    print(f"  Documents: {doc_count}")
    print(f"  Chunks: {chunk_count}")
    if errors:
        print(f"  Errors: {len(errors)}")

    return {"documents": doc_count, "chunks": chunk_count, "errors": errors}


def list_indexed_documents(provider: str) -> list[str]:
    """List all documents indexed for a provider.

    Args:
        provider: Provider identifier.

    Returns:
        List of unique document names.
    """
    if not CHROMA_DIR.exists():
        return []

    client = chromadb.PersistentClient(path=str(CHROMA_DIR))
    collection_name = get_collection_name(provider)

    try:
        collection = client.get_collection(collection_name)
    except ValueError:
        return []

    # Get all metadatas
    results = collection.get(include=["metadatas"])
    if not results or not results.get("metadatas"):
        return []

    # Extract unique document names
    doc_names: set[str] = set()
    metadatas = results.get("metadatas")
    if metadatas:
        for meta in metadatas:
            if meta and "document_name" in meta:
                name = meta["document_name"]
                if isinstance(name, str):
                    doc_names.add(name)

    return sorted(doc_names)


def main() -> None:
    """CLI entrypoint for ingestion (legacy support)."""
    ingest_provider("cme", force=True)


if __name__ == "__main__":
    main()
