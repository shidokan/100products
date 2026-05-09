# Outlander RAG — Personal Azure Deployment Guide

This guide covers deploying the Outlander Gear RAG service to your **personal**
Azure subscription as a permanent portfolio piece. Unlike the Udacity sandbox
(which had quota restrictions), a personal subscription has full access to
all Azure services. The cleanest approach is **Container Apps with scale-to-zero
as the primary** and **App Service Free tier as an optional always-on alternative**.

## Architecture for the personal deployment

```
                     ┌──────────────────────────┐
                     │  Azure Container Apps    │
                     │  (scale-to-zero)         │
                     │  outlander-rag           │
                     │  https://...azurecontainerapps.io
                     └───────┬──────────────────┘
                             │
                ┌────────────┴────────────┐
                │                         │
                ▼                         ▼
        ┌──────────────┐          ┌──────────────────┐
        │ Azure OpenAI │          │ Azure AI Search  │
        │  Foundry     │          │  Free or Basic   │
        │  resource    │          │  outlander-      │
        │              │          │  products index  │
        │ • gpt-4o     │          │ (~750 chunks for │
        │ • ada-002    │          │  100 products)   │
        └──────────────┘          └──────────────────┘
                                          ▲
                                          │
                                  ┌───────┴───────────┐
                                  │ Azure Blob Storage│
                                  │ product-info/     │
                                  │ (100 .md files)   │
                                  └───────────────────┘
```

## Cost summary (estimated monthly, low-traffic portfolio piece)

| Component | Service | Approx. cost |
|---|---|---|
| Compute | Container Apps (scale-to-zero) | $0-2 (only when accessed) |
| Vector index | Azure AI Search **Free** tier | $0 |
| Document storage | Blob Storage | $0.10 |
| OpenAI calls (gpt-4o) | Pay-per-token | $0.50 per 200 demo queries |
| OpenAI calls (ada-002) | Pay-per-token | Negligible (one-time embedding) |
| Container registry | ACR Basic | $5 |
| **Total (idle)** | | **~$5/month** |
| **Total (with 200 demo queries/month)** | | **~$6-7/month** |

If you swap Container Apps for **App Service F1 Free tier** the compute drops
to $0 always-on, but with daily CPU caps and idle sleep that may slow first
responses for portfolio viewers.

## Pre-deployment checklist

Before running the deployment script, prepare these items in your personal
Azure subscription:

1. **Azure CLI installed and logged in** to your personal account:
   ```bash
   az login
   az account show --query name -o tsv
   ```

2. **Resource group created** (or pick one to reuse):
   ```bash
   az group create --name outlander-rg --location eastus
   ```

3. **Foundry resource with model deployments** — same shape as the sandbox
   used. From Azure Portal: create a Foundry / Azure AI Services resource,
   then deploy `gpt-4o` and `text-embedding-ada-002` from the model catalog.

4. **Azure AI Search resource** — pick **Free** tier for portfolio purposes
   (3 indexes, 50 MB total — fits 100 products with vectors easily). If you
   want to demonstrate Basic tier features, $75/month.

5. **Azure Storage account** with a container named `product-info`:
   ```bash
   STORAGE="outlanderdata$RANDOM"
   az storage account create \
     --name "$STORAGE" \
     --resource-group outlander-rg \
     --location eastus \
     --sku Standard_LRS

   az storage container create \
     --name product-info \
     --account-name "$STORAGE" \
     --auth-mode login
   ```

6. **Upload all 100 products** to the storage container:
   ```bash
   az storage blob upload-batch \
     --destination product-info \
     --source ./product-info \
     --account-name "$STORAGE" \
     --auth-mode login
   ```

7. **Run the AI Search "Import and vectorize data" wizard** in the Azure
   portal pointing at this storage container. Use the same settings as the
   sandbox (semantic ranker on, embedding model `text-embedding-ada-002`,
   indexer schedule Once, object name prefix `outlander-products`).

8. **Update `.env`** with your personal-account endpoints and keys.

## Path 1 — Container Apps with scale-to-zero (recommended)

Save this as `deploy_personal_aca.sh`:

