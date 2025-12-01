import os, uuid, asyncio
from worker.heartbeat import send_heartbeat
from core.redis_client import redis_client
from core import models
from core.database import SessionLocal

# assigning a unique worker id using uuid
worker_id = os.getenv("WORKER_ID", f"worker-{os.getpid()}-{uuid.uuid4()}")

async def process_task(task_data):
    print(f"Processing task {task_data.id}")
    # Simulate some work based on task data
    await asyncio.sleep(5)
    print(f"Task {task_data.id} processed")


async def worker_loop():
    while True:
        db = SessionLocal()
        # we try to get the task from redis_client
        task_id = redis_client.lpop("task_queue")

        if task_id:
            task = db.query(models.Tasks).filter(
                models.Tasks.id == task_id
            ).first()

            if task and task.status == 'PENDING':
                task.status = 'IN_PROGRESS'
                task.worker_id = worker_id
                db.commit()
                await process_task(task)
                task.status = 'COMPLETED'
                db.commit()
            else:
                pass
        else:
            # No task, sleep briefly before polling again
            await asyncio.sleep(1)



async def main_worker():
    # Starting the heartbeat in the background
    asyncio.create_task(send_heartbeat(worker_id))

    await worker_loop()


