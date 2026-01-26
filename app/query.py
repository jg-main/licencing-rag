# app/query.py
"""Query pipeline for the License Intelligence System."""

from typing import Any

import chromadb

from app.config import CHROMA_DIR
from app.config import DEFAULT_PROVIDERS
from app.config import PROVIDERS
from app.config import TOP_K
from app.embed import OllamaEmbeddingFunction
from app.llm import LLMConnectionError
from app.llm import get_llm
from app.logging import get_logger
from app.prompts import QA_PROMPT
from app.prompts import REFUSAL_MESSAGE
from app.prompts import SYSTEM_PROMPT

log = get_logger(__name__)


def format_context(
    documents: list[str],
    metadatas: list[dict],
) -> str:
    """Format retrieved documents into context string.

    Args:
        documents: List of document texts.
        metadatas: List of metadata dicts.

    Returns:
        Formatted context string.
    """
    context_parts = []
    for doc, meta in zip(documents, metadatas):
        source = meta.get("document_name", "Unknown")
        section = meta.get("section_heading", "N/A")
        page_start = meta.get("page_start", "?")
        page_end = meta.get("page_end", "?")

        if page_start == page_end:
            page_info = f"Page {page_start}"
        else:
            page_info = f"Pages {page_start}-{page_end}"

        header = f"--- {source} | {section} | {page_info} ---"
        context_parts.append(f"{header}\n{doc}")

    return "\n\n".join(context_parts)


def query(
    question: str,
    providers: list[str] | None = None,
    top_k: int = TOP_K,
) -> dict:
    """Query the knowledge base.

    Args:
        question: User question.
        providers: List of providers to query. Defaults to all configured.
        top_k: Number of chunks to retrieve per provider.

    Returns:
        Dictionary with answer, context, and citations.

    Raises:
        RuntimeError: If no collections are available.
    """
    if providers is None:
        providers = DEFAULT_PROVIDERS

    # Validate providers
    invalid = [p for p in providers if p not in PROVIDERS]
    if invalid:
        log.error(
            "invalid_providers", invalid=invalid, available=list(PROVIDERS.keys())
        )
        raise ValueError(
            f"Unknown providers: {invalid}. Available: {list(PROVIDERS.keys())}"
        )

    if not CHROMA_DIR.exists():
        log.error("no_index_found", path=str(CHROMA_DIR))
        raise RuntimeError(
            "No index found. Run 'python main.py ingest --provider <name>' first."
        )

    log.info("query_started", question=question[:100], providers=providers, top_k=top_k)

    client = chromadb.PersistentClient(path=str(CHROMA_DIR))
    embed_fn = OllamaEmbeddingFunction()

    all_documents: list[str] = []
    all_metadatas: list[dict[str, Any]] = []

    for provider in providers:
        collection_name = PROVIDERS[provider].get("collection", f"{provider}_docs")

        try:
            collection = client.get_collection(
                name=collection_name,
                embedding_function=embed_fn,  # type: ignore[arg-type]
            )
        except ValueError:
            log.warning(
                "collection_not_found", collection=collection_name, provider=provider
            )
            continue

        results = collection.query(
            query_texts=[question],
            n_results=top_k,
        )

        if results:
            docs = results.get("documents")
            metas = results.get("metadatas")
            if docs and docs[0]:
                all_documents.extend(docs[0])
            if metas and metas[0]:
                for m in metas[0]:
                    if m:
                        all_metadatas.append(dict(m))

    if not all_documents:
        log.info("no_chunks_retrieved", question=question[:100])
        return {
            "answer": REFUSAL_MESSAGE,
            "context": "",
            "citations": [],
            "chunks_retrieved": 0,
        }

    log.debug("chunks_retrieved", count=len(all_documents))

    # Format context
    context = format_context(all_documents, all_metadatas)

    # Build prompt
    prompt = QA_PROMPT.format(context=context, question=question)

    # Call LLM
    log.debug("calling_llm")
    try:
        llm = get_llm()
        answer = llm.generate(system=SYSTEM_PROMPT, prompt=prompt)
    except LLMConnectionError as e:
        log.error("llm_connection_failed", error=str(e))
        raise RuntimeError(f"LLM connection failed: {e}") from e

    log.info(
        "query_complete",
        chunks=len(all_documents),
        answer_length=len(answer),
    )

    # Extract citations
    citations = []
    seen = set()
    for meta in all_metadatas:
        doc_name = meta.get("document_name", "Unknown")
        section = meta.get("section_heading", "N/A")
        page_start = meta.get("page_start", "?")
        key = (doc_name, section, page_start)
        if key not in seen:
            seen.add(key)
            citations.append(
                {
                    "document": doc_name,
                    "section": section,
                    "page": page_start,
                    "provider": meta.get("provider", "unknown"),
                }
            )

    return {
        "answer": answer,
        "context": context,
        "citations": citations,
        "chunks_retrieved": len(all_documents),
    }


def print_response(result: dict) -> None:
    """Print a formatted response.

    Args:
        result: Query result dictionary.
    """
    print("\n" + "=" * 60)
    print("ANSWER")
    print("=" * 60)
    print(result["answer"])

    if result["citations"]:
        print("\n" + "-" * 60)
        print("CITATIONS")
        print("-" * 60)
        for cit in result["citations"]:
            print(f"  • {cit['document']} | {cit['section']} | Page {cit['page']}")

    print("\n" + f"[Retrieved {result['chunks_retrieved']} chunks]")


def main(question: str) -> None:
    """CLI entrypoint for queries (legacy support).

    Args:
        question: User question.
    """
    result = query(question)
    print_response(result)


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        main(sys.argv[1])
    else:
        print("Usage: python -m app.query 'Your question here'")
