#!/bin/bash
# =============================================================================
# Maintenance-Eye — One-Command Deployment Script
# Deploys to GCP using Terraform + Cloud Build
#
# Prerequisites:
#   1. gcloud CLI installed and authenticated
#   2. Terraform installed
#   3. GCP project created
#   4. Gemini API key from https://aistudio.google.com/apikey
#
# Usage:
#   ./scripts/deploy.sh <project-id> <gemini-api-key> [region] [allowed-origins]
# =============================================================================

set -euo pipefail

PROJECT_ID="${1:?Usage: ./scripts/deploy.sh <project-id> <gemini-api-key> [region] [allowed-origins]}"
GEMINI_API_KEY="${2:?Usage: ./scripts/deploy.sh <project-id> <gemini-api-key> [region] [allowed-origins]}"
REGION="${3:-us-central1}"
ALLOWED_ORIGINS="${4:-}"
SERVICE_NAME="maintenance-eye"

echo "============================================"
echo "  Maintenance-Eye Deployment"
echo "  Project: $PROJECT_ID"
echo "  Region:  $REGION"
echo "============================================"

# 1. Set GCP project
echo ""
echo ">>> Setting GCP project..."
gcloud config set project "$PROJECT_ID"

# 2. Enable required APIs
echo ""
echo ">>> Enabling GCP APIs..."
gcloud services enable \
  run.googleapis.com \
  firestore.googleapis.com \
  storage.googleapis.com \
  secretmanager.googleapis.com \
  cloudbuild.googleapis.com \
  artifactregistry.googleapis.com

# 3. Create Artifact Registry repo (if not exists)
echo ""
echo ">>> Creating Artifact Registry repo..."
gcloud artifacts repositories create maintenance-eye \
  --repository-format=docker \
  --location="$REGION" \
  --quiet 2>/dev/null || echo "  (already exists)"

# 4. Build and push Docker image
# 4. Create/update Secret Manager secret for Gemini API key
echo ""
echo ">>> Ensuring Secret Manager secret exists..."
gcloud secrets describe gemini-api-key --project="$PROJECT_ID" >/dev/null 2>&1 || \
  gcloud secrets create gemini-api-key --replication-policy="automatic" --project="$PROJECT_ID"
printf "%s" "$GEMINI_API_KEY" | gcloud secrets versions add gemini-api-key --data-file=- --project="$PROJECT_ID" >/dev/null

# 5. Build and push Docker image
echo ""
echo ">>> Building Docker image via Cloud Build..."
gcloud builds submit \
  --config=cloudbuild.yaml \
  --substitutions="_REGION=${REGION}"

# 6. Terraform (optional — if user has terraform installed)
if command -v terraform &> /dev/null; then
  echo ""
  echo ">>> Running Terraform..."
  cd terraform
  terraform init
  terraform apply -auto-approve \
    -var="project_id=${PROJECT_ID}" \
    -var="region=${REGION}" \
    -var="gemini_api_key=${GEMINI_API_KEY}" \
    -var="allowed_origins=${ALLOWED_ORIGINS}"
  SERVICE_URL=$(terraform output -raw service_url)
  cd ..
else
  echo ""
  echo ">>> Terraform not installed, skipping IaC. Getting service URL from gcloud..."
  SERVICE_URL=$(gcloud run services describe "$SERVICE_NAME" --region="$REGION" --format="value(status.url)")
fi

echo ""
echo "============================================"
echo "  ✅ Deployment Complete!"
echo "  URL: $SERVICE_URL"
echo "  Health: ${SERVICE_URL}/health"
echo "============================================"
