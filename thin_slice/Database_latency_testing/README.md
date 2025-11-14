### Simple script to query database and record latency, printing average and maximum lateny=cy

### Steps to run app
1. Run `python3 -m venv venv`
2. Run `source venv/bin/activate`
3. Run `pip3 install -r requirements.txt`
4. Run `export GOOGLE_APPLICATION_CREDENTIALS="<absolute path to firebase admin creds .json>"`
5. Run `python3 latency.py`