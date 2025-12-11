import asyncio, logging, os
from core.redis_client import get_async_redis_client

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

class HeartbeatService:
    def __init__(self, worker_id: str, ttl_seconds: int=10, interval: int = 3):
        self.worker_id = worker_id
        self.ttl_seconds = ttl_seconds
        self.interval = interval
        self.running = True
        self._task = None

    async def start(self):
        """ Starts the background hearbeat loop """
        self.redis = await get_async_redis_client("high")
        self._task = asyncio.create_task(self._loop())

    async def _loop(self):
        logger.info(f"Started the heartbeat of the worker:{self.worker_id} asyncronously")
        key = f"worker:{self.worker_id}:heartbeat"

        while self.running:
            try:
                await self.redis.set(key, "alive" ,ex=self.ttl_seconds)
            except Exception as e:
                logger.error(f"Heartbeat failed: {e}")

            await asyncio.sleep(self.interval)

    async def stop(self):
        """ Stops the heartbeat of the worker and closes the redis connection """
        self.running = False
        if self._task:
            await self._task  # wait for the task loop to get over 
        else:
            await self.redis.close()
        logger.info(f"Heartbeat of worker:{self.worker_id} stopped")