## Example app to demonstrate the google route and geocoding apis as well as FirebaseDB integration

### Steps to run app
1. Run `python3 -m venv venv`
2. Run `source venv/bin/activate`
3. Run `pip3 install -r requirements.txt`
4. Run `export GOOGLE_API_KEY="<your api key with routes and geocoding enabled>"`
5. Run `export GOOGLE_APPLICATION_CREDENTIALS="<absolute path to firebase admin creds .json>"`
6. To run app on localhost run `flask run`

Run `deactivate` to deactivate the venv