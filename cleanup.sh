#!/usr/bin/env bash
# Deletes all resources provisioned by lab-template.json.
# Usage: ./cleanup.sh -g <resourceGroup> -n <aiHubName> -s <uniqueSuffix> [-S <searchServiceName>] [--purge-kv] [--dry-run]
#
# Defaults match the template defaults:
#   aiHubName        = lab-demo
#   searchServiceName = contosoproducts
#   uniqueSuffix     = (required — no default)

set -euo pipefail

# ── Defaults ────────────────────────────────────────────────────────────────
RESOURCE_GROUP="rg-student-lab-01-9697"
AI_HUB_NAME="lab-demo"
UNIQUE_SUFFIX="slab"
SEARCH_SERVICE_NAME="contosoproducts"
PURGE_KV=false
DRY_RUN=false

# ── Argument parsing ─────────────────────────────────────────────────────────
usage() {
  echo "Usage: $0 -g <resourceGroup> -s <uniqueSuffix> [-n <aiHubName>] [-S <searchServiceName>] [--purge-kv] [--dry-run]"
  exit 1
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    -g) RESOURCE_GROUP="$2"; shift 2 ;;
    -n) AI_HUB_NAME="$2";    shift 2 ;;
    -s) UNIQUE_SUFFIX="$2";  shift 2 ;;
    -S) SEARCH_SERVICE_NAME="$2"; shift 2 ;;
    --purge-kv) PURGE_KV=true; shift ;;
    --dry-run)  DRY_RUN=true;  shift ;;
    *) usage ;;
  esac
done

[[ -z "$RESOURCE_GROUP" || -z "$UNIQUE_SUFFIX" ]] && usage

# ── Derived resource names (mirror template logic) ───────────────────────────
NAME="$(echo "$AI_HUB_NAME" | tr '[:upper:]' '[:lower:]')"
AI_SERVICES_NAME="ais${NAME}${UNIQUE_SUFFIX}"
STORAGE_NAME="st${NAME}${UNIQUE_SUFFIX}"
STORAGE_NAME="${STORAGE_NAME//-/}"                   # remove dashes
KV_NAME="kv-${NAME}-${UNIQUE_SUFFIX}"
SEARCH_NAME="${SEARCH_SERVICE_NAME}-${UNIQUE_SUFFIX}"
HUB_NAME="aih-${NAME}-${UNIQUE_SUFFIX}"
PROJECT_NAME="aip-${NAME}-${UNIQUE_SUFFIX}"
CONNECTION_NAME="${HUB_NAME}-connection-AzureOpenAI"

# ── Helpers ──────────────────────────────────────────────────────────────────
run() {
  if $DRY_RUN; then
    echo "[dry-run] $*"
  else
    echo "Running: $*"
    "$@"
  fi
}

delete_resource() {
  local type="$1" name="$2"
  echo "Deleting $type: $name"
  run az resource delete \
    --resource-group "$RESOURCE_GROUP" \
    --resource-type "$type" \
    --name "$name" \
    --no-wait
}

# ── Summary ──────────────────────────────────────────────────────────────────
echo ""
echo "=== Lab Cleanup ==="
echo "  Resource Group : $RESOURCE_GROUP"
echo "  AI Hub         : $HUB_NAME"
echo "  AI Project     : $PROJECT_NAME"
echo "  Connection     : $CONNECTION_NAME"
echo "  AI Services    : $AI_SERVICES_NAME"
echo "  Search         : $SEARCH_NAME"
echo "  Storage        : $STORAGE_NAME"
echo "  Key Vault      : $KV_NAME"
echo "  Purge KV       : $PURGE_KV"
echo "  Dry Run        : $DRY_RUN"
echo ""

if ! $DRY_RUN; then
  read -r -p "Proceed with deletion? [y/N] " confirm
  [[ "$(echo "$confirm" | tr '[:upper:]' '[:lower:]')" == "y" ]] || { echo "Aborted."; exit 0; }
fi

