## Example app to demonstrate the google route and geocoding apis as well as FirebaseDB integration

### Steps to run app locally
(This only works in WSL or Linux)
1. Run `python3 -m venv venv`
2. Run `source venv/bin/activate`
3. Run `pip3 install -r requirements.txt`
4. Run `export GOOGLE_API_KEY="<your api key with routes and geocoding enabled>"`
5. Run `export GOOGLE_APPLICATION_CREDENTIALS="<absolute path to firebase admin creds .json>"`
6. To run app on localhost run `flask run`

Run `deactivate` to deactivate the venv

### Steps to deploy app to google cloud run using build_and_deploy script
1. Make sure you are logged into gcloud-cli in your local environment, install it and log in if not
2. Make sure you have access to the ase-city-management 
3. Run `./build_and_deploy.sh` from this directory
4. Profit!!!

### CD pipeline notes:
1. Merging a PR to main branch on the github with changes in this dirctory will automatically trigger a build and deployment job in google build and run


# Deployment Guide Powershell
This it to deploy using your local repository without using the CD Pipeline
This guide explains how to deploy the route-app to Google Cloud Run.

## Prerequisites

Before deploying, ensure you have the following installed and configured:

1. **Docker Desktop** - [Download here](https://www.docker.com/products/docker-desktop/)
   - Must be running before deployment
   
2. **Google Cloud SDK (gcloud)** - [Installation guide](https://cloud.google.com/sdk/docs/install)
   - Verify installation: `gcloud --version`

3. **Project Access** - You need the following IAM roles on the `ase-city-management` project:
   - `roles/editor` (recommended)
   - OR minimum: `roles/serviceusage.serviceUsageAdmin`, `roles/run.admin`, `roles/artifactregistry.admin`

## Initial Setup (One-time only)

### 1. Authenticate with Google Cloud

```powershell
# Initialize gcloud and select your account
gcloud init

# Set up application default credentials
gcloud auth application-default login

# Verify you're using the correct project
gcloud config set project ase-city-management
```

### 2. Configure Docker Authentication

```powershell
# Authenticate Docker with Artifact Registry
gcloud auth configure-docker europe-west1-docker.pkg.dev
```

### 3. Enable Required Services (if not already enabled)

```powershell
gcloud services enable run.googleapis.com artifactregistry.googleapis.com
```

## Deployment

### Option 1: Using PowerShell Script (Recommended for Windows)

1. **Navigate to the app directory:**
   ```powershell
   cd thin_slice/example_route_app
   ```

2. **Run the deployment script:**
   ```powershell
   .\build_and_deploy.ps1
   ```

3. **Access your deployed service:**
   - The script will output the service URL at the end
   - Example: `https://route-app-otw57csiuq-ew.a.run.app`

### Option 2: Using Bash Script (Linux/Mac/WSL)

1. **Navigate to the app directory:**
   ```bash
   cd thin_slice/example_route_app
   ```

2. **Make the script executable (first time only):**
   ```bash
   chmod +x build_and_deploy.sh
   ```

3. **Run the deployment script:**
   ```bash
   ./build_and_deploy.sh
   ```

### Option 3: Manual Deployment

If you prefer to run commands individually:

```powershell
# Set variables
$PROJECT_ID = "ase-city-management"
$REGION = "europe-west1"
$REPO = "route-app-repo"
$SERVICE_NAME = "route-app"
$IMAGE_NAME = "route-app"
$ARTIFACT_URL = "${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPO}/${IMAGE_NAME}:latest"

# Build and push
docker build -t $IMAGE_NAME .
docker tag $IMAGE_NAME $ARTIFACT_URL
docker push $ARTIFACT_URL

# Deploy
gcloud run deploy $SERVICE_NAME --image=$ARTIFACT_URL --region=$REGION --platform=managed --allow-unauthenticated
```

## Troubleshooting

### Common Issues

**1. "gcloud: command not found"**
- Solution: Add gcloud to your PATH or restart your terminal after installation
  ```powershell
  $env:Path += ";C:\Users\YOUR_USERNAME\AppData\Local\Google\Cloud SDK\google-cloud-sdk\bin"
  ```

**2. "Permission denied" errors**
- Solution: Contact the project owner to grant you Editor role:
  ```bash
  gcloud projects add-iam-policy-binding ase-city-management \
      --member="user:YOUR_EMAIL@gmail.com" \
      --role="roles/editor"
  ```

**3. "Docker daemon not running"**
- Solution: Start Docker Desktop and wait for it to fully initialize

**4. "Invalid reference format" error**
- Solution: Make sure you're using PowerShell's `${}` syntax for variables:
  ```powershell
  $ARTIFACT_URL = "${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPO}/${IMAGE_NAME}:latest"
  ```

**5. Authentication issues**
- Solution: Re-authenticate:
  ```powershell
  gcloud auth login
  gcloud auth application-default login
  gcloud auth configure-docker europe-west1-docker.pkg.dev
  ```

## Project Configuration

The deployment uses the following configuration:

- **Project ID:** `ase-city-management`
- **Region:** `europe-west1`
- **Repository:** `route-app-repo`
- **Service Name:** `route-app`
- **Platform:** Cloud Run (managed)
- **Access:** Public (unauthenticated access allowed)

To modify these settings, edit the variables at the top of `build_and_deploy.ps1` or `build_and_deploy.sh`.

## Viewing Logs

To view logs from your deployed service:

```powershell
gcloud run services logs read route-app --region=europe-west1
```

Or view in the [Google Cloud Console](https://console.cloud.google.com/run?project=ase-city-management).

## Updating the Deployment

To deploy a new version:

1. Make your code changes
2. Run the deployment script again
3. Cloud Run will automatically create a new revision and route traffic to it

## Rolling Back

To rollback to a previous revision:

```powershell
# List revisions
gcloud run revisions list --service=route-app --region=europe-west1

# Route traffic to a specific revision
gcloud run services update-traffic route-app --to-revisions=REVISION_NAME=100 --region=europe-west1
```
