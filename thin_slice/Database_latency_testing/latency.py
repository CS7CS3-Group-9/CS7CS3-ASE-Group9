import time
from firebase_admin import firestore, credentials, initialize_app

initialize_app()
db = firestore.client()
accumulator = 0
max = 0


for _ in range(10):
    start = time.time()
    db.collection("Time").document().set({"time": time.time()})
    print(f"Latency: {(time.time()-start)*1000:.2f}ms")
    accumulator += (time.time()-start)*1000
    if max < (time.time()-start)*1000:
        max = (time.time()-start)*1000
    

print(f"Average Latency: {accumulator/10:.2f}ms")
print(f"Max Latency: {max:.2f}ms")
