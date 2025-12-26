import requests
import time
import sys
import json
from datetime import datetime, timezone

# ⚙️ CONFIGURATION
API_URL = "http://127.0.0.1"  # Or your Minikube IP
# Use timestamp to create unique user for each run (avoids rate limit carryover)
USERNAME = f"stress_tester_{int(time.time())}"
PASSWORD = "strongpassword123"
EMAIL = f"stress_{int(time.time())}@test.com"
NUM_TASKS = 200
BATCH_SIZE = 100  # Send in batches to avoid rate limiting

def run_stress_test():
    print(f"🚀 Connecting to {API_URL}...")

    # 1. CREATE USER (Ignore error if already exists)
    print("👤 Creating user...")
    requests.post(f"{API_URL}/users/", json={
        "username": USERNAME,
        "email": EMAIL,
        "password": PASSWORD
    })

    # 2. LOGIN (Get Token)
    print("🔑 Logging in...")
    # TaskFlow uses /login endpoint with JSON containing identifier and password
    login_response = requests.post(f"{API_URL}/login", json={
        "identifier": USERNAME,
        "password": PASSWORD
    })

    if login_response.status_code != 200:
        print(f"Login Failed: {login_response.text}")
        sys.exit(1)

    token = login_response.json().get("access_token")
    headers = {"Authorization": f"Bearer {token}"}
    print("Login successful! Token acquired.")

    # 3. SPAM TASKS
    print(f"🔥 Starting CPU Attack ({NUM_TASKS} tasks)...")
    print(f"⏱️  Rate limit is 500 requests/hour. Sending in batches with delays...")
    
    # scheduled_at should be in MINUTES from now (not Unix timestamp)
    # Set to 0 to schedule immediately
    scheduled_minutes = 0
    
    count = 0
    failed_count = 0
    
    # Calculate how many batches we need
    num_batches = (NUM_TASKS + BATCH_SIZE - 1) // BATCH_SIZE
    
    for batch in range(num_batches):
        start_idx = batch * BATCH_SIZE
        end_idx = min((batch + 1) * BATCH_SIZE, NUM_TASKS)
        batch_size = end_idx - start_idx
        
        print(f"\n📦 Batch {batch + 1}/{num_batches} ({batch_size} tasks)...")
        
        for i in range(start_idx, end_idx):
            # We send the "heavy_task" payload we added to the worker earlier
            # Note: payload must be a JSON string, not a dict
            resp = requests.post(
                f"{API_URL}/tasks/", 
                headers=headers, 
                json={
                    "title": f"Stress Test {i}", 
                    "payload": json.dumps({"type": "heavy_task"}),
                    "priority": "high",
                    "scheduled_at": scheduled_minutes  # Minutes from now
                }
            )
            
            if resp.status_code in [200, 201]:
                print(".", end="", flush=True)
                count += 1
            else:
                print("x", end="", flush=True)
                failed_count += 1
                if failed_count == 1:  # Print first error for debugging
                    print(f"\nFirst error: {resp.status_code} - {resp.text[:100]}")
            
            # Small delay between requests
            time.sleep(0.05)
        
        # If not the last batch and hit rate limit, wait before next batch
        if batch < num_batches - 1 and failed_count > 0:
            wait_time = 10
            print(f"\n⏸️  Rate limit hit. Waiting {wait_time}s before next batch...")
            time.sleep(wait_time)
            failed_count = 0  # Reset for next batch
    
    print(f"\n✅ Done! Sent {count}/{NUM_TASKS} tasks to the Queue.")

if __name__ == "__main__":
    try:
        run_stress_test()
    except requests.exceptions.ConnectionError:
        print(f"\nCould not connect to {API_URL}. Is 'minikube tunnel' running?")