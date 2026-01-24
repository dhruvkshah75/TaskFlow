from sqlalchemy import update
from core.database import SessionLocal
from core.models import Tasks 


def update_task_status_sync(task_id: int, status: str, worker_id: str = None):
    session = SessionLocal()
    try:
        # Update both status AND worker_id
        update_values = {"status": status}
        if worker_id:
            update_values["worker_id"] = worker_id
            
        query = update(Tasks).where(Tasks.id == task_id).values(**update_values)
        session.execute(query)
        session.commit()
    finally:
        session.close()

async def update_task_status(task_id: int, status: str, worker_id: str = None):
    import asyncio
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, update_task_status_sync, task_id, status, worker_id)  