import uuid, logging, json, threading, time, signal
from .redis_client import get_redis, get_redis_client
from datetime import timezone, datetime
from .database import SessionLocal
from .models import Tasks, TaskStatus 

LEADER_KEY = "taskflow:leader"
LEASE_TTL_MS = 10000      # Leader lease time (10 seconds)
RENEW_INTERVAL_S = 3      # Try to renew every 3 seconds

SCHEDULER_INTERVAL_S = 5  # How often to check for scheduled tasks
RECLAIM_INTERVAL_S = 10   # How often to check for stuck tasks 
MAX_RETRIES = 3
PROCESSING_QUEUE_PREFIX = "processing"
PROCESSING_RECLAIM_S = 30  # Age (s) after which a processing item is considered stale

# Logger configuration
import os
os.makedirs("logs", exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - [QueueManager] - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("logs/queue_manager.log"), # Writes to the file
        logging.StreamHandler()                        # Writes to the terminal
    ]
)
logger = logging.getLogger(__name__)


# --- LUA SCRIPT FOR ATOMIC RENEWAL ---
# Returns 1 if successful (we still own the lock), 0 if lost
RENEW_SCRIPT = """
if redis.call("get", KEYS[1]) == ARGV[1] then
    return redis.call("pexpire", KEYS[1], ARGV[2])
else
    return 0
end
"""

# ================== CLIENT FUNCTIONS USED BY THE API & WORKER =====================================
def push_task(queue_name: str, message: dict, priority: str = "low") -> bool:
    """
    Pushes a task to the specific Redis instance based on priority.
    Returns True on success, False on failure.
    """
    try:
        r = get_redis_client(priority)
        json_message = json.dumps(message)
        r.rpush(queue_name, json_message)
        try:
            # logging the length of the queue 
            length = r.llen(queue_name)
            logger.debug(f"Pushed task {message.get('task_id')} to {queue_name} (len={length})")
        except Exception:
            # non-fatal, ignore if LLEN fails
            pass
        return True
    except Exception as e:
        logger.error(f"Error pushing to {priority} Redis: {e}")
        return False