```bash
#!/bin/bash
set -e
source .env

RG="outlander-rg"
LOC="eastus"
APP="outlander-rag"
ACR_NAME="outlanderacr$RANDOM"
ENV_NAME="outlander-env"

# 1. Create Container Apps environment (managed, includes Log Analytics)
az containerapp env create \
  --name "$ENV_NAME" \
  --resource-group "$RG" \
  --location "$LOC"

# 2. Create Azure Container Registry
az acr create \
  --resource-group "$RG" \
  --name "$ACR_NAME" \
  --sku Basic \
  --admin-enabled true

# 3. Build and push image to ACR
az acr build \
  --registry "$ACR_NAME" \
  --image "$APP:latest" \
  --file Dockerfile \
  .

# 4. Deploy Container App with scale-to-zero
az containerapp create \
  --name "$APP" \
  --resource-group "$RG" \
  --environment "$ENV_NAME" \
  --image "${ACR_NAME}.azurecr.io/${APP}:latest" \
  --registry-server "${ACR_NAME}.azurecr.io" \
  --registry-identity system \
  --target-port 8000 \
  --ingress external \
  --min-replicas 0 \
  --max-replicas 3 \
  --cpu 0.5 \
  --memory 1.0Gi \
  --secrets \
      "aoai-key=$AZURE_OPENAI_API_KEY" \
      "search-key=$AZURE_SEARCH_API_KEY" \
  --env-vars \
      AZURE_OPENAI_ENDPOINT="$AZURE_OPENAI_ENDPOINT" \
      AZURE_OPENAI_API_KEY=secretref:aoai-key \
      AZURE_OPENAI_API_VERSION="$AZURE_OPENAI_API_VERSION" \
      AZURE_OPENAI_CHAT_DEPLOYMENT="$AZURE_OPENAI_CHAT_DEPLOYMENT" \
      AZURE_OPENAI_EMBED_DEPLOYMENT="$AZURE_OPENAI_EMBED_DEPLOYMENT" \
      AZURE_SEARCH_ENDPOINT="$AZURE_SEARCH_ENDPOINT" \
      AZURE_SEARCH_API_KEY=secretref:search-key \
      AZURE_SEARCH_INDEX="$AZURE_SEARCH_INDEX" \
      TOP_K="$TOP_K"

# 5. Print the public URL
URL=$(az containerapp show \
  --name "$APP" \
  --resource-group "$RG" \
  --query properties.configuration.ingress.fqdn \
  -o tsv)

echo ""
echo "=================================================="
echo "Deployed: https://$URL"
echo "=================================================="
echo ""
echo "First request after idle takes ~5-15 seconds (cold start)."
echo "Subsequent requests are fast. Container scales to zero when idle."
```

Run:
```bash
chmod +x deploy_personal_aca.sh
./deploy_personal_aca.sh
```

You'll get a managed HTTPS URL like:
```
https://outlander-rag.kindcliff-12345.eastus.azurecontainerapps.io
```

The container scales to zero replicas when idle (~$0 compute cost), spins up
on the first incoming request (5-15 second cold start), and scales up to 3
replicas if traffic increases.

## Path 2 — App Service F1 Free tier (alternative, always-on)

If you want a permanently-available URL with no cold starts but accept daily
CPU caps and the F1 free tier's 60-minute-per-day compute limit:

```bash
#!/bin/bash
set -e
source .env

RG="outlander-rg"
LOC="eastus"
PLAN="outlander-plan-free"
APP="outlander-rag-app$RANDOM"

# 1. App Service Plan (F1 Free tier — Linux)
az appservice plan create \
  --name "$PLAN" \
  --resource-group "$RG" \
  --location "$LOC" \
  --is-linux \
  --sku F1

# 2. Web App with Python 3.12 runtime
az webapp create \
  --name "$APP" \
  --resource-group "$RG" \
  --plan "$PLAN" \
  --runtime "PYTHON:3.12"

# 3. Startup command for FastAPI
az webapp config set \
  --name "$APP" \
  --resource-group "$RG" \
  --startup-file "uvicorn app:app --host 0.0.0.0 --port 8000"

# 4. App settings
az webapp config appsettings set \
  --name "$APP" \
  --resource-group "$RG" \
  --settings \
      AZURE_OPENAI_ENDPOINT="$AZURE_OPENAI_ENDPOINT" \
      AZURE_OPENAI_API_KEY="$AZURE_OPENAI_API_KEY" \
      AZURE_OPENAI_API_VERSION="$AZURE_OPENAI_API_VERSION" \
      AZURE_OPENAI_CHAT_DEPLOYMENT="$AZURE_OPENAI_CHAT_DEPLOYMENT" \
      AZURE_OPENAI_EMBED_DEPLOYMENT="$AZURE_OPENAI_EMBED_DEPLOYMENT" \
      AZURE_SEARCH_ENDPOINT="$AZURE_SEARCH_ENDPOINT" \
      AZURE_SEARCH_API_KEY="$AZURE_SEARCH_API_KEY" \
      AZURE_SEARCH_INDEX="$AZURE_SEARCH_INDEX" \
      TOP_K="$TOP_K" \
      SCM_DO_BUILD_DURING_DEPLOYMENT=true

# 5. Zip and deploy
zip -r outlander_rag.zip outlander_rag.py app.py requirements.txt -x "*.pyc"
az webapp deploy \
  --name "$APP" \
  --resource-group "$RG" \
  --src-path outlander_rag.zip \
  --type zip

echo ""
echo "Deployed: https://${APP}.azurewebsites.net"
```

