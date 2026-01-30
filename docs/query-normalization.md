# Query Normalization Guide

This guide explains how user questions are preprocessed before retrieval.

## Overview

Query normalization improves search by extracting core semantic content:

```
"What is a subscriber?" → "subscriber"
"Can you tell me about CME fees?" → "cme fees"
"Please explain non-display use requirements" → "non-display use requirements"
```

**Benefits:**

- Better embedding similarity (fewer filler words)
- Improved BM25 keyword matching (focused terms)
- Consistent retrieval across query phrasings

## How It Works

### 1. Strip Leading Phrases

Removes conversational prefixes:

- "what is"
- "what are"
- "can you"
- "could you"
- "please explain"
- "tell me about"
- "how does"

**Example:**

```
"What is a subscriber?" → "a subscriber?"
"Can you explain the fees?" → "explain the fees?"
```

### 2. Remove Filler Words

Removes common stopwords:

**Articles:** the, a, an\
**Auxiliary verbs:** is, are, was, were, be\
**Conjunctions:** and, or, but\
**Prepositions:** in, on, at, to, for, of, with, from\
**Pronouns:** it, this, that, these, those\
**Quantifiers:** any, some, all

**Example:**

```
"a subscriber?" → "subscriber"
"the fees for redistribution" → "fees redistribution"
```

### 3. Preserve Domain Terms

**Never removes:**

- Technical terms (subscriber, redistribution, non-display)
- Numbers and dates
- Acronyms (CME, OPRA, API)
- Legal terminology
- Proper nouns

**Example:**

```
"What are the CME non-display fees?" → "cme non-display fees"
"Can you explain Section 3.1?" → "section 3.1"
```

## Examples

| Original Query                                            | Normalized Query                 |
| --------------------------------------------------------- | -------------------------------- |
| "What is a subscriber?"                                   | "subscriber"                     |
| "Can you tell me about CME fees?"                         | "cme fees"                       |
| "Please explain the redistribution requirements"          | "redistribution requirements"    |
| "What are the fees for non-display use?"                  | "fees non-display use"           |
| "How does the subscriber definition work?"                | "subscriber definition work"     |
| "What is the difference between display and non-display?" | "difference display non-display" |

## When It Runs

**Automatically** before every query:

```
User Question
    ↓
Query Normalization  ← HERE
    ↓
Embedding
    ↓
Hybrid Search
    ...
```

No configuration needed - always active.

## Impact on Accuracy

**Positive effects:**

- Reduces embedding dimensionality noise
- Focuses BM25 on meaningful keywords
- Improves cross-query consistency

**Evaluation results:**

- Before normalization: 75% chunk recall
- After normalization: 87.5% chunk recall

## Implementation

**Module:** `app/normalize.py`

**Key function:**

```python
def normalize_query(query: str) -> str:
    """Normalize user query for better retrieval.

    Args:
        query: Raw user question

    Returns:
        Normalized query with filler words removed
    """
```

**Algorithm:**

1. Lowercase query
1. Strip leading conversational phrases
1. Remove filler words (preserving domain terms)
1. Clean up extra whitespace
1. Return normalized query

## Configuration

**Edit `app/normalize.py` to customize:**

```python
# Add custom prefixes to strip
STRIP_PREFIXES = [
    "what is",
    "your custom prefix",
]

# Add custom filler words
FILLER_WORDS = {
    "the", "a", "an",
    "your_custom_word",
}
```

**Note:** Over-aggressive normalization can harm accuracy. Test changes with evaluation set.

## Debug Mode

See normalization output:

```bash
rag query --debug "What is a subscriber?"

# Output shows:
# Original query: What is a subscriber?
# Normalized query: subscriber
```

## Limitations

1. **English only** - Not designed for other languages
1. **Context-blind** - Doesn't understand negation ("not a subscriber")
1. **Aggressive** - May remove meaningful prepositions in rare cases
1. **Domain-specific** - Optimized for license agreement queries

## Best Practices

1. **Use natural questions** - System handles normalization
1. **Be specific** - "CME subscriber fees" better than "fees"
1. **Include key terms** - "non-display use" vs "use"
1. **Test edge cases** - Use `--debug` to verify normalization

## Advanced: Custom Normalization

For domain-specific tuning:

```python
# app/normalize.py

# Example: Preserve legal citations
import re

def normalize_query(query: str) -> str:
    # Protect citations like "Section 3.1" from normalization
    protected = re.findall(r'Section \d+\.\d+', query, re.IGNORECASE)

    # ... normal normalization ...

    # Restore protected terms
    return normalized
```

## See Also

- [Hybrid Search Guide](hybrid-search.md) - How normalized queries are used
- [Configuration Guide](configuration.md) - Search settings
- [Developer Guide](development/DEVELOPER_GUIDE.md) - Implementation details
