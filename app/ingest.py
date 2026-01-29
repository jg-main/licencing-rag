# app/ingest.py
"""Document ingestion pipeline for the License Intelligence System."""

import shutil
from pathlib import Path
from typing import Any

import chromadb
from chromadb.errors import NotFoundError
from tqdm import tqdm

from app.chunking import Chunk
from app.chunking import chunk_document
from app.chunking import save_chunks_artifacts
from app.config import CHROMA_DIR
from app.config import CHUNKS_DATA_DIR
from app.config import EMBEDDING_DIMENSIONS
from app.config import EMBEDDING_MODEL
from app.config import RAW_DATA_DIR
from app.config import SOURCES
from app.config import TEXT_DATA_DIR
from app.definitions import build_definitions_index
from app.definitions import save_definitions_index
from app.embed import OpenAIEmbeddingFunction
from app.extract import ExtractionError
from app.extract import detect_document_version
from app.extract import extract_document
from app.extract import save_extraction_artifacts
from app.extract import validate_extraction
from app.logging import get_logger
from app.search import BM25_INDEX_DIR
from app.search import BM25Index

log = get_logger(__name__)


def get_provider_raw_dir(source: str) -> Path:
    """Get the raw documents directory for a source.

    Args:
        source: Provider identifier (e.g., "cme").

    Returns:
        Path to the source's raw documents directory.
    """
    return RAW_DATA_DIR / source


def get_provider_text_dir(source: str) -> Path:
    """Get the extracted text directory for a source.

    Args:
        source: Provider identifier (e.g., "cme").

    Returns:
        Path to the source's text output directory.
    """
    return TEXT_DATA_DIR / source


def get_provider_chunks_dir(source: str) -> Path:
    """Get the chunks directory for a source.

    Args:
        source: Provider identifier (e.g., "cme").

    Returns:
        Path to the source's chunks output directory.
    """
    return CHUNKS_DATA_DIR / source


def get_collection_name(source: str) -> str:
    """Get collection name for a source.

    Args:
        source: Source identifier.

    Returns:
        Collection name.
    """
    return SOURCES.get(source, {}).get("collection", f"{source}_docs")


