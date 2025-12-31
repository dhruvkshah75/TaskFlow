import requests
import time
import sys
import json
from datetime import datetime, timezone

# CONFIGURATION
API_URL = "http://127.0.0.1:8080"  # Port-forwarded to taskflow-api service
# Use timestamp to create unique user for each run
USERNAME = f"integration_user_{int(time.time())}"
PASSWORD = "strongpassword123"
EMAIL = f"integration_{int(time.time())}@test.com"
NUM_TASKS = 20
BATCH_SIZE = 10  # Send in batches

def run_integration_test():
    print(f"Connecting to {API_URL}...")

    # 1. CREATE USER
    print("Creating test user...")
    try:
        requests.post(f"{API_URL}/users/", json={
            "username": USERNAME,
            "email": EMAIL,
            "password": PASSWORD
        })
    except Exception as e:
        print(f"Note: User creation might have failed or already exists: {e}")

    # 2. LOGIN (Get Token)
    print("Logging in...")
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

    # 3. GENERATE TASKS
    print(f"Starting Integration Test ({NUM_TASKS} tasks)...")
    
    # scheduled_at = 0 means schedule immediately
    scheduled_minutes = 0
    
    count = 0
    failed_count = 0
    
    # Calculate batches
    num_batches = (NUM_TASKS + BATCH_SIZE - 1) // BATCH_SIZE
    
    for batch in range(num_batches):
        start_idx = batch * BATCH_SIZE
        end_idx = min((batch + 1) * BATCH_SIZE, NUM_TASKS)
        batch_size = end_idx - start_idx
        
        print(f"Batch {batch + 1}/{num_batches} ({batch_size} tasks)...", end=" ")
        
        for i in range(start_idx, end_idx):
            try:
                # Payload must be a JSON string inside the JSON body
                resp = requests.post(
                    f"{API_URL}/tasks/", 
                    headers=headers, 
                    json={
                        "title": f"Integration Task {i}", 
                        "payload": json.dumps({"type": "standard_task"}), # Changed payload type name
                        "priority": "high",
                        "scheduled_at": scheduled_minutes
                    },
                    timeout=5 
                )
                
                if resp.status_code in [200, 201]:
                    print(".", end="", flush=True)
                    count += 1
                else:
                    print("x", end="", flush=True)
                    failed_count += 1
                    if failed_count == 1:
                        print(f"\n   First error: {resp.status_code} - {resp.text[:100]}")
            except Exception as e:
                print("!", end="", flush=True)
                failed_count += 1
            
            # Tiny delay to keep CI stable
            time.sleep(0.02)
        
        print(" Done.")
        
        # Simple backoff if we hit errors
        if failed_count > 0 and batch < num_batches - 1:
            time.sleep(2)
    
    print(f"\nTest Complete: Sent {count}/{NUM_TASKS} tasks to the Queue.")
    
    # Fail CI if too many tasks failed
    if count < (NUM_TASKS * 0.8): # Require 80% success
        print("Test Failed: Too many dropped requests.")
        sys.exit(1)
    else:
        print("Integration Test Passed.")

if __name__ == "__main__":
    try:
        run_integration_test()
    except requests.exceptions.ConnectionError:
        print(f"\nCould not connect to {API_URL}. Is the service port-forwarded?")
        sys.exit(1)