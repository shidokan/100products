#!/bin/bash
# Deploy outlander-rag to Azure Container Apps with scale-to-zero
# For personal Azure subscription. Reuses .env values for runtime config.

set -e
source .env

# ---- Edit these if your setup differs ----
RG="azureAI"                   # RG containing your AI Search + Storage
LOC="eastus"                   # match your AI Search region (cross-region call to Foundry in eastus2 is fine)
APP="outlander-rag"
ENV_NAME="outlander-env"
ACR_NAME="outlanderacr$RANDOM" # globally unique, lowercase alphanumeric
# ------------------------------------------

echo "=== Deployment plan ==="
echo "Subscription:   $(az account show --query name -o tsv)"
echo "Resource group: $RG"
echo "Location:       $LOC"
echo "ACR name:       $ACR_NAME"
echo "App name:       $APP"
echo "Environment:    $ENV_NAME"
echo ""

echo "=== Step 1/5: Create Container Apps environment ==="
az containerapp env create \
  --name "$ENV_NAME" \
  --resource-group "$RG" \
  --location "$LOC"

echo ""
echo "=== Step 2/5: Create Azure Container Registry (Basic SKU, ~\$5/mo) ==="
az acr create \
  --resource-group "$RG" \
  --name "$ACR_NAME" \
  --sku Basic \
  --admin-enabled true

echo ""
echo "=== Step 3/5: Build container image in ACR (cloud build, no local Docker) ==="
az acr build \
  --registry "$ACR_NAME" \
  --image "$APP:latest" \
  --file Dockerfile \
  .

echo ""
echo "=== Step 4/5: Pull ACR credentials ==="
ACR_LOGIN_SERVER=$(az acr show --name "$ACR_NAME" --query loginServer -o tsv)
ACR_USERNAME=$(az acr credential show --name "$ACR_NAME" --query username -o tsv)
ACR_PASSWORD=$(az acr credential show --name "$ACR_NAME" --query "passwords[0].value" -o tsv)
echo "ACR login server: $ACR_LOGIN_SERVER"

echo ""
echo "=== Step 5/5: Deploy Container App with scale-to-zero ==="
az containerapp create \
  --name "$APP" \
  --resource-group "$RG" \
  --environment "$ENV_NAME" \
  --image "${ACR_LOGIN_SERVER}/${APP}:latest" \
  --registry-server "$ACR_LOGIN_SERVER" \
  --registry-username "$ACR_USERNAME" \
  --registry-password "$ACR_PASSWORD" \
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

URL=$(az containerapp show \
  --name "$APP" \
  --resource-group "$RG" \
  --query properties.configuration.ingress.fqdn \
  -o tsv)

echo ""
echo "============================================================"
echo "DEPLOYED at: https://$URL"
echo "============================================================"
echo ""
echo "First request after idle takes ~5-15 seconds (cold start)."
echo "Subsequent requests are fast. Container scales to zero when idle."
echo ""
echo "Test:"
echo "  open https://$URL"
echo "  curl https://$URL/health"
echo "  curl -X POST https://$URL/chat -H 'Content-Type: application/json' \\"
echo "    -d '{\"question\":\"Which sleeping pad has the highest R-value?\"}'"
echo ""
echo "Logs:"
echo "  az containerapp logs show -n $APP -g $RG --follow"
