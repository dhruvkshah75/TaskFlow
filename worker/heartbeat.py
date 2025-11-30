import time 
from core.redis_client import redis_client
from core.config import settings 
from datetime import datetime, timezone

def send_heartbeat(worker_id):
    while True:
        heartbeat_key = f"worker:{worker_id}:heartbeat"
        key_value = datetime.now(timezone.utc).isoformat()

        redis_client.set(heartbeat_key, key_value)
        redis_client.expire(heartbeat_key, settings.HEARTBEAT_INTERVAL_SECONDS * 2)


        time.sleep(settings.HEARTBEAT_INTERVAL_SECONDS)