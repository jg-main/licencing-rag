# RAG for Beginners: A Rookie's Guide

## What You'll Learn

This tutorial explains how the License RAG system works, step by step. By the end, you'll understand:

- What LLMs are and their limitations
- What RAG is and why we need it
- How documents become searchable
- How questions get answered
- Where Claude fits in

______________________________________________________________________

## Part 1: Understanding the Problem

### What is an LLM?

An LLM (Large Language Model) is a program that predicts the next word in a sentence. It was trained on billions of documents from the internet.

```
You type:  "The capital of France is"
LLM thinks: What word usually comes after this?
LLM says:  "Paris"
```

**Key insight:** The LLM doesn't "know" things. It recognizes patterns from training.

### Why Can't We Just Ask Claude About CME Licenses?

Try asking Claude: *"What is the CME Non-Display A1 fee?"*

Claude will either:

1. **Hallucinate** - Make up a plausible-sounding but wrong number
1. **Refuse** - Say "I don't have access to current CME fee schedules"

**The problem:** Claude was trained on public internet data, not your specific license documents. Even if it saw old CME docs during training, the fees change yearly.

### The Solution: Give Claude the Documents

Instead of hoping Claude knows the answer, we:

1. Find the relevant parts of your documents
1. Give those parts to Claude
1. Ask Claude to answer based ONLY on what we gave it

This is called **RAG** - Retrieval-Augmented Generation.

______________________________________________________________________

## Part 2: How RAG Works (The Big Picture)

```
┌─────────────────────────────────────────────────────────────────┐
│                         RAG SYSTEM                              │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│   YOUR DOCUMENTS              YOUR QUESTION                     │
│        │                           │                            │
│        ▼                           ▼                            │
│   ┌─────────┐                ┌─────────┐                        │
│   │ INGEST  │                │  EMBED  │                        │
│   │ (once)  │                │ (query) │                        │
│   └────┬────┘                └────┬────┘                        │
│        │                          │                             │
│        ▼                          ▼                             │
│   ┌─────────┐    search     ┌─────────┐                        │
│   │ Vector  │◄──────────────│ Vector  │                        │
│   │   DB    │               │ (query) │                        │
│   └────┬────┘               └─────────┘                        │
│        │                                                        │
│        │ top 5 matching chunks                                  │
│        ▼                                                        │
│   ┌─────────────────────────────────────┐                      │
│   │              CLAUDE                  │                      │
│   │                                      │                      │
│   │  "Here are the relevant docs:        │                      │
│   │   [chunk 1] [chunk 2] [chunk 3]...   │                      │
│   │                                      │                      │
│   │   Question: What is the fee?         │                      │
│   │                                      │                      │
│   │   Answer ONLY from these docs."      │                      │
│   └──────────────┬──────────────────────┘                      │
│                  │                                              │
│                  ▼                                              │
│              ANSWER                                             │
│   "The Non-Display A1 fee is $1,012/month                      │
│    (source: gme-fee-notice.pdf, page 1)"                       │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

**Two phases:**

1. **Ingestion** (once): Turn your PDFs into searchable pieces
1. **Query** (every question): Find relevant pieces, ask Claude

______________________________________________________________________

## Part 3: Ingestion - Making Documents Searchable

### Step 1: Extract Text from PDFs

```
PDF File                         Plain Text
┌──────────────┐                ┌──────────────────────────────┐
│ ▓▓▓▓▓▓▓▓▓▓▓▓ │                │ CME Market Data Fee Notice   │
│ ▓▓▓▓▓▓▓▓▓▓▓▓ │  ───────────► │                              │
│ ▓▓▓▓▓▓▓▓▓▓▓▓ │   PyMuPDF     │ Non-Display A1 fee: $1,012   │
│ ▓▓▓▓▓▓▓▓▓▓▓▓ │                │ ...                          │
└──────────────┘                └──────────────────────────────┘
```

**Code:** `app/extract.py` does this.

### Step 2: Split into Chunks

A 50-page PDF is too big to send to Claude. We split it into smaller pieces.

```
Full Document (10,000 words)
┌────────────────────────────────────────────────────────────────┐
│ Section 1: Introduction                                        │
│ Lorem ipsum dolor sit amet...                                  │
│                                                                │
│ Section 2: Fee Schedule                                        │
│ The Non-Display A1 fee is $1,012 per month...                  │
│                                                                │
│ Section 3: Reporting Requirements                              │
│ Subscribers must report usage quarterly...                     │
└────────────────────────────────────────────────────────────────┘
                              │
                              ▼ split by sections + size
┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐
│ Chunk 1         │  │ Chunk 2         │  │ Chunk 3         │
│ Section 1: ...  │  │ Section 2: ...  │  │ Section 3: ...  │
│ (400 words)     │  │ (400 words)     │  │ (400 words)     │
│                 │  │                 │  │                 │
│ + metadata:     │  │ + metadata:     │  │ + metadata:     │
│   file: abc.pdf │  │   file: abc.pdf │  │   file: abc.pdf │
│   page: 1       │  │   page: 3       │  │   page: 5       │
│   section: Intro│  │   section: Fees │  │   section: Rpt  │
└─────────────────┘  └─────────────────┘  └─────────────────┘
```

**Code:** `app/chunking.py` does this.

### Step 3: Convert Chunks to Vectors (Embeddings)

This is the magic part. We convert text into numbers that capture meaning.

```
Text                              Vector (simplified)
"Non-Display A1 fee: $1,012"  →   [0.23, -0.45, 0.78, 0.12, ...]
"Professional device: $98"    →   [0.21, -0.42, 0.81, 0.15, ...]
"Report usage quarterly"      →   [-0.55, 0.33, 0.12, 0.89, ...]
```

**Key insight:** Similar meanings → similar vectors.

- "Non-Display A1 fee" and "Professional device" are both about fees
- Their vectors are close together (0.23 ≈ 0.21, -0.45 ≈ -0.42, etc.)

**We use:** `nomic-embed-text` model via Ollama (free, runs locally).

**Code:** `app/embed.py` does this.

### Step 4: Store in Vector Database

ChromaDB stores the vectors so we can search them later.

```
ChromaDB
┌────────────────────────────────────────────────────────────────┐
│  ID      │ Vector                  │ Text           │ Metadata │
├──────────┼─────────────────────────┼────────────────┼──────────┤
│  chunk_1 │ [0.23, -0.45, 0.78...]  │ "Non-Display"  │ fee.pdf  │
│  chunk_2 │ [0.21, -0.42, 0.81...]  │ "Professional" │ fee.pdf  │
│  chunk_3 │ [-0.55, 0.33, 0.12...]  │ "Report usage" │ guide.pdf│
│  ...     │ ...                     │ ...            │ ...      │
└────────────────────────────────────────────────────────────────┘
```

**Code:** `app/ingest.py` orchestrates all of this.

______________________________________________________________________

## Part 4: Query - Answering Questions

### Step 1: Embed the Question

Your question gets converted to a vector too.

```
Question: "What is the Non-Display A1 fee?"
                    │
                    ▼ embed
Vector: [0.22, -0.44, 0.79, 0.13, ...]
```

### Step 2: Find Similar Chunks

Compare the question vector to all stored vectors. Return the closest matches.

```
Question vector: [0.22, -0.44, 0.79, 0.13, ...]

Compare to stored chunks:
  chunk_1: [0.23, -0.45, 0.78...] → distance: 0.02 ✓ CLOSE!
  chunk_2: [0.21, -0.42, 0.81...] → distance: 0.05 ✓ CLOSE!
  chunk_3: [-0.55, 0.33, 0.12...] → distance: 0.89 ✗ far

