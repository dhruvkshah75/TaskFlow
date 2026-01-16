import logging, uuid, json, signal, asyncio, os
from core.redis_client import get_async_redis_client
from .heartbeat import HeartbeatService
from .task_handler import TaskHandler

# Ensure logs directory exists
os.makedirs("logs", exist_ok=True)

logging.basicConfig(
    level=logging.INFO, 
    format='%(asctime)s - [Worker] - %(levelname)s - %(message)s',
        handlers=[
        logging.FileHandler("logs/worker.log"), # Writes to the file
        logging.StreamHandler()                 # Writes to the terminal
    ]
)
logger = logging.getLogger(__name__)

QUEUE_NAME = "default"
PROCESSING_QUEUE = f"processing:{QUEUE_NAME}"

class AsyncWorker:

    def __init__(self):
        self.worker_id = str(uuid.uuid4())[:8]
        self.running = True
        self.redis = None 
        self.handler = TaskHandler(self.worker_id)
        self.heartbeat = HeartbeatService(self.worker_id)

    async def start(self):
        logger.info(f"Async worker:{self.worker_id} started up...")
        # Connect to both high and low priority redis instances
        self.redis_high = await get_async_redis_client("high")
        self.redis_low = await get_async_redis_client("low")

        await self.heartbeat.start()

        logger.info(f"Worker:{self.worker_id} listening on queue.")
        while self.running:
            try:
                # Atomically move an item from the queue to a processing queue.
                # Try high priority queue first, then fall back to low priority.
                # Prefer BLMOVE (atomic blocking move) when available. Fall back to
                # BRPOPLPUSH for older Redis versions / clients.
                raw_data = None
                try:
                    # Try high priority queue first (with short timeout)
                    if hasattr(self.redis_high, 'blmove'):
                        try:
                            raw_data = await self.redis_high.blmove(QUEUE_NAME, PROCESSING_QUEUE, 'RIGHT', 'LEFT', 1)
                        except Exception as e:
                            logger.debug(f"blmove on high failed ({e}), falling back to brpoplpush")
                            raw_data = await self.redis_high.brpoplpush(QUEUE_NAME, PROCESSING_QUEUE, 1)
                    else:
                        raw_data = await self.redis_high.brpoplpush(QUEUE_NAME, PROCESSING_QUEUE, 1)
                    
                    # If no task from high priority queue, try low priority queue
                    if not raw_data:
                        if hasattr(self.redis_low, 'blmove'):
                            try:
                                raw_data = await self.redis_low.blmove(QUEUE_NAME, PROCESSING_QUEUE, 'RIGHT', 'LEFT', 1)
                            except Exception as e:
                                logger.debug(f"blmove on low failed ({e}), falling back to brpoplpush")
                                raw_data = await self.redis_low.brpoplpush(QUEUE_NAME, PROCESSING_QUEUE, 1)
                        else:
                            raw_data = await self.redis_low.brpoplpush(QUEUE_NAME, PROCESSING_QUEUE, 1)

                    if raw_data:
                        try:
                            data = json.loads(raw_data)
                        except json.JSONDecodeError:
                            logger.error(f"worker:{self.worker_id} failed to decode to json")
                            # remove the malformed message from processing queue (try both redis instances)
                            try:
                                await self.redis_low.lrem(PROCESSING_QUEUE, 0, raw_data)
                                await self.redis_high.lrem(PROCESSING_QUEUE, 0, raw_data)
                            except Exception:
                                logger.exception("Failed to remove malformed message from processing queue")
                            continue

                        logger.info(f"Worker:{self.worker_id} received Task: {data.get('task_id')}")

                        try:
                            await self.handler.handle_task(data)
                        except Exception:
                            logger.exception("Handler raised during processing")
                        finally:
                            # Always attempt to remove the message from the processing
                            # queue once handler.run returns (success or failure).
                            try:
                                if raw_data:
                                    await self.redis_low.lrem(PROCESSING_QUEUE, 0, raw_data)
                                    await self.redis_high.lrem(PROCESSING_QUEUE, 0, raw_data)
                            except Exception:
                                logger.exception("Failed to remove item from processing queue in finally")
                except Exception as e:
                    # Prevent CPU spin if Redis connection drops
                    if self.running:
                        logger.error(f"Worker {self.worker_id} Loop Error: {e}")
                        await asyncio.sleep(2)
            except Exception as e:
                # Prevent CPU spin if Redis connection drops
                if self.running:
                    logger.error(f"Worker {self.worker_id} Loop Error: {e}")
                    await asyncio.sleep(2)

        logger.info(f"Worker:{self.worker_id} shutting down ..")
        await self.heartbeat.stop()
        await self.redis_low.aclose()
        await self.redis_high.aclose()

    def request_shutdown(self):
        logger.info("Shutdown signal received.")
        self.running = False

async def main():
    worker = AsyncWorker()
    # Handle Signals for graceful shutdown
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, worker.request_shutdown)

    await worker.start()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass