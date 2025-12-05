import redis, uuid, logging, json, threading, time, signal
from .redis_client import get_redis, get_redis_client
from datetime import timezone, timedelta, datetime
from .database import SessionLocal
from .models import Tasks, TaskStatus 

LEADER_KEY = "taskflow:leader"
LEASE_TTL_MS = 10000      # Leader lease time (10 seconds)
RENEW_INTERVAL_S = 3      # Try to renew every 3 seconds

SCHEDULER_INTERVAL_S = 5  # How often to check for scheduled tasks
RECLAIM_INTERVAL_S = 10   # How often to check for stuck tasks 
MAX_RETRIES = 3

# Logger configuration
logging.basicConfig(
    level=logging.INFO, 
    format='%(asctime)s - [QueueManager] - %(levelname)s - %(message)s'
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
    Used by the API to submit jobs.
    """
    try:
        r = get_redis_client(priority)
        json_message = json.dumps(message)
        r.rpush(queue_name, json_message)
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
    def scheduler_loop(self):
        """
        Placeholder for Future Scheduling.
        Moves tasks from 'PENDING' -> 'QUEUED' when their time comes.
        """
        logger.info("Scheduler loop started (Waiting for leadership).")
        while self.running:
            if self.is_leader:
                db = SessionLocal()
                try:
                    now = datetime.now(timezone.utc)
                    # find tasks that are scheduled by seaching in databse
                    # LOGIC UPDATE: We look for PENDING tasks (waiting in DB) to move to QUEUED (Redis)
                    tasks = db.query(Tasks).filter(
                        Tasks.status == TaskStatus.PENDING,
                        Tasks.scheduled_at <= now
                    ).limit(100).all()

                    if tasks:
                        logger.info(f"Scheduler found {len(tasks)} tasks.")
                        for task in tasks:
                            # 2. Push to Redis (Standard Default Queue)
                            payload = {"task_id": task.id}
                            # Assuming priority is stored in task.priority or defaulting to low
                            success = push_task("default", payload, priority="low")
                            
                            if success:
                                task.status = TaskStatus.QUEUED  # that is put in the queue 
                                task.updated_at = datetime.now(timezone.utc)
                        
                        db.commit() # <--- FIXED: Commit needed to save status change
                except Exception as e:
                    logger.error(f"Error in Scheduler: {e}")
                    db.rollback()
                finally:
                    db.close()
            
            # <--- FIXED: Sleep moved to end of loop so it runs immediately on start
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

        # Keep main thread alive to handle signals
        try:
            while self.running:
                time.sleep(1)
        except KeyboardInterrupt:
            self.shutdown(None, None)

if __name__ == "__main__":
    qm = QueueManager()
    qm.start()