# Outlander Gear — RAG Product Assistant

A retrieval-augmented chat assistant over a 100-product outdoor-equipment catalog, built on Azure AI Foundry (gpt-4o + text-embedding-ada-002), Azure AI Search (hybrid vector + keyword + semantic ranking), and a FastAPI service deployable to Azure Container Apps with scale-to-zero.

> Demonstrates: RAG architecture, hybrid retrieval, evaluation harness with LLM-as-judge, prompt engineering, FastAPI service design, containerization, and Azure cloud deployment.

## Live demo

🔗 **Demo URL:** [https://outlander-rag.wittysand-6ec9ce26.eastus.azurecontainerapps.io](https://outlander-rag.wittysand-6ec9ce26.eastus.azurecontainerapps.io)

> The container scales to zero when idle, so the first request after a period of inactivity may take 5-15 seconds (cold start). Subsequent requests are fast.

Try asking:

- *"Which tent is the most waterproof?"*
- *"How much does the AlpineEdge Climbing Rope cost?"*
- *"Compare the snowshoes available in the catalog."*
- *"Can the warranty for TrailBlaze pants be transferred?"*
- *"What's the most affordable headlamp under $60?"*

Each response is grounded in the indexed product catalog with citations to the specific source markdown files.

## Architecture

```
┌────────────────────────────────────────────────────────────┐
│         Azure Container Apps (scale-to-zero)               │
│         outlander-rag — FastAPI on port 8000               │
│         https://...azurecontainerapps.io                   │
└────────────┬───────────────────────────────────────────────┘
             │
   ┌─────────┴─────────┐
   │                   │
   ▼                   ▼
┌──────────────┐  ┌──────────────────┐
│ Azure OpenAI │  │  Azure AI Search │
│              │  │                  │
│ • gpt-4o     │  │ outlander-       │
│ • ada-002    │  │ products index   │
│              │  │ (~750 chunks)    │
│              │  │ Hybrid + semantic│
└──────────────┘  └──────────────────┘
                          ▲
                          │ Imported & vectorized
                          │
                   ┌──────┴────────────┐
                   │ Azure Blob Storage│
                   │ product-info/     │
                   │ (100 .md files)   │
                   └───────────────────┘
```

**Pipeline at runtime:**

1. User question → `text-embedding-ada-002` → 1536-dim vector
2. Vector + keyword query → Azure AI Search (hybrid) → top-K chunks
3. Semantic re-ranker promotes most relevant chunks
4. Chunks + chat history → `gpt-4o` system+user prompt
5. Grounded response with citations returned to user

## Tech stack

| Layer | Technology |
|---|---|
| LLM | Azure OpenAI `gpt-4o` |
| Embeddings | Azure OpenAI `text-embedding-ada-002` (1536 dim) |
| Vector store | Azure AI Search (hybrid retrieval, semantic re-ranking) |
| Document storage | Azure Blob Storage |
| Web framework | FastAPI |
| Container | Docker (Python 3.12 slim) |
| Container registry | Azure Container Registry |
| Hosting | Azure Container Apps (scale-to-zero) |
| Evaluation | gpt-4o-as-judge (groundedness / relevance / accuracy) |
| Language | Python 3.12 |

## Repository structure

```
.
├── app.py                       FastAPI service (REST API + HTML test page)
├── outlander_rag.py             Core RAG pipeline (retrieve → augment → generate)
├── outlander_eval.py            Evaluation harness (LLM-as-judge)
├── outlander_eval.jsonl         Evaluation dataset
├── outlander_eval_results.csv   Per-question evaluation scores
├── outlander_eval_summary.json  Aggregate evaluation metrics
├── generate_products.py         Synthetic product catalog generator (demonstrates data generation)
├── product-info/                100 product markdown files (item_1.md through item_100.md)
├── Dockerfile                   Python 3.12 container image
├── requirements.txt             Python dependencies
├── .env.template                Environment variable template
├── personal_deploy.md           Detailed Azure deployment guide
└── README.md                    This file
```

## Quick start (local development)

```bash
# 1. Clone
git clone https://github.com/shidokan/100products.git
cd 100products

# 2. Set up Python environment
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 3. Configure environment
cp .env.template .env
# Edit .env with your Azure OpenAI and AI Search endpoints + keys

# 4. Run the CLI chat loop
python outlander_rag.py

# 5. Run the FastAPI service
uvicorn app:app --host 127.0.0.1 --port 8000
# Open http://127.0.0.1:8000 in your browser

# 6. Run the evaluation harness
python outlander_eval.py
```

## Cloud deployment

Detailed instructions in [`personal_deploy.md`](./personal_deploy.md).

The recommended path is **Azure Container Apps with scale-to-zero**, giving:

- Public HTTPS URL with managed TLS certificate
- $0 compute cost when idle (scales to zero replicas)
- Automatic scaling up to handle traffic
- ~$5/month total (Container Registry Basic) for a portfolio-traffic deployment
- One-command deploy via `az containerapp create`

An alternative App Service Free (F1) tier deployment is also documented for an always-on URL with $0 hosting cost.

## Evaluation

The evaluation harness uses `gpt-4o` as a judge to score responses on three dimensions (1-5 scale each):

| Metric | Score |
|---|---|
| Groundedness | 5.00 / 5 |
| Relevance | 5.00 / 5 |
| Accuracy | 5.00 / 5 |
| **Overall** | **5.00 / 5** |

Run yourself with:

```bash
python outlander_eval.py
```

The harness is meaningfully self-correcting: in early iterations it caught a factual mismatch where the ground-truth dataset was wrong (claimed 3-person capacity for the Alpine Explorer Tent; catalog actually states 8-person). The chatbot was correct; the eval data needed fixing. This is the kind of behavior that demonstrates the harness actually works — perfect scores on the first run can be a sign the test set isn't challenging enough.

## Catalog generation

The 100-product catalog is generated by [`generate_products.py`](./generate_products.py), which produces structured markdown files with consistent schema (features, technical specs, FAQ, warranty) across 10 product categories:

- Tents and shelters
- Hiking footwear and apparel
- Climbing gear (ropes, harnesses, hardware)
- Water sports (kayaks, paddles, dry bags)
- Winter sports (snowshoes, ice axes, crampons)
- Fishing equipment
- Cooking and water filtration
- Lighting (headlamps, lanterns)
- Tools (multi-tools, GPS, knives)
- Sleeping accessories and hydration

The synthetic catalog is intentional — it lets the data generation pipeline be reviewed alongside the RAG pipeline, demonstrating end-to-end engineering rather than just integration with a third-party dataset.

## Design decisions worth highlighting

**Why hybrid + semantic search instead of pure vector?** Pure vector retrieval excels at semantic similarity but misses exact-match queries (specific product names, dollar figures, model numbers). Hybrid retrieval combines vector similarity with BM25 keyword matching, then semantic re-ranking promotes the most contextually relevant chunks. This produces measurably better answers on a product catalog where exact identifiers matter.

**Why ada-002 instead of text-embedding-3?** Ada-002 produces 1536-dim vectors with proven quality on retail product data. The newer `text-embedding-3-large` (3072 dim) would provide marginal accuracy gains at 2x the index storage cost. For this dataset size, ada-002 is the right balance.

**Why Container Apps instead of App Service or Functions?** Container Apps provides scale-to-zero billing (zero compute cost when idle), managed HTTPS, modern container packaging, and revision-based deployments — all features that App Service Basic doesn't have, and that Functions doesn't expose as cleanly for a FastAPI app. For a low-traffic portfolio piece, scale-to-zero is the cost-optimal choice.

**Why an explicit eval harness?** RAG quality degrades silently — bad embeddings, wrong chunk size, irrelevant retrieval all manifest as wrong-but-plausible answers. The eval harness is the production safeguard that catches drift after model upgrades or catalog changes. The LLM-as-judge approach is more nuanced than exact-match scoring while still being automated.

## License

MIT — see [LICENSE](./LICENSE).

## Author

John Cueva
