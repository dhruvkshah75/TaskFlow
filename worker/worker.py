import os, uuid, asyncio
from worker.heartbeat import send_heartbeat
from core.redis_client import redis_client
from core import models
from core.database import SessionLocal

# assigning a unique worker id using uuid
worker_id = os.getenv("WORKER_ID", f"worker-{os.getpid()}-{uuid.uuid4()}")

async def process_task(task_data):
    pass
    # after doing the task we update the data in the DB 
    # where the status is made to COMPLETED 


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
                task.status = 'ASSIGNED'
                task.worker_id = worker_id
                db.commit()
                await process_task(task)
            else:
                pass
        else:
            # No task, sleep briefly before polling again
            await asyncio.sleep(1)



async def main_worker():
    # Starting the heartbeat in the background
    asyncio.create_task(send_heartbeat(worker_id))

    await worker_loop()


