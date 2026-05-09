#!/bin/bash
# Quick redeploy: rebuilds the container image and updates the Container App.
# Use this after code changes (UI tweaks, new features, etc.) — much faster
# than tearing down and re-running deploy_personal_aca.sh.

set -e
source .env

RG="azureAI"
APP="outlander-rag"

# Find the existing ACR (assumes one ACR with name starting with "outlanderacr")
ACR_NAME=$(az acr list --resource-group "$RG" --query "[?starts_with(name,'outlanderacr')].name | [0]" -o tsv)

if [ -z "$ACR_NAME" ]; then
  echo "ERROR: No outlander ACR found in $RG. Run deploy_personal_aca.sh first."
  exit 1
fi

echo "Using ACR: $ACR_NAME"
echo ""

echo "=== Rebuilding container image ==="
az acr build \
  --registry "$ACR_NAME" \
  --image "$APP:latest" \
  --file Dockerfile \
  .

echo ""
echo "=== Restarting Container App revision (pulls latest image) ==="
# Force a new revision to pull the rebuilt :latest tag
az containerapp update \
  --name "$APP" \
  --resource-group "$RG" \
  --image "${ACR_NAME}.azurecr.io/${APP}:latest"

URL=$(az containerapp show \
  --name "$APP" \
  --resource-group "$RG" \
  --query properties.configuration.ingress.fqdn \
  -o tsv)

echo ""
echo "============================================================"
echo "Redeployed at: https://$URL"
echo "============================================================"
echo ""
echo "Cold start of new revision takes ~10-20 seconds."
echo "Hard-refresh your browser (Cmd-Shift-R) to bypass cached HTML."
