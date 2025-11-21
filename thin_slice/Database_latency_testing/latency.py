import time
import os


from firebase_admin import firestore, credentials, initialize_app


class LatencyTesting:
    def authenticate_firestore(self):
        """Authenticate and return Firestore client."""
        credential_path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
        cred = credentials.Certificate(credential_path)
        initialize_app(cred)
        db = firestore.client()
        return db
    
    def test_firestore_latency(self, num_tests=10):
        """
        Test Firestore write latency.
        
        Args:
            num_tests (int): Number of write operations to test
        """
        db = self.authenticate_firestore()

        accumulator = 0
        max_latency = 0  

        for i in range(num_tests):
            start = time.time()
            db.collection("Time").document().set({"time": time.time()})
            time_diff = (time.time() - start) * 1000
            print(f"Latency: {time_diff:.2f}ms") 
            accumulator += time_diff
            if max_latency < time_diff:
                max_latency = time_diff
        mean_latency = accumulator / num_tests
        print(f"Average Latency: {mean_latency:.2f}ms")
        print(f"Max Latency: {max_latency:.2f}ms")

        return mean_latency, max_latency


if __name__ == "__main__":
    tester = LatencyTesting()
    tester.test_firestore_latency(100)