Return: chunk_1, chunk_2 (top 5 closest)
```

**This is why RAG works:** Questions about fees match chunks about fees, even if the exact words are different.

### Step 3: Build the Prompt

We construct a careful prompt for Claude:

```
┌────────────────────────────────────────────────────────────────┐
│ SYSTEM PROMPT (hidden from user, sent to Claude)              │
├────────────────────────────────────────────────────────────────┤
│ You are an expert on CME license agreements.                  │
│ Answer ONLY using the provided context.                       │
│ If the answer is not in the context, say "I don't know."      │
│ Always cite the source document.                              │
│ Never make up information.                                    │
├────────────────────────────────────────────────────────────────┤
│ CONTEXT (the chunks we retrieved)                             │
├────────────────────────────────────────────────────────────────┤
│ [1] From: fee-schedule.pdf, Page 3                            │
│ "The Non-Display A1 fee for trading as principal is $1,012    │
│  per month per Licensee Group..."                             │
│                                                                │
│ [2] From: fee-schedule.pdf, Page 4                            │
│ "Non-Display A2 for facilitating client business is $505..."  │
├────────────────────────────────────────────────────────────────┤
│ QUESTION                                                       │
├────────────────────────────────────────────────────────────────┤
│ What is the Non-Display A1 fee?                               │
└────────────────────────────────────────────────────────────────┘
```

### Step 4: Claude Generates the Answer

Claude reads the context and question, then generates a response.

```
┌────────────────────────────────────────────────────────────────┐
│ CLAUDE'S ANSWER                                                │
├────────────────────────────────────────────────────────────────┤
│ The Non-Display A1 fee is $1,012 per month per Licensee Group. │
│ This applies to trading as a principal.                        │
│                                                                 │
│ Source: fee-schedule.pdf, Page 3                               │
└────────────────────────────────────────────────────────────────┘
```

**Code:** `app/query.py` does this.

______________________________________________________________________

## Part 5: Where Each Tool Fits

```
┌─────────────────────────────────────────────────────────────────┐
│                        YOUR SYSTEM                              │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  LOCAL (free)                     CLOUD (paid per use)         │
│  ┌─────────────────────┐          ┌─────────────────────┐      │
│  │     Ollama          │          │      Claude API      │      │
│  │  ┌───────────────┐  │          │                      │      │
│  │  │nomic-embed-   │  │          │  Answers questions   │      │
│  │  │text           │  │          │  based on context    │      │
│  │  │               │  │          │                      │      │
│  │  │ Creates       │  │          │  ~$0.003 per query   │      │
│  │  │ embeddings    │  │          │                      │      │
│  │  └───────────────┘  │          └──────────▲──────────┘      │
│  └─────────┬───────────┘                     │                  │
│            │                                 │                  │
│            ▼                                 │                  │
│  ┌─────────────────────┐                     │                  │
│  │     ChromaDB        │                     │                  │
│  │                     │                     │                  │
│  │  Stores vectors     │─────────────────────┘                  │
│  │  Searches for       │   sends matching                       │
│  │  similar chunks     │   chunks + question                    │
│  │                     │                                        │
│  │  (local database)   │                                        │
│  └─────────────────────┘                                        │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

**Why this split?**

- Embeddings are cheap/fast → run locally (Ollama)
- Generation needs intelligence → use Claude API (better quality)
- Storage → local ChromaDB (your data stays on your machine)

______________________________________________________________________

## Part 6: The Code Flow

### Ingestion (`python main.py ingest --provider cme`)

```python
# 1. Find all PDFs
pdfs = list(data/raw/cme/*.pdf)

# 2. For each PDF
for pdf in pdfs:
    # Extract text with page numbers
    doc = extract_pdf(pdf)  # → ExtractedDocument

    # Split into chunks
    chunks = chunk_document(doc)  # → List[Chunk]

    # Each chunk has: text, source file, page, section

# 3. Embed all chunks (calls Ollama)
embeddings = embed_function(chunk_texts)

# 4. Store in ChromaDB
collection.add(
    documents=chunk_texts,
    embeddings=embeddings,
    metadatas=chunk_metadata,
    ids=chunk_ids
)
```

### Query (`python main.py query "What is the A1 fee?"`)

