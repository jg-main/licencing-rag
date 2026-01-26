# app/ingest.py
"""Document ingestion pipeline for the License Intelligence System."""

from pathlib import Path
from typing import Any

import chromadb
from tqdm import tqdm

from app.chunking import Chunk
from app.chunking import chunk_document
from app.config import CHROMA_DIR
from app.config import PROVIDERS
from app.config import RAW_DATA_DIR
from app.embed import OllamaEmbeddingFunction
from app.extract import extract_document


def get_provider_raw_dir(provider: str) -> Path:
    """Get the raw documents directory for a provider.

    Args:
        provider: Provider identifier (e.g., "cme").

    Returns:
        Path to the provider's raw documents directory.
    """
    return RAW_DATA_DIR / provider


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
        raise ValueError(
            f"Unknown provider: {provider}. Available: {list(PROVIDERS.keys())}"
        )

    raw_dir = get_provider_raw_dir(provider)
    if not raw_dir.exists():
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
            print(f"Deleted existing collection: {collection_name}")
        except ValueError:
            pass  # Collection doesn't exist

    collection = client.get_or_create_collection(
        name=collection_name,
        embedding_function=embed_fn,  # type: ignore[arg-type]
        metadata={"provider": provider},
    )

    # Find all supported documents
    supported_extensions = {".pdf", ".docx"}
    doc_files = [
        f for f in raw_dir.iterdir() if f.suffix.lower() in supported_extensions
    ]

    if not doc_files:
        print(f"No documents found in {raw_dir}")
        return {"documents": 0, "chunks": 0, "errors": []}

    doc_count = 0
    chunk_count = 0
    errors: list[str] = []

    print(f"Ingesting {len(doc_files)} documents for provider: {provider}")

    for doc_path in tqdm(doc_files, desc=f"Processing {provider}"):
        try:
            # Extract document
            extracted = extract_document(doc_path)

            # Chunk document
            chunks = chunk_document(extracted, provider)

            if not chunks:
                print(f"  Warning: No chunks from {doc_path.name}")
                continue

            # Convert to ChromaDB format
            documents, metadatas, ids = chunks_to_chroma_format(chunks)

            # Add to collection
            collection.add(
                documents=documents,
                metadatas=metadatas,  # type: ignore[arg-type]
                ids=ids,
            )

            doc_count += 1
            chunk_count += len(chunks)

        except Exception as e:
            error_msg = f"Error processing {doc_path.name}: {e}"
            errors.append(error_msg)
            print(f"  {error_msg}")

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
