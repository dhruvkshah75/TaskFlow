import time
import psycopg2
import sys
from datetime import datetime, timedelta

# --- CONFIGURATION ---
# Must match NUM_TASKS in integration_test.py
EXPECTED_TASKS = 20 

# Timeout (300s = 5 minutes)
TIMEOUT_SECONDS = 300

# Database connection matches the 'kubectl port-forward'
DB_CONFIG = {
    "dbname": "taskflow_db",
    "user": "postgres",
    "password": "password",
    "host": "localhost",
    "port": "6432"
}

def get_recent_completed_count(cursor):
    """
    Queries the DB for tasks completed that were created in the last 15 minutes.
    This prevents counting old tasks from previous test runs.
    """
    try:
        # Assuming your tasks table has a 'created_at' timestamp column.
        # If not, remove the "AND created_at..." part.
        query = """
            SELECT COUNT(*) 
            FROM tasks 
            WHERE status = 'COMPLETED' 
            AND created_at > (NOW() - INTERVAL '15 minutes');
        """
        cursor.execute(query)
        result = cursor.fetchone()
        return result[0] if result else 0
    except Exception as e:
        print(f"   [Warning] DB Query failed: {e}")
        return 0

def verify_tasks():
    print(f"Waiting for {EXPECTED_TASKS} RECENT tasks to complete (Timeout: {TIMEOUT_SECONDS}s)...")
    
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
            count = get_recent_completed_count(cur)
            
            # Print progress bar effect on the same line
            sys.stdout.write(f"\rCurrent Status: {count}/{EXPECTED_TASKS} tasks completed ({elapsed}s elapsed)")
            sys.stdout.flush()

            # 3. Success Condition
            if count >= EXPECTED_TASKS:
                print(f"\n\nSUCCESS: Found {count} completed tasks in {elapsed} seconds!")
                break
            
            # Poll every 2 seconds
            time.sleep(2)

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