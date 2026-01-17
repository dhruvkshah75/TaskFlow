import requests
import time
import sys
import random
import json
from datetime import datetime

# CONFIGURATION
API_URL = "http://127.0.0.1:8080"  # Port-forwarded to taskflow-api service
USERNAME = f"autoscale_tester_{int(time.time())}"
PASSWORD = "strongpassword123"
EMAIL = f"autoscale_{int(time.time())}@test.com"
TASK_TITLE = "run_temp2"  # Same title for all tasks
NUM_TASKS = 200

def generate_random_payload():
    """Generate simple payload for the test"""
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return f"autoscale_test by user at {current_time}"

def run_autoscale_test():
    print(f"=== TaskFlow Autoscaling Test ===")
    print(f"Connecting to {API_URL}...")

    # 1. CREATE USER
    print(f"\n[1/4] Creating user '{USERNAME}'...")
    user_response = requests.post(f"{API_URL}/users/", json={
        "username": USERNAME,
        "email": EMAIL,
        "password": PASSWORD
    })
    
    if user_response.status_code in [200, 201]:
        print(f"User created successfully")
    elif user_response.status_code == 400:
        print(f"User already exists (using existing account)")
    else:
        print(f"Failed to create user: {user_response.text}")
        sys.exit(1)

    # 2. LOGIN
    print(f"\n[2/4] Logging in...")
    login_response = requests.post(f"{API_URL}/login", json={
        "identifier": USERNAME,
        "password": PASSWORD
    })

    if login_response.status_code != 200:
        print(f"✗ Login failed: {login_response.text}")
        sys.exit(1)

    token = login_response.json().get("access_token")
    headers = {"Authorization": f"Bearer {token}"}
    print(f"Login successful! Token acquired.")

    # 3. VERIFY TASK FILE EXISTS
    print(f"\n[3/4] Checking if task file '{TASK_TITLE}.py' exists...")
    # Create a dummy task to check if file exists
    test_response = requests.post(
        f"{API_URL}/tasks/",
        headers=headers,
        json={
            "title": TASK_TITLE,
            "payload": json.dumps({"data": "test"}),
            "priority": "low",
            "scheduled_at": 0  # Execute IMMEDIATELY
        }
    )
    
    if test_response.status_code == 404:
        print(f"✗ Task file '{TASK_TITLE}.py' not found!")
        print(f"   Please upload the task file first using:")
        print(f"   POST {API_URL}/tasks/upload_file?file_name={TASK_TITLE}")
        sys.exit(1)
    elif test_response.status_code in [200, 201]:
        print(f"✓ Task file exists and is ready")
        # Delete the test task
        test_task_id = test_response.json().get("id")
        if test_task_id:
            requests.delete(f"{API_URL}/tasks/{test_task_id}", headers=headers)
    else:
        print(f"Unexpected response: {test_response.status_code}")

    # 4. CREATE 200 TASKS
    print(f"\n[4/4] Creating {NUM_TASKS} tasks with title '{TASK_TITLE}'...")
    print(f"Each task will perform intensive computation (30-60 seconds)")
    print(f"This should trigger worker autoscaling!")
    print(f"\nProgress: ", end="", flush=True)
    
    start_time = time.time()
    success_count = 0
    failed_count = 0
    
    for i in range(NUM_TASKS):
        payload = generate_random_payload()
        
        resp = requests.post(
            f"{API_URL}/tasks/",
            headers=headers,
            json={
                "title": TASK_TITLE,
                "payload": json.dumps({"data": payload}),
                "priority": "low",  # All tasks low priority
                "scheduled_at": 0  # Execute IMMEDIATELY (was 1)
            }
        )
        
        if resp.status_code in [200, 201]:
            print("✓", end="", flush=True)
            success_count += 1
        else:
            print("✗", end="", flush=True)
            failed_count += 1
            if failed_count == 1:
                print(f"\nFirst error: {resp.status_code} - {resp.text[:150]}")
                print("Continuing... ", end="", flush=True)
        
        # Small delay to avoid overwhelming the API
        if (i + 1) % 50 == 0:
            print(f" [{i+1}/{NUM_TASKS}]", end="", flush=True)
        
        time.sleep(0.02)
    
    elapsed_time = time.time() - start_time
    
    print(f"\n\n=== Test Complete ===")
    print(f"✓ Successfully created: {success_count}/{NUM_TASKS} tasks")
    if failed_count > 0:
        print(f"✗ Failed: {failed_count}/{NUM_TASKS} tasks")
    print(f"Time taken: {elapsed_time:.2f} seconds")
    print(f"\nNow monitor worker autoscaling:")
    print(f"   kubectl get pods -n taskflow -l app=worker -w")
    print(f"   kubectl get hpa -n taskflow -w")
    print(f"\nExpected behavior:")
    print(f"   • Workers should scale from 2 → 10+ pods")
    print(f"   • Queue length should build up in Redis")
    print(f"   • Tasks will take 30-60 seconds each to complete")

if __name__ == "__main__":
    try:
        run_autoscale_test()
    except requests.exceptions.ConnectionError:
        print(f"\n✗ Could not connect to {API_URL}")
        print(f"   Make sure port-forwarding is active:")
        print(f"   kubectl port-forward -n taskflow svc/taskflow-api 8080:80")
        sys.exit(1)
    except KeyboardInterrupt:
        print(f"\n\n⚠ Test interrupted by user")
        sys.exit(1)
