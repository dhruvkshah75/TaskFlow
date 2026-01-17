import time
import psycopg2
import sys
from datetime import datetime, timedelta

# --- CONFIGURATION ---
# Must match NUM_TASKS in autoscale-test.py
EXPECTED_TASKS = 200

# Timeout (600s = 10 minutes for autoscaling test)
TIMEOUT_SECONDS = 600

# Database connection matches the 'kubectl port-forward'
DB_CONFIG = {
    "dbname": "taskflow_db",
    "user": "postgres",
    "password": "password",
    "host": "localhost",
    "port": "6432"
}

def get_task_status_counts(cursor):
    """
    Get counts of tasks by status created in the last 30 minutes.
    """
    try:
        query = """
            SELECT status, COUNT(*) 
            FROM tasks 
            WHERE created_at > (NOW() - INTERVAL '30 minutes')
            GROUP BY status;
        """
        cursor.execute(query)
        results = cursor.fetchall()
        
        status_dict = {status: count for status, count in results}
        return status_dict
    except Exception as e:
        print(f"   [Warning] DB Query failed: {e}")
        return {}

def get_recent_completed_count(cursor):
    """
    Queries the DB for tasks completed that were created in the last 30 minutes.
    """
    try:
        query = """
            SELECT COUNT(*) 
            FROM tasks 
            WHERE status = 'COMPLETED' 
            AND created_at > (NOW() - INTERVAL '30 minutes');
        """
        cursor.execute(query)
        result = cursor.fetchone()
        return result[0] if result else 0
    except Exception as e:
        print(f"   [Warning] DB Query failed: {e}")
        return 0

def verify_autoscaling_tasks():
    """
    Verify that autoscaling test completes all tasks.
    Monitors task completion and reports progress.
    """
    print(f"=" * 60)
    print(f"AUTOSCALING VERIFICATION")
    print(f"=" * 60)
    print(f"Waiting for {EXPECTED_TASKS} tasks to complete...")
    print(f"Timeout: {TIMEOUT_SECONDS}s ({TIMEOUT_SECONDS//60} minutes)")
    print(f"=" * 60)
    
    start_time = time.time()
    last_report_time = start_time
    
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
                
                # Show final status
                status_counts = get_task_status_counts(cur)
                print(f"\n   Final Status:")
                for status, count in status_counts.items():
                    print(f"     {status}: {count}")
                
                cur.close()
                conn.close()
                sys.exit(1)

            # 2. Check the Count
            completed_count = get_recent_completed_count(cur)
            
            # Get all status counts for detailed progress
            status_counts = get_task_status_counts(cur)
            
            # Print progress every 10 seconds with detailed info
            if elapsed - last_report_time >= 10:
                print(f"\n[{elapsed}s] Progress Report:")
                print(f"Completed: {completed_count}/{EXPECTED_TASKS}")
                for status, count in status_counts.items():
                    if status != 'COMPLETED':
                        print(f"{status}: {count}")
                last_report_time = elapsed
            else:
                # Update progress on same line
                sys.stdout.write(f"\rProgress: {completed_count}/{EXPECTED_TASKS} completed ({elapsed}s elapsed)   ")
                sys.stdout.flush()

            # 3. Success Condition
            if completed_count >= EXPECTED_TASKS:
                print(f"\n\n{'=' * 60}")
                print(f"SUCCESS!")
                print(f"{'=' * 60}")
                print(f"Completed {completed_count} tasks in {elapsed} seconds")
                print(f"Average time per task: {elapsed/completed_count:.2f}s")
                print(f"{'=' * 60}")
                
                cur.close()
                conn.close()
                sys.exit(0)
            
            # Poll every 3 seconds
            time.sleep(3)

    except psycopg2.OperationalError:
        print("\n\nConnection Failed: Is the PgBouncer Port Forward running?")
        print("   Make sure 'kubectl port-forward -n taskflow svc/taskflow-pgbouncer 6432:6432' is active.")
        sys.exit(1)
    except Exception as e:
        print(f"\n\nCRITICAL ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    verify_autoscaling_tasks()
