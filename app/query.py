# app/query.py
"""Query pipeline for the License Intelligence System."""

from typing import Any

import chromadb
import ollama

from app.config import CHROMA_DIR
from app.config import DEFAULT_PROVIDERS
from app.config import LLM_MODEL
from app.config import PROVIDERS
from app.config import TOP_K
from app.embed import OllamaEmbeddingFunction
from app.prompts import QA_PROMPT
from app.prompts import REFUSAL_MESSAGE
from app.prompts import SYSTEM_PROMPT


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
        raise ValueError(
            f"Unknown providers: {invalid}. Available: {list(PROVIDERS.keys())}"
        )

    if not CHROMA_DIR.exists():
        raise RuntimeError(
            "No index found. Run 'python main.py ingest --provider <name>' first."
        )

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
            print(f"Warning: Collection '{collection_name}' not found. Skipping.")
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
        return {
            "answer": REFUSAL_MESSAGE,
            "context": "",
            "citations": [],
            "chunks_retrieved": 0,
        }

    # Format context
    context = format_context(all_documents, all_metadatas)

    # Build prompt
    prompt = QA_PROMPT.format(context=context, question=question)

    # Call LLM
    response = ollama.chat(
        model=LLM_MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
    )

    answer = response["message"]["content"]

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
