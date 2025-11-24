import time
import os
from firebase_admin import firestore, credentials, initialize_app

credential_path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
cred = credentials.Certificate(credential_path)
initialize_app(cred)
db = firestore.client()

accumulator = 0
max_latency = 0  # Changed from 'max' to avoid built-in function

for i in range(10):
    start = time.time()
    db.collection("Time").document().set({"time": time.time()})
    time_diff = (time.time() - start) * 1000
    print(f"Latency: {time_diff:.2f}ms")  # Fixed string formatting
    accumulator += time_diff
    if max_latency < time_diff:
        max_latency = time_diff

print(f"Average Latency: {accumulator/10:.2f}ms")
print(f"Max Latency: {max_latency:.2f}ms")