def chunks_to_chroma_format(
    chunks: list[Chunk],
) -> tuple[list[str], list[dict[str, Any]], list[str]]:
    """Convert chunks to ChromaDB format.

    Filters out metadata fields with None values since ChromaDB rejects them.

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
        # Build metadata dict, excluding None values (ChromaDB rejects None)
        meta: dict[str, Any] = {
            "chunk_id": chunk.chunk_id,
            "source": chunk.source,
            "document_name": chunk.document_name,
            "document_path": chunk.document_path,  # Relative path for unique identification
            "section_heading": chunk.section_heading,
            "page_start": chunk.page_start,
            "page_end": chunk.page_end,
            "chunk_index": chunk.chunk_index,
            "word_count": chunk.word_count,
            "is_definitions": chunk.is_definitions,
        }
        # Only add document_version if not None
        if chunk.document_version is not None:
            meta["document_version"] = chunk.document_version
        metadatas.append(meta)
        ids.append(chunk.chunk_id)

    return documents, metadatas, ids


def prune_deleted_documents(
    source: str,
    collection: chromadb.Collection,
    current_doc_paths: set[str],
) -> int:
    """Remove chunks for documents that no longer exist in data/raw.

    This ensures that when documents are deleted from data/raw, their chunks
    are also removed from ChromaDB during incremental ingestion.

    Args:
        source: Provider identifier.
        collection: ChromaDB collection to prune.
        current_doc_paths: Set of document_path values for documents currently in data/raw.

    Returns:
        Number of chunks deleted.
    """
    # Get all metadatas from the collection
    try:
        results = collection.get(include=["metadatas"])
    except Exception as e:
        log.warning("failed_to_get_collection_data", source=source, error=str(e))
        return 0

    if not results or not results.get("metadatas"):
        return 0

    # Find IDs of chunks belonging to deleted documents
    ids_to_delete: list[str] = []
    deleted_docs: set[str] = set()

    metadatas = results.get("metadatas", [])
    all_ids = results.get("ids", [])

    # Type guard for mypy - both should be lists if results is valid
    if not isinstance(metadatas, list) or not isinstance(all_ids, list):
        return 0

    for chunk_id, meta in zip(all_ids, metadatas):
        if not meta or not isinstance(chunk_id, str):
            continue

        # Get document_path (or fallback to document_name for backwards compat)
        doc_path_raw = meta.get("document_path") or meta.get("document_name")
        if not isinstance(doc_path_raw, str):
            continue

        # If this document is not in the current set, mark for deletion
        if doc_path_raw not in current_doc_paths:
            ids_to_delete.append(chunk_id)
            deleted_docs.add(doc_path_raw)

    # Delete chunks if any found
    if ids_to_delete:
        collection.delete(ids=ids_to_delete)
        log.info(
            "pruned_deleted_documents",
            source=source,
            documents=len(deleted_docs),
            chunks=len(ids_to_delete),
            deleted_docs=sorted(deleted_docs),
        )
        print(
            f"Pruned {len(ids_to_delete)} chunks from {len(deleted_docs)} deleted document(s)"
        )

    return len(ids_to_delete)


def ingest_provider(source: str, force: bool = False) -> dict[str, int | list[str]]:
    """Ingest all documents for a source.

    Args:
        source: Provider identifier (e.g., "cme").
        force: If True, delete existing collection before ingesting.

    Returns:
        Dictionary with ingestion statistics.

    Raises:
        ValueError: If source is not configured.
        FileNotFoundError: If source directory doesn't exist.
    """
    if source not in SOURCES:
        log.error("unknown_source", source=source, available=list(SOURCES.keys()))
        raise ValueError(f"Unknown source: {source}. Available: {list(SOURCES.keys())}")

    raw_dir = get_provider_raw_dir(source)
    if not raw_dir.exists():
        log.error("provider_directory_not_found", source=source, path=str(raw_dir))
        raise FileNotFoundError(f"Provider directory not found: {raw_dir}")

    # Clean up all artifacts if force=True
    if force:
        # Clean text and chunks directories (source-specific)
        text_dir = get_provider_text_dir(source)
        chunks_dir = get_provider_chunks_dir(source)
        for artifact_dir in [text_dir, chunks_dir]:
            if artifact_dir.exists():
                shutil.rmtree(artifact_dir)
                log.info("artifacts_deleted", directory=str(artifact_dir))

        # Clean BM25 index (source-specific)
        bm25_path = BM25_INDEX_DIR / f"{source}_index.pkl"
        if bm25_path.exists():
            bm25_path.unlink()
            log.info("bm25_index_deleted", path=str(bm25_path))

    # Initialize ChromaDB
    CHROMA_DIR.mkdir(parents=True, exist_ok=True)
    client = chromadb.PersistentClient(path=str(CHROMA_DIR))
    embed_fn = OpenAIEmbeddingFunction()

    collection_name = get_collection_name(source)

    # Delete existing collection if force=True (source-specific)
    # Note: This may leave orphaned segment folders, but preserves other sources' data
    if force:
        try:
            client.delete_collection(collection_name)
            log.info("collection_deleted", collection=collection_name)
        except NotFoundError:
            log.debug("collection_not_found_for_deletion", collection=collection_name)

    # Store embedding model metadata with collection for version checking
    collection = client.get_or_create_collection(
        name=collection_name,
        embedding_function=embed_fn,  # type: ignore[arg-type]
        metadata={
            "source": source,
            "embedding_model": EMBEDDING_MODEL,
            "embedding_dimensions": EMBEDDING_DIMENSIONS,
        },
    )
    log.info("collection_ready", collection=collection_name, source=source)

    # Initialize BM25 index for hybrid search
    bm25_index = BM25Index(source)
    if force:
        bm25_index.clear()

    # Find all supported documents recursively (sorted by relative path for deterministic ordering)
    supported_extensions = {".pdf", ".docx"}
    doc_files = sorted(
        [
            f
            for f in raw_dir.rglob("*")
            if f.is_file() and f.suffix.lower() in supported_extensions
        ],
        key=lambda p: p.relative_to(raw_dir).as_posix().lower(),
    )

    if not doc_files:
        log.warning("no_documents_found", source=source, path=str(raw_dir))
        return {"documents": 0, "chunks": 0, "errors": [], "warnings": []}

    # Prune deleted documents if not using --force (which rebuilds from scratch)
    if not force:
        # Build set of current document paths for pruning comparison
        current_doc_paths = {str(doc.relative_to(raw_dir)) for doc in doc_files}
        prune_deleted_documents(source, collection, current_doc_paths)

    doc_count = 0
    chunk_count = 0
    errors: list[str] = []
    warnings: list[str] = []

    log.info(
        "ingestion_started",
        source=source,
        document_count=len(doc_files),
        force=force,
    )
    print(f"Ingesting {len(doc_files)} documents for source: {source}")

    # Get text output directory for extraction artifacts
    text_dir = get_provider_text_dir(source)

    for doc_path in tqdm(doc_files, desc=f"Processing {source}"):
        try:
            # Calculate relative path for subdirectory support
            relative_path = doc_path.relative_to(raw_dir)

            # Delete existing chunks for this document BEFORE extraction
            # This ensures consistency: if extraction/chunking fails, we don't
            # have stale chunks from a previous version of the document
            if not force:
                try:
                    existing = collection.get(
                        where={"document_path": str(relative_path)},
                        include=[],
                    )
                    if existing and existing.get("ids"):
                        collection.delete(ids=existing["ids"])
                        log.debug(
                            "deleted_existing_chunks",
                            document_path=str(relative_path),
                            count=len(existing["ids"]),
                        )
                except Exception as e:
                    log.warning(
                        "failed_to_delete_existing_chunks",
                        document_path=str(relative_path),
                        error=str(e),
                    )

            # Extract document
            log.debug(
                "extracting_document",
                filename=doc_path.name,
                relative_path=str(relative_path),
            )
            extracted = extract_document(doc_path)

            # Validate extraction quality and log any warnings
            extraction_warnings = validate_extraction(extracted)
            if extraction_warnings:
                warnings.extend(extraction_warnings)

            # Detect document version for chunk metadata
            doc_version = detect_document_version(extracted.full_text)

            # Save extraction artifacts (.txt and .meta.json) per spec
            save_extraction_artifacts(extracted, text_dir, source, relative_path)

            # Chunk document with version info and relative path
            chunks = chunk_document(
                extracted,
                source,
                document_version=doc_version,
                relative_path=relative_path,
            )

            if not chunks:
                log.warning("no_chunks_generated", filename=doc_path.name)
                continue

            # Save chunk artifacts for visibility into chunking process
            chunks_dir = get_provider_chunks_dir(source)
            save_chunks_artifacts(chunks, relative_path, chunks_dir)

            # Convert to ChromaDB format
            documents, metadatas, ids = chunks_to_chroma_format(chunks)

            # Add to collection (existing chunks already deleted earlier)
            collection.add(
                documents=documents,
                metadatas=metadatas,  # type: ignore[arg-type]
                ids=ids,
            )

            # Add to BM25 index for hybrid search
            bm25_index.add_documents(ids, documents)

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

    # Build and save BM25 index
    if chunk_count > 0:
        bm25_index.build()
        bm25_index.save()

        # Build and save definitions index from definition chunks
        all_chunks: list[dict[str, Any]] = []
        results = collection.get(include=["documents", "metadatas"])
        if results and results["documents"] and results["metadatas"]:
            for doc, meta in zip(
                results["documents"],
                results["metadatas"],
            ):
                all_chunks.append({"text": doc, "metadata": dict(meta)})

        if all_chunks:
            definitions_index = build_definitions_index(source, all_chunks)
            if len(definitions_index) > 0:
                save_definitions_index(definitions_index)
                print(f"  Definitions index: {len(definitions_index)} terms")
            else:
                print("  Definitions index: no definitions found")

    log.info(
        "ingestion_complete",
        source=source,
        documents=doc_count,
        chunks=chunk_count,
        errors=len(errors),
        warnings=len(warnings),
    )
    print("\nIngestion complete:")
    print(f"  Documents: {doc_count}")
    print(f"  Chunks: {chunk_count}")
    print(f"  BM25 index: {'built and saved' if chunk_count > 0 else 'skipped'}")
    if warnings:
        print(f"  Warnings: {len(warnings)}")
    if errors:
        print(f"  Errors: {len(errors)}")

    return {
        "documents": doc_count,
        "chunks": chunk_count,
        "errors": errors,
        "warnings": warnings,
    }


def list_indexed_documents(source: str) -> list[str]:
    """List all documents indexed for a source.

    Args:
        source: Provider identifier.

    Returns:
        List of unique document paths (relative to source directory).
    """
    if not CHROMA_DIR.exists():
        return []

    client = chromadb.PersistentClient(path=str(CHROMA_DIR))
    collection_name = get_collection_name(source)

    try:
        collection = client.get_collection(collection_name)
    except NotFoundError:
        return []

    # Get all metadatas
    results = collection.get(include=["metadatas"])
    if not results or not results.get("metadatas"):
        return []

    # Extract unique document paths (prefer document_path, fallback to document_name)
    doc_paths: set[str] = set()
    metadatas = results.get("metadatas")
    if metadatas:
        for meta in metadatas:
            if meta:
                # Prefer document_path (includes subdirectory), fall back to document_name
                path = meta.get("document_path") or meta.get("document_name")
                if isinstance(path, str):
                    doc_paths.add(path)

    return sorted(doc_paths)


def main() -> None:
    """CLI entrypoint for ingestion (legacy support)."""
    ingest_provider("cme", force=True)


if __name__ == "__main__":
    main()
