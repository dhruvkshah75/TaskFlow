# scripts/janitor.py

from sqlalchemy.orm import Session
from sqlalchemy import or_, and_
from datetime import datetime, timedelta, timezone

from core.database import SessionLocal
from core import models

def cleanup_inactive_keys():
    """
    Deactivates API keys that haven't been used in the last 30 days.
    Also handles keys that were created > 30 days ago and NEVER used.
    """
    db = SessionLocal()
    try:
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=30)
        current_time = datetime.now(timezone.utc) 
        # Query for keys to deactivate
        # Logic for deactivating keys:
        # 1. Must be currently Active (is_active = True)
        # 2. If the key has expired 
        # 3. AND EITHER:
        #    a. last_used_at is older than cutoff
        #    b. last_used_at is NULL (never used) AND created_at is older than cutoff
        
        keys_to_deactivate = db.query(models.ApiKey).filter(
            models.ApiKey.is_active == True,
            or_(
                models.ApiKey.last_used_at < cutoff_date,
                and_(
                    models.ApiKey.last_used_at.is_(None),
                    models.ApiKey.created_at < cutoff_date,
                )
            )
        ).all()

        if not keys_to_deactivate:
            print("No stale keys found. System clean.")
            return

        # Deactivate them
        for key in keys_to_deactivate:
            key.is_active = False
            key.deactivated_at = datetime.now(timezone.utc)

        db.commit()

    except Exception as e:
        print(f"Error during cleanup: {e}")
        db.rollback()
    finally:
        db.close()




def delete_old_inactive_keys():
    db = SessionLocal()

    try:
        threshold = datetime.now(timezone.utc) - timedelta(days=30)
        keys_to_delete = db.query(models.ApiKey).filter(
            models.ApiKey.is_active == False,
            models.ApiKey.deactivated_at < threshold
        ).all()

        for key in keys_to_delete:
            db.delete(key)

        db.commit()
        
        if keys_to_delete != None:
            print(f"Deleted {len(keys_to_delete)} old inactive API keys.")
    except Exception as e:
        print(f"Error while deleting old keys: {e}")
        db.rollback()
    finally:
        db.close()
    


# we will call this function in our docker file while creating a container 
if __name__ == "__main__":
    cleanup_inactive_keys()
    delete_old_inactive_keys()