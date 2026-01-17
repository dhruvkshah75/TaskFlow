from sqlalchemy import create_all, update
from core.database import SessionLocal # Adjust based on your path
from core.models import Tasks 

async def update_task_status(task_id: int, status: str, result: str = None):
    async with SessionLocal() as session:
        query = update(Tasks).where(Tasks.id == task_id).values(
            status=status,
            result=result
        )
        await session.execute(query)
        await session.commit()