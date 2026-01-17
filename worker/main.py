import logging
import uuid
import json
import signal
import asyncio
import os
import sys

# Core imports
from core.redis_client import get_async_redis_client
from .heartbeat import HeartbeatService
from .task_handler import execute_dynamic_task
# Import the new database helper
from .utils import update_task_status 

# Ensure logs directory exists
os.makedirs("logs", exist_ok=True)

# Logging matches your Victus environment
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
        self.worker_id = str(uuid.uuid4())[:8]
        self.running = True
        self.redis_high = None
        self.redis_low = None
        self.heartbeat = HeartbeatService(self.worker_id)

    async def start(self):
        logger.info(f"Async worker:{self.worker_id} starting up on modular-worker branch...")
        
        self.redis_high = await get_async_redis_client("high")
        self.redis_low = await get_async_redis_client("low")
        await self.heartbeat.start()

        logger.info(f"Worker:{self.worker_id} listening for dynamic tasks on Redis.")
        
        while self.running:
            try:
                raw_data = None
                # Priority-based Redis polling
                if hasattr(self.redis_high, 'blmove'):
                    raw_data = await self.redis_high.blmove(QUEUE_NAME, PROCESSING_QUEUE, 'RIGHT', 'LEFT', 1)
                else:
                    raw_data = await self.redis_high.brpoplpush(QUEUE_NAME, PROCESSING_QUEUE, 1)
                
                if not raw_data:
                    if hasattr(self.redis_low, 'blmove'):
                        raw_data = await self.redis_low.blmove(QUEUE_NAME, PROCESSING_QUEUE, 'RIGHT', 'LEFT', 1)
                    else:
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
                    payload = data.get('payload') # The JSONB salted dictionary

                    logger.info(f"Worker:{self.worker_id} processing Dynamic Task: {task_id}")

                    try:
                        # 1. UPDATE DB: Mark as starting
                        await update_task_status(task_id, "IN_PROGRESS")

                        # 2. EXECUTE: Load and run the uploaded script
                        result = await execute_dynamic_task(task_title, payload)
                        
                        logger.info(f"Task {task_id} COMPLETED successfully.")
                        
                        # 3. UPDATE DB: Mark as success with result
                        await update_task_status(task_id, "COMPLETED", result=json.dumps(result))
                        
                    except Exception as e:
                        logger.error(f"Execution failed for Task {task_id}: {str(e)}")
                        
                        # 4. UPDATE DB: Mark as failed with error message
                        await update_task_status(task_id, "FAILED", result=str(e))
                    
                    finally:
                        await self._remove_from_processing(raw_data)

            except Exception as e:
                if self.running:
                    logger.error(f"Worker {self.worker_id} Loop Error: {e}")
                    await asyncio.sleep(2)

        # Shutdown Logic
        logger.info(f"Worker:{self.worker_id} shutting down...")
        await self.heartbeat.stop()
        if self.redis_low: await self.redis_low.aclose()
        if self.redis_high: await self.redis_high.aclose()

    async def _remove_from_processing(self, raw_data):
        try:
            await self.redis_low.lrem(PROCESSING_QUEUE, 0, raw_data)
            await self.redis_high.lrem(PROCESSING_QUEUE, 0, raw_data)
        except Exception:
            logger.exception("Failed to remove item from processing queue")

    async def _cleanup_malformed(self, raw_data):
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
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, worker.request_shutdown)
    await worker.start()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass