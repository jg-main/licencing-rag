# app/ingest.py

import os

import fitz
from chromadb import Client
from chromadb.config import Settings
from langchain_community.embeddings import OllamaEmbeddings
from tqdm import tqdm

from app.chunking import chunk_document
from app.config import CHROMA_DIR, EMBED_MODEL, RAW_DATA_DIR, TEXT_DATA_DIR


def extract_pdf_text(path):
    doc = fitz.open(path)
    return "\n".join(page.get_text() for page in doc)


def main():
    os.makedirs(TEXT_DATA_DIR, exist_ok=True)

    client = Client(Settings(persist_directory=CHROMA_DIR))
    collection = client.get_or_create_collection("cme_docs")

    embedder = OllamaEmbeddings(model=EMBED_MODEL)

    for file in tqdm(os.listdir(RAW_DATA_DIR)):
        if not file.lower().endswith(".pdf"):
            continue

        raw_path = os.path.join(RAW_DATA_DIR, file)
        text = extract_pdf_text(raw_path)

        chunks = chunk_document(text)

        embeddings = embedder.embed_documents(chunks)

        collection.add(
            documents=chunks,
            embeddings=embeddings,
            metadatas=[{"source": file, "chunk": i} for i in range(len(chunks))],
            ids=[f"{file}_{i}" for i in range(len(chunks))],
        )

    client.persist()


if __name__ == "__main__":
    main()
