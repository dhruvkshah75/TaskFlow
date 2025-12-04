import redis, uuid, logging, json, threading, time, signal
from .redis_client import get_redis, get_redis_client
from datetime import timezone, timedelta, datetime
from .database import SessionLocal

LEADER_KEY = "taskflow:leader"
LEASE_TTL_MS = 10000      # Leader lease time (10 seconds)
RENEW_INTERVAL_S = 3      # Try to renew every 3 seconds

SCHEDULER_INTERVAL_S = 5  # How often to check for scheduled tasks
RECLAIM_INTERVAL_S = 10   # How often to check for stuck tasks 
# Assume worker crash if stuck in 'processing' > 5 mins
VISIBILITY_TIMEOUT_MINUTES = 5 
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
        json_message = json.dump(message)
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
        

    # ===================== LOOPS RUN ONLY BY THE LEADER =======================
    def scheduler_loop(self):
        """
        Placeholder for Future Scheduling.
        Moves tasks from 'SCHEDULED' -> 'QUEUED' when their time comes.
        """
        logger.info("Scheduler loop started (Waiting for leadership).")
        while self.running:
            if self.is_leader:
                # Logic would go here to check DB for scheduled tasks
                # For now, we just sleep to simulate activity
                pass
            
            time.sleep(SCHEDULER_INTERVAL_S)
        logger.info("Scheduler loop stopped.")


    def pel_scanner_loop(self):
        """
        Recovery Mechanism.
        Checks for tasks stuck in 'IN_PROGRESS' for too long (indicating worker crash).
        Re-queues them or marks them as failed.
        """
        pass