The URL is permanent and HTTPS-terminated by Azure. The trade-off is the F1
tier's daily CPU caps (60 minutes) and sleep-after-idle behavior.

## Hardening for portfolio use

These steps make the deployment more presentable for a public portfolio.

### 1. Add basic authentication to the FastAPI app

The default app has no auth, meaning anyone with the URL can use it (and
burn your gpt-4o tokens). Add a simple API key check:

```python
# In app.py, add near the top
import os
from fastapi import Header, HTTPException

API_KEY = os.environ.get("APP_API_KEY", "")

def require_api_key(x_api_key: str = Header(None)):
    if not API_KEY or x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API key")

# Then add to chat endpoint:
@app.post("/chat", response_model=ChatResponse, dependencies=[Depends(require_api_key)])
def chat(req: ChatRequest) -> ChatResponse:
    ...
```

Set a strong `APP_API_KEY` in your env vars. Keep `/health` and the HTML page
public so the deployment can be shown to viewers, but require the key for
actual API calls.

### 2. Add rate limiting

Install `slowapi` and limit per-IP requests:

```bash
pip install slowapi
```

```python
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter

@app.post("/chat", dependencies=[Depends(require_api_key)])
@limiter.limit("10/minute")
def chat(req: ChatRequest, request: Request) -> ChatResponse:
    ...
```

### 3. Set Azure budget alerts

In Azure Portal → Cost Management → Budgets → Add a $10 monthly threshold.
You'll get an email if costs exceed expectation (e.g., from a runaway loop
or scraping bot).

### 4. Custom domain (optional)

Container Apps supports custom domains with managed TLS:

```bash
az containerapp hostname add \
  --hostname yourdomain.com \
  --resource-group outlander-rg \
  --name outlander-rag

# Add CNAME record at your DNS provider pointing to the Container Apps URL,
# then bind the cert:
az containerapp hostname bind \
  --hostname yourdomain.com \
  --resource-group outlander-rg \
  --name outlander-rag \
  --validation-method CNAME
```

## Github repo setup for portfolio storytelling

For maximum portfolio value, mirror the project to a public GitHub repo:

1. Initialize repo and push the project (excluding `.env` and `__pycache__`)
2. Add a clean `README.md` with:
   - Architecture diagram (the one above)
   - Live demo URL (your Container Apps deployment)
   - Tech stack summary
   - Setup instructions
   - Sample queries with screenshots
3. Set up GitHub Actions for CI:
   - `pytest` on push
   - Linting with `ruff` or `black`
   - Optional: auto-deploy to Container Apps on merge to main using
     `azure/login@v2` with OIDC federated identity (no long-lived secrets)

This converts your portfolio from "I built this" to "I built this, here's
the live URL, here's the code, and here's the CI/CD pipeline." That's the
full GenAI engineer story.

## Validation after deployment

Once deployed, run these checks:

```bash
# Health check
curl https://<your-url>/health
# Expected: {"status":"ok"}

# Chat call
curl -X POST https://<your-url>/chat \
  -H "Content-Type: application/json" \
  -d '{"question":"How much do the AlpineEdge Climbing Rope cost?"}' | jq

# Browser test
open https://<your-url>/
```

Run the existing `outlander_eval.py` against the new deployment by changing
the `AZURE_OPENAI_ENDPOINT` and search endpoint in `.env` to your personal
versions. The evaluation harness re-tests the same 8 questions; with 100
products it's worth expanding the eval dataset to 15-20 questions covering
the new categories (climbing, water sports, winter gear, fishing, etc.).

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| Container Apps deploy fails with `Microsoft.App not registered` | Resource provider not enabled in your subscription | `az provider register -n Microsoft.App` |
| ACR build fails on `Dockerfile not found` | Running from wrong directory | `cd` into the project root before running |
| Container starts but `/chat` returns 500 | Env vars not set correctly | `az containerapp logs show -n outlander-rag -g outlander-rg --follow` |
| `AZURE_SEARCH_API_KEY invalid` | Used query key instead of admin key | Get the **Primary admin key** from AI Search → Keys |
| Embedding API returns 401 | Wrong endpoint format | Use `https://<name>.openai.azure.com/` not the Foundry project URL |
| Free tier AI Search index won't take vectors | Free tier has reduced vector capacity | Verify `vector_index_size` < 50 MB; reduce chunk count if needed |
