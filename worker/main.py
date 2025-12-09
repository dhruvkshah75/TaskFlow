import logging, uuid, json, signal, asyncio
from core.redis_client import get_async_redis_client
from .heartbeat import HeartbeatService
from .task_handler import TaskHandler


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

class AsyncWorker:

    def __init__(self):
        self.worker_id = str(uuid.uuid4())[:8]
        self.running = True
        self.redis = None 
        self.handler = TaskHandler(self.worker_id)
        self.heartbeat = HeartbeatService(self.worker_id)

    async def start(self):
        logger.info(f"Async worker:{self.worker_id} started up...")
        # Connect to the redis low i.e. Task Queue
        self.redis = await get_async_redis_client("low")

        await self.heartbeat.start()

        logger.info(f"Worker:{self.worker_id} listening on queue.")
        while self.running:
            try:
                # brpop is async
                #Timeout allows loop to check self.running periodically.
                result = await self.redis.brpop(QUEUE_NAME, timeout=1.0)
                if result:
                    queue, raw_data = result
                    if raw_data:
                        try:
                            data = json.loads(raw_data)
                            logger.info(f"Worker:{self.worker_id} recieved Task: {data.get('task_id')}")

                            await self.handler.handle_task(data)

                        except json.JSONDecodeError:
                            logger.error(f"worker:{self.worker_id} failed to decode to json")
            except Exception as e:
                # Prevent CPU spin if Redis connection drops
                if self.running:
                    logger.error(f"Worker {self.worker_id} Loop Error: {e}")
                    await asyncio.sleep(2)

        logger.info(f"Worker:{self.worker_id} shutting down ..")
        await self.heartbeat.stop()
        await self.redis.close()

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