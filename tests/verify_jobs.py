import time
import psycopg2
import sys

# --- CONFIGURATION ---
EXPECTED_TASKS = 200
# 12 Minutes (720s) to allow for processing + buffer
TIMEOUT_SECONDS = 720 

# Database connection matches the 'kubectl port-forward' in your CI
# Connects to PgBouncer (connection pooler) on port 6432
DB_CONFIG = {
    "dbname": "taskflow_db",
    "user": "postgres",
    "password": "password",
    "host": "localhost",
    "port": "6432"
}

def get_completed_count(cursor):
    """Queries the DB for the count of completed tasks."""
    try:
        cursor.execute("SELECT COUNT(*) FROM tasks WHERE status = 'COMPLETED';")
        result = cursor.fetchone()
        return result[0] if result else 0
    except Exception as e:
        print(f"   [Warning] DB Query failed: {e}")
        return 0

def verify_tasks():
    print(f"Waiting for {EXPECTED_TASKS} tasks to complete (Timeout: {TIMEOUT_SECONDS}s)...")
    
    start_time = time.time()
    
    try:
        # Connect to the database
        conn = psycopg2.connect(**DB_CONFIG)
        cur = conn.cursor()
        
        while True:
            elapsed = int(time.time() - start_time)
            
            # 1. Check for Timeout
            if elapsed > TIMEOUT_SECONDS:
                print(f"\n\nTIMEOUT: Stopped after {elapsed}s.")
                print("   Workers were too slow or crashed.")
                sys.exit(1)

            # 2. Check the Count
            count = get_completed_count(cur)
            
            # Print progress bar effect on the same line
            sys.stdout.write(f"\rCurrent Status: {count}/{EXPECTED_TASKS} tasks completed ({elapsed}s elapsed)")
            sys.stdout.flush()

            # 3. Success Condition
            if count == EXPECTED_TASKS:
                print(f"\n\nSUCCESS: All {EXPECTED_TASKS} tasks finished in {elapsed} seconds!")
                break
            
            # 4. Failure Condition (Data Integrity Error)
            if count > EXPECTED_TASKS:
                print(f"\n\nFAILURE: Found {count} completed tasks (Expected exactly {EXPECTED_TASKS}).")
                print("   This might mean tasks are being processed twice.")
                sys.exit(1)

            # Poll every 5 seconds
            time.sleep(5)

        cur.close()
        conn.close()
        sys.exit(0)

    except psycopg2.OperationalError:
        print("\n\nConnection Failed: Is the PgBouncer Port Forward running?")
        print("   Make sure 'kubectl port-forward -n taskflow svc/taskflow-pgbouncer 6432:6432' is active.")
        sys.exit(1)
    except Exception as e:
        print(f"\n\nCRITICAL ERROR: {e}")
        sys.exit(1)

if __name__ == "__main__":
    verify_tasks()