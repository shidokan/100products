"""
Outlander Gear RAG Chatbot
==========================

Bridges:
  - Azure AI Search (Central US, Basic tier) — index: outlander-products
  - Azure OpenAI / Foundry (East US) — gpt-4o + text-embedding-ada-002

Replicates the Foundry Chat playground "Add your data" flow.
Used because Foundry's Add-your-data wizard rejects Basic-tier AI Search
in the Udacity sandbox (a Microsoft-side requirement tightening).

Usage:
    pip install -r requirements.txt
    cp .env.template .env  # then fill in the values
    python outlander_rag.py
"""

import os
import sys
import textwrap
from typing import List, Tuple

from dotenv import load_dotenv
from openai import AzureOpenAI
from azure.core.credentials import AzureKeyCredential
from azure.search.documents import SearchClient
from azure.search.documents.models import VectorizedQuery

load_dotenv()

# ---------- Config ----------
AOAI_ENDPOINT       = os.environ["AZURE_OPENAI_ENDPOINT"]            # e.g. https://outlander.openai.azure.com/
AOAI_API_KEY        = os.environ["AZURE_OPENAI_API_KEY"]
AOAI_API_VERSION    = os.getenv("AZURE_OPENAI_API_VERSION", "2024-08-01-preview")
CHAT_DEPLOYMENT     = os.getenv("AZURE_OPENAI_CHAT_DEPLOYMENT", "gpt-4o")
EMBED_DEPLOYMENT    = os.getenv("AZURE_OPENAI_EMBED_DEPLOYMENT", "text-embedding-ada-002")

SEARCH_ENDPOINT     = os.environ["AZURE_SEARCH_ENDPOINT"]            # e.g. https://outlander.search.windows.net
SEARCH_API_KEY      = os.environ["AZURE_SEARCH_API_KEY"]
SEARCH_INDEX        = os.getenv("AZURE_SEARCH_INDEX", "outlander-products")
# Import & Vectorize wizard names the semantic config "<index>-semantic-configuration"
SEARCH_SEMANTIC_CONFIG = os.getenv(
    "AZURE_SEARCH_SEMANTIC_CONFIG",
    f"{SEARCH_INDEX}-semantic-configuration",
)

TOP_K               = int(os.getenv("TOP_K", "5"))
SYSTEM_MESSAGE = textwrap.dedent("""
    You are a product information assistant for Outlander Gear Co., a retailer of
    high-quality outdoor equipment. Answer customer questions only using the provided
    product catalog excerpts. Always cite the specific product name when stating
    facts. If the answer cannot be found in the provided context, say so explicitly
    rather than guessing.
""").strip()

# ---------- Clients ----------
aoai = AzureOpenAI(
    azure_endpoint=AOAI_ENDPOINT,
    api_key=AOAI_API_KEY,
    api_version=AOAI_API_VERSION,
)

search = SearchClient(
    endpoint=SEARCH_ENDPOINT,
    index_name=SEARCH_INDEX,
    credential=AzureKeyCredential(SEARCH_API_KEY),
)


# ---------- Pipeline ----------
def embed(text: str) -> List[float]:
    """Return a 1536-dim ada-002 embedding for the input text."""
    resp = aoai.embeddings.create(model=EMBED_DEPLOYMENT, input=text)
    return resp.data[0].embedding


def retrieve(query: str, top_k: int = TOP_K) -> List[dict]:
    """Hybrid search (keyword + vector) against the outlander-products index."""
    query_vector = embed(query)
    results = search.search(
        search_text=query,
        vector_queries=[VectorizedQuery(
            vector=query_vector,
            k_nearest_neighbors=top_k,
            fields="text_vector",  # field name produced by Import & Vectorize wizard
        )],
        top=top_k,
        query_type="semantic",
        semantic_configuration_name=SEARCH_SEMANTIC_CONFIG,
        select=["chunk", "title", "chunk_id"],
    )
    return [
        {
            "title":    r.get("title", "Unknown"),
            "chunk":    r.get("chunk", ""),
            "chunk_id": r.get("chunk_id", ""),
            "score":    r.get("@search.score", 0.0),
        }
        for r in results
    ]


def format_context(chunks: List[dict]) -> Tuple[str, List[str]]:
    """Format retrieved chunks into a context block + a citation list."""
    context_lines = []
    citations = []
    for i, c in enumerate(chunks, start=1):
        source = c["title"] or c["chunk_id"] or f"source-{i}"
        context_lines.append(f"[{i}] Source: {source}\n{c['chunk']}\n")
        citations.append(f"[{i}] {source}")
    return "\n".join(context_lines), citations


def answer(question: str, history: List[dict]) -> Tuple[str, List[str]]:
    """One full RAG turn: retrieve → augment → generate."""
    chunks = retrieve(question)
    context, citations = format_context(chunks)

    user_message = textwrap.dedent(f"""
        Question: {question}

        Catalog excerpts to ground your answer:
        {context}
    """).strip()

    messages = [{"role": "system", "content": SYSTEM_MESSAGE}]
    messages.extend(history)
    messages.append({"role": "user", "content": user_message})

    resp = aoai.chat.completions.create(
        model=CHAT_DEPLOYMENT,
        messages=messages,
        temperature=0.3,
        max_tokens=600,
    )
    return resp.choices[0].message.content, citations


# ---------- Multi-turn chat loop ----------
def main() -> None:
    print("=" * 72)
    print("Outlander Gear Co. — Product Information Assistant")
    print(f"Index: {SEARCH_INDEX}  |  Chat model: {CHAT_DEPLOYMENT}  |  Top-K: {TOP_K}")
    print("Type 'quit' or Ctrl-D to exit.")
    print("=" * 72)

    history: List[dict] = []

    while True:
        try:
            question = input("\nYou: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye.")
            return

        if not question or question.lower() in {"quit", "exit"}:
            print("Goodbye.")
            return

        try:
            reply, citations = answer(question, history)
        except Exception as e:
            print(f"\nError: {e}", file=sys.stderr)
            continue

        print("\nAssistant:")
        print(textwrap.fill(reply, width=88))
        print("\nCitations:")
        for c in citations:
            print(f"  {c}")

        # keep the last user/assistant turn in history (without the bulky context)
        history.append({"role": "user", "content": question})
        history.append({"role": "assistant", "content": reply})

        # cap history at last 6 exchanges to keep prompt size sane
        if len(history) > 12:
            history = history[-12:]


if __name__ == "__main__":
    main()