# ── 1. ML workspace connection ───────────────────────────────────────────────
echo ""
echo "--- Removing ML workspace connection ---"
run az ml connection delete \
  --name "$CONNECTION_NAME" \
  --workspace-name "$HUB_NAME" \
  --resource-group "$RESOURCE_GROUP" \
  --yes 2>/dev/null || echo "  (connection not found or already removed)"

# ── 2. ML Project workspace ──────────────────────────────────────────────────
echo ""
echo "--- Removing ML Project workspace ---"
run az ml workspace delete \
  --name "$PROJECT_NAME" \
  --resource-group "$RESOURCE_GROUP" \
  --yes \
  --no-wait 2>/dev/null || echo "  (project workspace not found)"

# ── 3. ML Hub workspace ──────────────────────────────────────────────────────
echo ""
echo "--- Removing ML Hub workspace ---"
run az ml workspace delete \
  --name "$HUB_NAME" \
  --resource-group "$RESOURCE_GROUP" \
  --yes \
  --no-wait 2>/dev/null || echo "  (hub workspace not found)"

# ── 4. Azure AI Search ───────────────────────────────────────────────────────
echo ""
echo "--- Removing Azure AI Search ---"
run az search service delete \
  --name "$SEARCH_NAME" \
  --resource-group "$RESOURCE_GROUP" \
  --yes 2>/dev/null || echo "  (search service not found)"

# ── 5. Storage account ───────────────────────────────────────────────────────
echo ""
echo "--- Removing Storage Account ---"
run az storage account delete \
  --name "$STORAGE_NAME" \
  --resource-group "$RESOURCE_GROUP" \
  --yes 2>/dev/null || echo "  (storage account not found)"

# ── 6. AI Services (Cognitive Services) ─────────────────────────────────────
echo ""
echo "--- Removing AI Services ---"
run az cognitiveservices account delete \
  --name "$AI_SERVICES_NAME" \
  --resource-group "$RESOURCE_GROUP" 2>/dev/null || echo "  (AI services not found)"

# Purge ALL soft-deleted instances of this account name across any resource group.
# Required because the template uses "restore: true" — any lingering soft-deleted
# account with the same name blocks deployment to a new resource group.
if ! $DRY_RUN; then
  DELETED_JSON=$(az cognitiveservices account list-deleted \
    --query "[?name=='$AI_SERVICES_NAME'].[location, resourceGroup]" -o tsv 2>/dev/null || true)
  if [[ -n "$DELETED_JSON" ]]; then
    while IFS=$'\t' read -r del_location del_rg; do
      echo "  Purging soft-deleted AI Services (rg=$del_rg, location=$del_location)..."
      az cognitiveservices account purge \
        --name "$AI_SERVICES_NAME" \
        --resource-group "$del_rg" \
        --location "$del_location" || echo "  (purge failed — may already be purged)"
    done <<< "$DELETED_JSON"
  else
    echo "  (no soft-deleted AI Services found)"
  fi
else
  echo "[dry-run] Would purge all soft-deleted AI Services named '$AI_SERVICES_NAME' across all resource groups"
fi

# ── 7. Key Vault ─────────────────────────────────────────────────────────────
echo ""
echo "--- Removing Key Vault ---"
run az keyvault delete \
  --name "$KV_NAME" \
  --resource-group "$RESOURCE_GROUP" 2>/dev/null || echo "  (key vault not found)"

if $PURGE_KV; then
  echo "  Purging soft-deleted Key Vault..."
  if ! $DRY_RUN; then
    LOCATION=$(az keyvault list-deleted \
      --query "[?name=='$KV_NAME'].properties.location | [0]" -o tsv 2>/dev/null || true)
    if [[ -n "$LOCATION" ]]; then
      run az keyvault purge --name "$KV_NAME" --location "$LOCATION"
    else
      echo "  (no soft-deleted Key Vault found to purge)"
    fi
  else
    echo "[dry-run] Would purge soft-deleted Key Vault"
  fi
fi

echo ""
echo "=== Cleanup complete ==="
echo "Note: ML workspace deletions were issued with --no-wait."
echo "      Run 'az ml workspace show -n $HUB_NAME -g $RESOURCE_GROUP' to confirm deletion."