```python
# 1. Embed the question (calls Ollama)
question_vector = embed_function(["What is the A1 fee?"])

# 2. Search ChromaDB for similar chunks
results = collection.query(
    query_embeddings=question_vector,
    n_results=5
)

# 3. Build prompt with retrieved chunks
prompt = f"""
Context:
{format_chunks(results)}

Question: What is the A1 fee?

Answer based only on the context above.
"""

# 4. Send to Claude API
response = anthropic.messages.create(
    model="claude-sonnet-4-20250514",
    messages=[{"role": "user", "content": prompt}]
)

# 5. Print answer with citations
print(response.content)
```

______________________________________________________________________

## Part 7: Why RAG is Better Than Fine-Tuning

You might ask: "Why not just train Claude on my documents?"

| Approach      | RAG                | Fine-Tuning      |
| ------------- | ------------------ | ---------------- |
| Cost          | ~$0.003/query      | $1,000+ to train |
| Update docs   | Just re-ingest     | Retrain model    |
| Citations     | ✅ Knows source    | ❌ Can't cite    |
| Hallucination | Rare (has context) | More common      |
| Setup time    | Hours              | Days/weeks       |

**RAG is the right choice for document Q&A.**

______________________________________________________________________

## Part 8: Common Failure Modes

### 1. Wrong Chunks Retrieved

**Symptom:** Answer is wrong or "I don't know" when answer exists.

**Cause:** Question words don't match document words.

- You ask: "What's the monthly rate?"
- Document says: "Per-device fee: $98"
- "rate" and "fee" are different words

**Fix:** Try rephrasing, or improve chunking to include more context.

### 2. Hallucinated Details

**Symptom:** Claude adds information not in the documents.

**Cause:** Prompt wasn't strict enough, or Claude "filled in gaps."

**Fix:** Stronger system prompt:

```
NEVER add information beyond what's explicitly stated.
If unsure, say "The document doesn't specify."
```

### 3. Missing Citations

**Symptom:** Answer looks right but no source given.

**Cause:** Prompt didn't require citations.

**Fix:** Add to prompt:

```
ALWAYS cite the source document and page number.
Format: (source: filename.pdf, page X)
```

______________________________________________________________________

## Part 9: Glossary

| Term              | Meaning                                                     |
| ----------------- | ----------------------------------------------------------- |
| **LLM**           | Large Language Model - AI that generates text (Claude, GPT) |
| **RAG**           | Retrieval-Augmented Generation - find docs, then ask LLM    |
| **Embedding**     | Converting text to numbers that capture meaning             |
| **Vector**        | A list of numbers representing text meaning                 |
| **Chunk**         | A small piece of a document (~400 words)                    |
| **ChromaDB**      | Database that stores and searches vectors                   |
| **Ollama**        | Tool to run AI models locally                               |
| **Context**       | The documents/chunks sent to Claude with your question      |
| **Hallucination** | When an LLM makes up false information                      |
| **Token**         | A word or word-piece (billing unit for APIs)                |

______________________________________________________________________

## Part 10: Your System's Architecture

```
licencing-rag/
├── data/
│   └── raw/
│       └── cme/           ← Your PDF documents go here
│           ├── fee-schedule.pdf
│           └── ila-guide.pdf
│
├── index/
│   └── chroma/            ← Vector database (auto-created)
│
├── app/
│   ├── config.py          ← Settings (model names, paths)
│   ├── extract.py         ← PDF → text
│   ├── chunking.py        ← text → chunks
│   ├── embed.py           ← text → vectors (Ollama)
│   ├── ingest.py          ← orchestrates ingestion
│   ├── query.py           ← orchestrates queries
│   ├── prompts.py         ← system prompts for Claude
│   └── llm.py             ← Claude API wrapper (to be added)
│
└── main.py                ← CLI entry point
```

______________________________________________________________________

## Next Steps

1. **Set up Claude API** - Get an API key from console.anthropic.com
1. **Test a query** - `python main.py query "What are the CME fees?"`
1. **Add more providers** - Put OPRA docs in `data/raw/opra/`

______________________________________________________________________

## Questions?

If something doesn't make sense, ask! The concepts are simple once you see them in action. The complexity is in the details, not the fundamentals.
