#!/bin/bash

set -e

PROJECT_ID="ase-city-management"
REGION="europe-west1"
REPO="route-app-repo"
SERVICE_NAME="route-app"
IMAGE_NAME="route-app"
ARTIFACT_URL="$REGION-docker.pkg.dev/$PROJECT_ID/$REPO/$IMAGE_NAME:latest"

echo "Using project: $PROJECT_ID"
gcloud config set project $PROJECT_ID

echo "Enabling required services..."
gcloud services enable run.googleapis.com artifactregistry.googleapis.com

echo "Authenticating Docker with Artifact Registry..."
gcloud auth configure-docker $REGION-docker.pkg.dev

echo "Building Docker image..."
docker build -t $IMAGE_NAME .

echo "Tagging image..."
docker tag $IMAGE_NAME $ARTIFACT_URL

echo "Pushing image to Artifact Registry..."
docker push $ARTIFACT_URL

echo "Deploying to Cloud Run..."
gcloud run deploy $SERVICE_NAME \
    --image=$ARTIFACT_URL \
    --region=$REGION \
    --platform=managed \
    --allow-unauthenticated \

echo "Deployment complete!"
URL=$(gcloud run services describe $SERVICE_NAME --region $REGION --format 'value(status.url)')
echo "Your service is live at: $URL"
