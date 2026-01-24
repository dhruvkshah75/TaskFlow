import uuid, logging, json, threading, time, signal
from .redis_client import get_redis, get_redis_client
from datetime import timezone, datetime
from .database import SessionLocal
from .models import Tasks, TaskStatus 

# Configuration
LEADER_KEY = "taskflow:leader"
LEASE_TTL_MS = 10000      
RENEW_INTERVAL_S = 3      
SCHEDULER_INTERVAL_S = 5  
RECLAIM_INTERVAL_S = 10   
MAX_RETRIES = 3
PROCESSING_QUEUE_PREFIX = "processing"
PROCESSING_RECLAIM_S = 30  

import os
os.makedirs("logs", exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - [QueueManager] - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("logs/queue_manager.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

RENEW_SCRIPT = """
if redis.call("get", KEYS[1]) == ARGV[1] then
    return redis.call("pexpire", KEYS[1], ARGV[2])
else
    return 0
end
"""

def push_task(queue_name: str, message: dict, priority: str = "low") -> bool:
    """Pushes task with full payload to ensure workers can execute immediately."""
    try:
        r = get_redis_client(priority)
        json_message = json.dumps(message)
        r.rpush(queue_name, json_message)
        length = r.llen(queue_name)
        logger.debug(f"Pushed task {message.get('task_id')} to {queue_name} (len={length})")
        return True
    except Exception as e:
        logger.error(f"Error pushing to {priority} Redis: {e}")
        return False

class QueueManager:
    def __init__(self):
        self.instance_id = str(uuid.uuid4())
        self.redis = get_redis()
        self.running = True
        self.is_leader = False
        self.renew = self.redis.register_script(RENEW_SCRIPT)
        signal.signal(signal.SIGTERM, self.shutdown)
        signal.signal(signal.SIGINT, self.shutdown)

    def shutdown(self, signum, frame):
        logger.info("Shutting down QueueManager...")
        self.running = False
        if self.is_leader:
            try:
                if self.redis.get(LEADER_KEY) == self.instance_id:
                    self.redis.delete(LEADER_KEY)
            except Exception as e:
                logger.error(f"Error releasing lock: {e}")

    # Leadership Management
    """
    The leader has a hearbeat whhich it sends to the redis every ten seconds and if the 
    leader doesnt respond for a particular amount of time, then a new leader is elected
    """
    def try_aquire_leader(self) -> bool:
        """ Attempts to become leader using Redis SET NX """
        try:
            result = self.redis.set(LEADER_KEY, self.instance_id, nx=True, px=LEASE_TTL_MS)
            return bool(result)
        except Exception as e:
            logger.error(f"Error acquiring leadership: {e}")
            return False
        
    def renew_lease(self) -> bool:
        """ Attempts to extend the lease only if we own the lease """
        try:
            return bool(self.renew(keys=[LEADER_KEY], args=[self.instance_id, LEASE_TTL_MS]))
        except Exception as e:
            logger.error(f"Error renewing lease: {e}")
            return False
        
    def maintain_leadership(self):
        """ 
        Bakgoround loop that keeps running to maintain leadership.
        If the leader crashes then this will help to elect the new leader 
        """
        while self.running:
            if self.is_leader:
                if not self.renew_lease():
                    logger.info(f"Instance {self.instance_id} LOST leadership.")
                    self.is_leader = False
            else:
                if self.try_aquire_leader():
                    logger.info(f"Instance {self.instance_id} ACQUIRED leadership.")
                    self.is_leader = True
            time.sleep(RENEW_INTERVAL_S)

    # --- Task Logic Loops ---

    def scheduler_loop(self):
        """Claims PENDING tasks and pushes them to Redis using pipelines for performance."""
        while self.running:
            if not self.is_leader:
                time.sleep(SCHEDULER_INTERVAL_S)
                continue
            db = SessionLocal()
            try:
                now = datetime.now(timezone.utc)
                candidates = (
                    db.query(Tasks)
                    .filter(Tasks.status == TaskStatus.PENDING, Tasks.scheduled_at <= now)
                    .order_by(Tasks.scheduled_at.asc())
                    .limit(100).with_for_update(skip_locked=True).all()
                )
                
                if not candidates:
                    db.close()
                    time.sleep(SCHEDULER_INTERVAL_S)
                    continue

                queued_ids = []
                # Updated mapping for push_task logic in queue_manager.py
                for task in candidates:
                    task_title = str(task.title)
                    task_payload = task.payload if task.payload is not None else {}
                    logger.info(f"This is the task_title: {task.title} that we got from the database")
                    payload = {
                        "task_id": task.id,
                        "title": task_title,
                        "payload": task_payload
                    }
                    
                    priority = getattr(task, "priority", "low") or "low"
                    if push_task("default", payload, priority=priority):
                        queued_ids.append(task.id)

                if queued_ids:
                    db.query(Tasks).filter(Tasks.id.in_(queued_ids)).update(
                        {Tasks.status: TaskStatus.QUEUED, Tasks.updated_at: datetime.now(timezone.utc)},
                        synchronize_session=False
                    )
                    db.commit()
            except Exception as e:
                logger.error(f"Scheduler Error: {e}")
                db.rollback()
            finally:
                db.close()
            time.sleep(SCHEDULER_INTERVAL_S)

    def pel_scanner_loop(self):
        """Recovery mechanism that respects the worker startup window."""
        while self.running: 
            if self.is_leader:
                db = SessionLocal()
                try:
                    running_tasks = db.query(Tasks).filter(Tasks.status == TaskStatus.IN_PROGRESS).all()
                    for task in running_tasks:
                        # FIX: Wait for worker_id to be written to avoid race condition
                        if not task.worker_id: continue
                            
                        if not self.redis.exists(f"worker:{task.worker_id}:heartbeat"):
                            self._recover_task(db, task, f"Worker {task.worker_id} dead")
                    db.commit()
                except Exception as e:
                    logger.error(f"PEL Scanner Error: {e}")
                    db.rollback()
                finally:
                    db.close()  
            time.sleep(RECLAIM_INTERVAL_S)

    def _recover_task(self, db, task: Tasks, reason):
        """Re-queues task with script payload if retry limit not exceeded."""
        if task.retry_count < MAX_RETRIES:
            # FIX: Payload must include title/code for the worker
            payload = {"task_id": task.id, "title": task.title, "payload": task.payload}
            if push_task("default", payload, priority=getattr(task, "priority", "low")):
                task.status = TaskStatus.QUEUED
                task.worker_id = None
                task.retry_count += 1
                task.updated_at = datetime.now(timezone.utc)
        else:
            task.status = TaskStatus.FAILED
            task.updated_at = datetime.now(timezone.utc)


    def processing_reclaimer_loop(self):
        """Moves stale items from processing lists back to main queue."""
        low_redis = get_redis_client('low')
        p_queue = f"{PROCESSING_QUEUE_PREFIX}:default"
        while self.running:
            if not self.is_leader:
                time.sleep(RECLAIM_INTERVAL_S)
                continue
            try:
                items = low_redis.lrange(p_queue, 0, -1) or []
                for raw in items:
                    data = json.loads(raw)
                    db = SessionLocal()
                    task = db.query(Tasks).filter(Tasks.id == data.get('task_id')).first()
                    if task and task.status != TaskStatus.IN_PROGRESS:
                        low_redis.lrem(p_queue, 0, raw)
                        low_redis.lpush('default', raw)
                    db.close()
            except Exception as e:
                logger.error(f"Reclaimer Error: {e}")
            time.sleep(RECLAIM_INTERVAL_S)


    def queued_reconciliation_loop(self):
        """Fixes sync issues where DB says QUEUED but Redis is empty."""
        while self.running:
            if self.is_leader:
                db = SessionLocal()
                try:
                    queued = db.query(Tasks).filter(Tasks.status == TaskStatus.QUEUED).limit(100).all()
                    for t in queued:
                        push_task("default", {"task_id": t.id, "title": t.title, "payload": t.payload})
                finally:
                    db.close()
            time.sleep(30)


    def start(self): 
        logger.info(f"Queue Manager {self.instance_id} online.")
        t_list = [
            threading.Thread(target=self.maintain_leadership, daemon=True),
            threading.Thread(target=self.scheduler_loop, daemon=True),
            threading.Thread(target=self.pel_scanner_loop, daemon=True),
            threading.Thread(target=self.processing_reclaimer_loop, daemon=True),
            threading.Thread(target=self.queued_reconciliation_loop, daemon=True)
        ]
        for t in t_list: t.start()
        while self.running: time.sleep(1)

if __name__ == "__main__":
    QueueManager().start()