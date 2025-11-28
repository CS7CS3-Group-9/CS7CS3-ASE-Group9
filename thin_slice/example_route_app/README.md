## Example app to demonstrate the google route and geocoding apis as well as FirebaseDB integration

### Steps to run app locally
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