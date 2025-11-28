# Cloud Run Deployment Script for route-app
# This script builds a Docker image, pushes it to Google Artifact Registry, 
# and deploys it to Cloud Run

# Configuration
$PROJECT_ID = "ase-city-management"
$REGION = "europe-west1"
$REPO = "route-app-repo"
$SERVICE_NAME = "route-app"
$IMAGE_NAME = "route-app"
$ARTIFACT_URL = "${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPO}/${IMAGE_NAME}:latest"

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Cloud Run Deployment Script" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Set the project
Write-Host "Setting project to: $PROJECT_ID" -ForegroundColor Yellow
gcloud config set project $PROJECT_ID

# Build Docker image
Write-Host "`nBuilding Docker image..." -ForegroundColor Yellow
docker build -t $IMAGE_NAME .

if ($LASTEXITCODE -ne 0) {
    Write-Host "Docker build failed!" -ForegroundColor Red
    exit 1
}

# Tag the image
Write-Host "`nTagging image for Artifact Registry..." -ForegroundColor Yellow
docker tag $IMAGE_NAME $ARTIFACT_URL

# Push to Artifact Registry
Write-Host "`nPushing image to Artifact Registry..." -ForegroundColor Yellow
docker push $ARTIFACT_URL

if ($LASTEXITCODE -ne 0) {
    Write-Host "Docker push failed!" -ForegroundColor Red
    exit 1
}

# Deploy to Cloud Run
Write-Host "`nDeploying to Cloud Run..." -ForegroundColor Yellow
gcloud run deploy $SERVICE_NAME `
    --image=$ARTIFACT_URL `
    --region=$REGION `
    --platform=managed `
    --allow-unauthenticated

if ($LASTEXITCODE -ne 0) {
    Write-Host "Cloud Run deployment failed!" -ForegroundColor Red
    exit 1
}

# Get the service URL
Write-Host "`nRetrieving service URL..." -ForegroundColor Yellow
$URL = gcloud run services describe $SERVICE_NAME --region $REGION --format 'value(status.url)'

Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "Deployment Successful!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host "Your service is live at:" -ForegroundColor Green
Write-Host $URL -ForegroundColor Cyan
Write-Host ""
