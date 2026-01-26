# app/chunking.py

import re

SECTION_REGEX = re.compile(r"(?m)^(SECTION|Article|\d+(\.\d+)*)\s+.*$")


def split_by_sections(text):
    matches = list(SECTION_REGEX.finditer(text))
    if not matches:
        return [text]

    chunks = []
    for i, match in enumerate(matches):
        start = match.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        chunks.append(text[start:end].strip())
    return chunks


def window_chunk(text, size=800, overlap=120):
    words = text.split()
    chunks = []
    i = 0
    while i < len(words):
        chunk = words[i : i + size]
        chunks.append(" ".join(chunk))
        i += size - overlap
    return chunks


def chunk_document(text):
    sections = split_by_sections(text)
    final_chunks = []
    for section in sections:
        final_chunks.extend(window_chunk(section))
    return final_chunks
