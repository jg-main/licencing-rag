# CME License Intelligence System (Local RAG) - Technical Product Brief

**Project Name:** CME License Intelligence System (Local RAG)

## 1. Objective

Build a **local, private legal Q&A system** that answers questions **exclusively** based on a curated set of CME license agreements and exhibits (≈40 documents).

The system must:

- Respond **only** using the provided documents
- Explicitly refuse to answer when the documents are silent
- Always provide **citations** (document name + section / chunk reference)
- Run **entirely locally** (no cloud, no external APIs)
- Be maintainable as documents are updated

This is **not** a general chatbot and **not** a trained LLM. It is a **retrieval-grounded legal analysis tool**.

______________________________________________________________________

## 2. Non-Goals (Explicitly Out of Scope)

- No model training or fine-tuning
- No external data sources
- No internet access
- No legal advice generation beyond document interpretation
- No “best practice” or industry commentary unless explicitly stated in the documents

______________________________________________________________________

## 3. High-Level Architecture

The system follows a **Retrieval-Augmented Generation (RAG)** pattern:

1. **Document ingestion**

   - PDFs / DOCX files are converted to clean text

1. **Chunking**

   - Documents are split into clause-sized chunks with metadata

1. **Indexing**

   - Chunks are embedded and stored in a local vector database

1. **Query flow**

   - User question → semantic retrieval of relevant chunks
   - Retrieved text is injected into the LLM prompt
   - LLM answers **strictly** from retrieved context

1. **Output**

   - Answer + citations
   - Explicit refusal if information is not found

______________________________________________________________________

## 4. Technology Stack (Initial)

### Runtime

- Python 3.10+
- Local execution on developer machine (macOS / Windows / Linux)

### Models (Local)

- **LLM:** LLaMA 3.1 8B (via Ollama)
- **Embeddings:** nomic-embed-text (or equivalent local embedding model)

### Libraries

- PDF extraction: PyMuPDF
- Vector database: ChromaDB (local persistence)
- Orchestration: minimal LangChain usage or plain Python
- No cloud services

______________________________________________________________________

## 5. Document Ingestion Requirements

### Input

- CME license agreements
- CME exhibits and addenda
- Amendments / revised versions

### Output

- One clean `.txt` file per source document
- Page boundaries preserved when possible
- Section headings preserved when detectable

### Constraints

- OCR is out of scope unless documents are scanned (to be confirmed)
- Manual verification of extracted text quality is required

______________________________________________________________________

## 6. Chunking Strategy (Critical)

### Chunk Granularity

- Target: **300–800 words per chunk**

- Overlap: **~100–150 words**

- Chunk boundaries should prefer:

  - Section numbers (e.g., `2.03`, `SECTION 7`)
  - Article headings
  - Exhibit boundaries

### Metadata per Chunk

Each chunk must include:

- `document_name`
- `document_version` (if known)
- `section_heading` or identifier
- `chunk_id`
- Optional: page range

### Definitions Handling

- “Definitions” sections must be indexed explicitly
- Definitions should be retrievable independently
- Later enhancement: auto-include relevant definitions when clauses reference defined terms

______________________________________________________________________

## 7. Retrieval & Answering Rules

### Retrieval

- Semantic vector search
- Top-k = 3–5 chunks
- No full-document stuffing

### Answer Constraints (Hard Rules)

The LLM must:

- Use **only** the retrieved context
- Never rely on prior knowledge
- Never speculate
- Explicitly refuse if the answer is not found

Standard refusal text:

> “Not addressed in the provided CME documents.”

______________________________________________________________________

## 8. Output Format (Minimum Standard)

Each response must include:

1. **Answer**

   - Clear, concise, grounded

1. **Supporting Clauses**

   - Short quoted or paraphrased excerpts

1. **Citations**

   - Document name
   - Section or chunk identifier

1. **Notes (optional)**

   - Ambiguities
   - Cross-references
   - Missing definitions

______________________________________________________________________

## 9. Security & Privacy

- Fully local execution
- No telemetry
- No outbound network calls
- Vector DB and models stored locally
- All queries and retrieved chunks can optionally be logged for auditability

______________________________________________________________________

## 10. Deliverables (Phase 1)

- Working local prototype
- CLI-based interface (e.g. `python query.py "question"`)
- Document ingestion script
- Persistent vector index
- Prompt guardrails enforcing refusal and citation
- Basic documentation (README + setup instructions)

______________________________________________________________________

## 11. Success Criteria

The system is considered successful if:

- It **never answers** beyond the provided CME documents
- It consistently provides citations
- It refuses correctly when information is missing
- Updating documents requires **re-ingestion only**, not retraining
- Performance is acceptable on a standard laptop (Dell XPS-class)

______________________________________________________________________

## 12. Future Enhancements (Explicitly Deferred)

- Clause comparison across agreements
- Risk flag extraction (audit, redistribution, termination)
- Version diffing between document updates
- Simple UI (Streamlit or web frontend)
- Multi-user access

______________________________________________________________________

## 13. Guiding Principle

This system must behave like a **careful legal analyst**, not a creative assistant.

Correctness, traceability, and refusal are **more important than fluency**.