# ===================== LEADER COORDINATOR =====================
class QueueManager:
    def __init__(self):
        """
        We use the High Priority Redis for coordination (locking) because 
        it is less likely to be clogged by bulk tasks.
        """
        self.instance_id = str(uuid.uuid4())
        self.redis = get_redis()
        self.running = True
        self.is_leader = False
        self.renew = self.redis.register_script(RENEW_SCRIPT)
        # Handle graceful shutdown (SIGTERM/SIGINT)
        signal.signal(signal.SIGTERM, self.shutdown)
        signal.signal(signal.SIGINT, self.shutdown)


    def shutdown(self, signum, frame):
        logger.info("Shutting down QueueManager...")
        self.running = False
        if self.is_leader:
            logger.info("Releasing leadership lock...")
            # Release lock so others can take over immediately
            try:
                if self.redis.get(LEADER_KEY) == self.instance_id:
                    self.redis.delete(LEADER_KEY)
            except Exception as e:
                logger.error(f"Error releasing lock: {e}")
    

    # ============== LEADER ELECTION MECHANISM =============
    """
    The leader has a hearbeat whhich it sends to the redis every ten seconds and if the 
    leader doesnt respond for a particular amount of time, then a new leader is elected
    """

    def try_aquire_leader(self) -> bool:
        """ Attempts to become leader using Redis SET NX """
        try:
            result = self.redis.set(LEADER_KEY, self.instance_id, 
                                    nx=True, px=LEASE_TTL_MS)
            return bool(result)
        except Exception as e:
            logger.error(f"Error aquiring the leader: {e}")
            return False
        
    def renew_lease(self) -> bool:
        """ Attempts to extend the lease only if we own the lease """
        try:
            result = self.renew(keys=[LEADER_KEY], 
                                args=[self.instance_id, LEASE_TTL_MS])
            return bool(result)
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
            # Sleep less than the TTL to ensure we renew in time
            time.sleep(RENEW_INTERVAL_S)
        

    # ===================== LOOPS RUN ONLY BY THE LEADER =======================
    def queued_reconciliation_loop(self):
        """
        Recovery mechanism for tasks marked as QUEUED in DB but missing from Redis.
        This can happen if Redis was down when tasks were being queued.
        Runs less frequently than scheduler to avoid overhead.
        """
        logger.info("Queued reconciliation loop started.")
        while self.running:
            if not self.is_leader:
                time.sleep(30)  # Check every 30 seconds when not leader
                continue
            
            db = SessionLocal()
            try:
                # Find tasks that are marked QUEUED in DB
                queued_tasks = (
                    db.query(Tasks)
                    .filter(Tasks.status == TaskStatus.QUEUED)
                    .limit(100)
                    .all()
                )
                
                if queued_tasks:
                    logger.info(f"Reconciling {len(queued_tasks)} QUEUED tasks with Redis")
                    requeued_count = 0
                    
                    for task in queued_tasks:
                        payload = {"task_id": task.id}
                        priority = getattr(task, "priority", "low") or "low"
                        
                        # Try to push to Redis
                        success = push_task("default", payload, priority=priority)
                        if success:
                            requeued_count += 1
                        else:
                            logger.error(f"Failed to reconcile task {task.id} to Redis")
                    
                    if requeued_count > 0:
                        logger.info(f"Successfully reconciled {requeued_count} tasks to Redis")
                
                db.close()
            except Exception as e:
                logger.error(f"Error in queued reconciliation: {e}")
                try:
                    db.rollback()
                    db.close()
                except Exception:
                    pass
            
            time.sleep(30)  # Run every 30 seconds
        logger.info("Queued reconciliation loop stopped.")

    def scheduler_loop(self):
        """
        Efficient scheduler:
        - Uses index (status, scheduled_at) by ordering on scheduled_at
        - Claims rows with FOR UPDATE SKIP LOCKED to avoid races between schedulers
        - Pushes to Redis, then batch-updates DB rows that were successfully queued
        """
        logger.info("Scheduler loop started (Waiting for leadership).")
        while self.running:
            if not self.is_leader:
                time.sleep(SCHEDULER_INTERVAL_S)
                continue
            db = SessionLocal()
            try:
                now = datetime.now(timezone.utc)
                # Select candidate tasks using the index-friendly query
                # NOTE: with_for_update(skip_locked=True) prevents locking contention
                candidates = (
                    db.query(Tasks)
                    .filter(
                        Tasks.status == TaskStatus.PENDING,
                        Tasks.scheduled_at != None,
                        Tasks.scheduled_at <= now
                    )
                    .order_by(Tasks.scheduled_at.asc())
                    .limit(100)
                    .with_for_update(skip_locked=True)
                    .all()
                )
                if not candidates:
                    # nothing to do
                    db.close()
                    time.sleep(SCHEDULER_INTERVAL_S)
                    continue

                logger.info(f"Scheduler found {len(candidates)} tasks.")

                # Batch push tasks to Redis by priority
                high_priority_tasks = []
                low_priority_tasks = []
                
                for task in candidates:
                    payload = {"task_id": task.id}
                    priority = getattr(task, "priority", "low") or "low"
                    
                    if priority == "high":
                        high_priority_tasks.append((task.id, json.dumps(payload)))
                    else:
                        low_priority_tasks.append((task.id, json.dumps(payload)))
                
                # Batch push to Redis using pipeline
                queued_ids = []
                
                if high_priority_tasks:
                    try:
                        r_high = get_redis_client("high")
                        pipe = r_high.pipeline()
                        for task_id, json_payload in high_priority_tasks:
                            pipe.rpush("default", json_payload)
                        pipe.execute()
                        queued_ids.extend([tid for tid, _ in high_priority_tasks])
                        logger.info(f"Batch pushed {len(high_priority_tasks)} high-priority tasks to Redis")
                    except Exception as e:
                        logger.error(f"Failed to batch push high-priority tasks: {e}")
                
                if low_priority_tasks:
                    try:
                        r_low = get_redis_client("low")
                        pipe = r_low.pipeline()
                        for task_id, json_payload in low_priority_tasks:
                            pipe.rpush("default", json_payload)
                        pipe.execute()
                        queued_ids.extend([tid for tid, _ in low_priority_tasks])
                        logger.info(f"Batch pushed {len(low_priority_tasks)} low-priority tasks to Redis")
                    except Exception as e:
                        logger.error(f"Failed to batch push low-priority tasks: {e}")

                # Batch-update DB for all queued ids
                if queued_ids:
                    now_upd = datetime.now(timezone.utc)
                    # single UPDATE for performance
                    db.query(Tasks).filter(Tasks.id.in_(queued_ids)).update(
                        {
                            Tasks.status: TaskStatus.QUEUED,
                            Tasks.updated_at: now_upd
                        },
                        synchronize_session=False
                    )
                    db.commit()
                    logger.info(f"Marked {len(queued_ids)} tasks as QUEUED in DB.")
                else:
                    # nothing queued, just rollback to release locks
                    db.rollback()
            except Exception as e:
                logger.error(f"Error in Scheduler: {e}")
                db.rollback()
            finally:
                # make sure session closed in all situations
                try:
                    db.close()
                except Exception:
                    pass
            # sleep before next poll
            time.sleep(SCHEDULER_INTERVAL_S)
        logger.info("Scheduler loop stopped.")


    def pel_scanner_loop(self):
        """
        Recovery Mechanism.
        Checks for tasks stuck in 'IN_PROGRESS' for too long (indicating worker crash).
        Re-queues them or marks them as failed.
        """
        logger.info("PEL Scanner (Recovery) started. ")
        while self.running: 
            if self.is_leader:
                db = SessionLocal()
                try:
                    # LOGIC UPDATE: We only recover tasks that are claimed by a worker (IN_PROGRESS)
                    running_tasks = db.query(Tasks).filter(
                        Tasks.status == TaskStatus.IN_PROGRESS
                    ).all()

                    for task in running_tasks:
                        if not task.worker_id:
                            self._recover_task(db, task, "No worker assigned")
                            continue
                            
                        # 2. Check Redis for Worker Heartbeat
                        heartbeat_key = f"worker:{task.worker_id}:heartbeat"
                        if not self.redis.exists(heartbeat_key):
                            self._recover_task(db, task, f"Worker {task.worker_id} died")
                    
                    db.commit() # <--- FIXED: Commit needed
                except Exception as e:
                    logger.error(f"Error in PEL Scanner: {e}")
                    db.rollback()
                finally:
                    db.close()  
            time.sleep(RECLAIM_INTERVAL_S)

    # loop runniing in the background for adding stale tasks back in the queue
    def processing_reclaimer_loop(self):
        """Scan `processing:*` lists and move stale items back to the main queue.
        We look at the `processing:default` list (where workers atomically move
        items) and for each element we check the DB row. If the DB row is not
        IN_PROGRESS and it has not been updated recently, we consider the
        processing item stale and move it back to the main queue.
        """
        logger.info("Processing reclaimer started.")
        low_redis = get_redis_client('low')
        processing_queue = f"{PROCESSING_QUEUE_PREFIX}:default"
        while self.running:
            if not self.is_leader:
                time.sleep(RECLAIM_INTERVAL_S)
                continue

            try:
                items = low_redis.lrange(processing_queue, 0, -1) or []
                if not items:
                    time.sleep(RECLAIM_INTERVAL_S)
                    continue

                now = datetime.now(timezone.utc)
                for raw in items:
                    try:
                        payload = json.loads(raw)
                        task_id = payload.get('task_id')
                    except Exception:
                        # If payload is unreadable, remove it to avoid blocking
                        logger.warning("Removing unreadable payload from processing queue")
                        try:
                            low_redis.lrem(processing_queue, 0, raw)
                        except Exception:
                            logger.exception("Failed to remove unreadable payload")
                        continue

                    db = SessionLocal()
                    try:
                        task = db.query(Tasks).filter(Tasks.id == task_id).first()
                        if not task:
                            # No DB row, remove the message
                            low_redis.lrem(processing_queue, 0, raw)
                            continue

                        # If the task is currently IN_PROGRESS, skip it
                        if task.status == TaskStatus.IN_PROGRESS:
                            continue

                        # If task hasn't been updated recently, requeue it
                        updated_at = getattr(task, 'updated_at', None)
                        age = (now - updated_at).total_seconds() if updated_at else None
                        if age is None or age > PROCESSING_RECLAIM_S:
                            logger.warning(f"Reclaiming stale processing item for task {task_id}")
                            # Move the message back to main queue and update DB
                            try:
                                low_redis.lrem(processing_queue, 0, raw)
                                low_redis.lpush('default', raw)
                            except Exception:
                                logger.exception("Failed to move item back to default queue")

                            task.status = TaskStatus.QUEUED
                            task.worker_id = None
                            task.updated_at = now
                            db.commit()
                    except Exception:
                        logger.exception("Error while examining processing item; rolling back DB")
                        db.rollback()
                    finally:
                        db.close()

                time.sleep(RECLAIM_INTERVAL_S)
            except Exception:
                logger.exception("Error in processing reclaimer")
                time.sleep(RECLAIM_INTERVAL_S)

    def _recover_task(self, db, task: Tasks, reason):
        """Helper to retry or fail a task."""
        if task.retry_count < MAX_RETRIES:
            logger.warning(f"Recovering Task {task.id}: {reason}")
            
            # Re-push to Redis
            success = push_task("default", {"task_id": task.id})

            if success:
                # Reset to QUEUED so a new worker can pick it up
                task.status = TaskStatus.QUEUED
                task.worker_id = None
                task.retry_count += 1
                task.updated_at = datetime.now(timezone.utc)
        else:
            logger.error(f"Task {task.id} FAILED: {reason} (Max retries)")
            task.status = TaskStatus.FAILED
            task.worker_id = None
            task.updated_at = datetime.now(timezone.utc)

    # ======================= ENTRY POINT ==========================================
    def start(self): 
        """
        Starts all the threads
        """

        logger.info(f"Starting Queue Manager {self.instance_id}...")

        # 1. Start Leadership Maintainer
        t_leader = threading.Thread(target=self.maintain_leadership, daemon=True)
        t_leader.start()
        # 2. Start Scheduler
        t_scheduler = threading.Thread(target=self.scheduler_loop, daemon=True)
        t_scheduler.start()
        # 3. Start PEL Scanner
        t_scanner = threading.Thread(target=self.pel_scanner_loop, daemon=True)
        t_scanner.start()
        # 4. Start Processing Reclaimer (moves stale items from processing back)
        t_reclaimer = threading.Thread(target=self.processing_reclaimer_loop, daemon=True)
        t_reclaimer.start()
        # 5. Start Queued Reconciliation (ensures QUEUED tasks are in Redis)
        t_reconciler = threading.Thread(target=self.queued_reconciliation_loop, daemon=True)
        t_reconciler.start()

        # Keep main thread alive to handle signals
        try:
            while self.running:
                time.sleep(1)
        except KeyboardInterrupt:
            self.shutdown(None, None)

if __name__ == "__main__":
    qm = QueueManager()
    qm.start()