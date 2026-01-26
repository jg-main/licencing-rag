# app/query.py

import sys

from chromadb import Client
from chromadb.config import Settings
from langchain_community.llms import Ollama

from app.config import CHROMA_DIR, LLM_MODEL, TOP_K
from app.promps import QA_PROMPT, SYSTEM_PROMPT


def main(question):
    client = Client(Settings(persist_directory=CHROMA_DIR))
    collection = client.get_collection("cme_docs")

    results = collection.query(query_texts=[question], n_results=TOP_K)
    if results is None or len(results["documents"][0]) == 0:
        print("No relevant documents found.")
        return

    docs = results["documents"][0]
    metas = results["metadatas"][0]

    context = ""
    for d, m in zip(docs, metas):
        context += f"\n--- {m['source']} (chunk {m['chunk']}) ---\n{d}\n"

    llm = Ollama(model=LLM_MODEL, system=SYSTEM_PROMPT)
    prompt = QA_PROMPT.format(context=context, question=question)

    print(llm(prompt))


if __name__ == "__main__":
    main(sys.argv[1])
