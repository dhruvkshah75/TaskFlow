import logging
import uuid
import json
import signal
import asyncio
import os

# Core imports
from core.redis_client import get_async_redis_client
from .heartbeat import HeartbeatService
from .task_handler import execute_dynamic_task
# Import the updated database helper that supports worker_id
from .utils import update_task_status 

# Ensure logs directory exists
os.makedirs("logs", exist_ok=True)

# Logging configuration matches your Victus environment
logging.basicConfig(
    level=logging.INFO, 
    format='%(asctime)s - [Worker] - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("logs/worker.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

QUEUE_NAME = "default"
PROCESSING_QUEUE = f"processing:{QUEUE_NAME}"

class AsyncWorker:
    def __init__(self):
        # Generate a unique short ID for this worker instance
        self.worker_id = str(uuid.uuid4())[:8]
        self.running = True
        self.redis_high = None
        self.redis_low = None
        self.heartbeat = HeartbeatService(self.worker_id)

    async def start(self):
        logger.info(f"Async worker:{self.worker_id} starting up on TaskFlow cluster...")
        
        self.redis_high = await get_async_redis_client("high")
        self.redis_low = await get_async_redis_client("low")
        
        # Start the heartbeat so the Leader knows this worker is alive
        await self.heartbeat.start()

        logger.info(f"Worker:{self.worker_id} listening for tasks on Redis.")
        
        while self.running:
            try:
                raw_data = None
                # Atomically move task from main queue to processing queue
                raw_data = await self.redis_high.brpoplpush(QUEUE_NAME, PROCESSING_QUEUE, 1)
                
                if not raw_data:
                    raw_data = await self.redis_low.brpoplpush(QUEUE_NAME, PROCESSING_QUEUE, 1)

                if raw_data:
                    try:
                        data = json.loads(raw_data)
                    except json.JSONDecodeError:
                        logger.error(f"Worker:{self.worker_id} failed to decode JSON")
                        await self._cleanup_malformed(raw_data)
                        continue

                    task_id = data.get('task_id')
                    task_title = data.get('title')
                    payload = data.get('payload') 

                    logger.info(f"Worker:{self.worker_id} claiming Task: {task_id}")

                    try:
                        # --- THE CRITICAL FIX ---
                        # Pass self.worker_id so the Leader's PEL scanner sees this task is claimed
                        await update_task_status(task_id, "IN_PROGRESS", self.worker_id)

                        # Execute the dynamically loaded script
                        result = await execute_dynamic_task(task_title, payload)
                        
                        logger.info(f"Task {task_id} COMPLETED successfully.")
                        await update_task_status(task_id, "COMPLETED")
                        
                    except Exception as e:
                        logger.error(f"Execution failed for Task {task_id}: {str(e)}")
                        # Mark as failed in DB
                        await update_task_status(task_id, "FAILED")
                    
                    finally:
                        # Task is finished (success or fail), remove from processing queue
                        await self._remove_from_processing(raw_data)

            except Exception as e:
                if self.running:
                    logger.error(f"Worker {self.worker_id} Loop Error: {e}")
                    await asyncio.sleep(2)

        # Shutdown Logic
        logger.info(f"Worker:{self.worker_id} gracefully shutting down...")
        await self.heartbeat.stop()
        if self.redis_low: await self.redis_low.aclose()
        if self.redis_high: await self.redis_high.aclose()

    async def _remove_from_processing(self, raw_data):
        """Clean up the processing queue in both Redis instances"""
        try:
            await self.redis_low.lrem(PROCESSING_QUEUE, 0, raw_data)
            await self.redis_high.lrem(PROCESSING_QUEUE, 0, raw_data)
        except Exception:
            logger.exception("Failed to remove item from processing queue")

    async def _cleanup_malformed(self, raw_data):
        """Remove messages that cannot be parsed as JSON"""
        try:
            await self.redis_low.lrem(PROCESSING_QUEUE, 0, raw_data)
            await self.redis_high.lrem(PROCESSING_QUEUE, 0, raw_data)
        except Exception:
            logger.exception("Failed to remove malformed message")

    def request_shutdown(self):
        self.running = False

async def main():
    worker = AsyncWorker()
    loop = asyncio.get_running_loop()
    # Handle OS signals for clean shutdown in Kubernetes
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, worker.request_shutdown)
    await worker.start()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass