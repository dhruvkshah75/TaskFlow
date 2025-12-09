
import asyncio, logging, json
from datetime import datetime, timezone, timedelta
import sqlalchemy as sa
from core.database import SessionLocal 
from core.models import Tasks, TaskStatus, TaskEvents, EventType
from .tasks import HANDLERS
from core.queue_manager import push_task

logging.basicConfig(
    level=logging.INFO, 
    format='%(asctime)s - [Worker] - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("logs/worker.log"), # Writes to the file
        logging.StreamHandler()                 # Writes to the terminal
    ]
)
logger = logging.getLogger(__name__)


class TaskHandler:
    def __init__(self, worker_id: str):
        self.worker_id = worker_id
        # how many retries before marking FAILED; keep small here or read from config
        self.max_retries = 5


    async def handle_task(self, task_data: dict):
        task_id = task_data.get("task_id")
        loop = asyncio.get_running_loop()
        # 1. Claim
        claim_result = await loop.run_in_executor(None, self._claim_task_sync, task_id)
        if not claim_result:
            return
        
        task_type, payload, task_title = claim_result
        # 2. Find Handler (Fallback to title if type is missing)
        handler_key = task_type or task_title
        handler = HANDLERS.get(handler_key)

        if not handler:
            logger.error(f"No handler found for key: '{handler_key}'")
            # If there's no handler registered for this task key, instead of
            # failing immediately we increment the retry counter and requeue
            # the task (up to max_retries). This gives operators a chance to
            # register a handler or recover transient misconfiguration.
            await loop.run_in_executor(None, self._retry_or_fail_sync, task_id, f"No handler: {handler_key}")
            return
        # 3. Execute
        try:
            if asyncio.iscoroutinefunction(handler):
                result = await handler(payload)
            else:
                result = await loop.run_in_executor(None, handler, payload)

            # Mark COMPLETED
            await loop.run_in_executor(None, self._complete_task_sync, task_id, result)

        except Exception as e:
            logger.exception(f"Task {task_id} crashed during execution")
            await loop.run_in_executor(None, self._retry_or_fail_sync, task_id, str(e))

    

    def _claim_task_sync(self, task_id):
        db = SessionLocal()
        try:
            # Perform an atomic UPDATE ... RETURNING so we claim the row and get
            # the payload/title in a single DB round-trip. This avoids races and
            # ensures the worker_id and status are persisted immediately.
            now = datetime.now(timezone.utc)
            stmt = (
                sa.update(Tasks)
                .where(Tasks.id == task_id, Tasks.status.in_([TaskStatus.PENDING, TaskStatus.QUEUED]))
                .values({
                    'status': TaskStatus.IN_PROGRESS,
                    'worker_id': self.worker_id,
                    'updated_at': now
                })
                .returning(Tasks.id, Tasks.payload, Tasks.title)
            )
            res = db.execute(stmt)
            row = res.fetchone()
            if not row:
                db.rollback()
                return None
            db.commit()
            logger.info(f"Claimed task {row.id} by worker {self.worker_id}")

            # Parse payload from returned row
            try:
                payload = json.loads(row.payload) if row.payload else {}
            except Exception:
                payload = {}

            return (payload.get("type"), payload, row.title)
        except Exception as e:
            logger.exception(f"Claim failed: {e}")
            db.rollback()
            return None
        finally:
            db.close()


    def _fail_task_sync(self, task_id, error_msg):
        db = SessionLocal()
        try:
            task = db.query(Tasks).filter(Tasks.id == task_id).first()
            if task:
                task.status = TaskStatus.FAILED
                task.worker_id = None
                task.updated_at = datetime.now(timezone.utc)
                ev = TaskEvents(task_id=task.id, event_type=EventType.FAILED, message=error_msg)
                db.add(ev)
                db.commit()
                logger.info(f"Task {task_id} marked FAILED in DB")
        except Exception as e:
            logger.exception(f"DB Fail Error: {e}")
            db.rollback()
        finally:
            db.close()
            

    def _complete_task_sync(self, task_id, result):
            """ Mark task as COMPLETED and save the result."""
            db = SessionLocal()
            try:
                task = db.query(Tasks).filter(Tasks.id == task_id).first()
                if task:
                    # 1. Update the Main Task Table
                    task.status = TaskStatus.COMPLETED
                    task.worker_id = None
                    task.updated_at = datetime.now(timezone.utc)
                    
                    # Format the result for storage
                    # If it's a dictionary (JSON), dump it to string. 
                    # If it's a TaskResult object, take the message or data.
                    final_output = str(result)
                    if hasattr(result, 'message'):
                        final_output = result.message
                    elif isinstance(result, dict):
                        final_output = json.dumps(result)

                    # SAVE THE RESULT TO THE MAIN TABLE (only if model has column)
                    # Avoid assigning to `task.result` when the Tasks model doesn't
                    # define a `result` column (some branches of the repo removed it).
                    if hasattr(Tasks, 'result'):
                        try:
                            task.result = final_output
                        except Exception:
                            logger.exception("Failed to save result to task.result; skipping")
                    
                    # 2. Add to Event Log (History)
                    ev = TaskEvents(
                        task_id=task.id, 
                        event_type=EventType.COMPLETED, 
                        message=final_output[:500] # Cap length for the log
                    )
                    db.add(ev)
                    
                    # Commit both changes (Task Update + Event Insert)
                    db.commit()
                    logger.info(f"Task:{task_id} marked COMPLETED (Result Saved)")
            except Exception as e:
                logger.exception(f"DB Complete Error: {e}")
                db.rollback()
            finally:
                db.close()


    def _retry_or_fail_sync(self, task_id, error_msg):
        db = SessionLocal()
        try:
            task = db.query(Tasks).filter(Tasks.id == task_id).first()
            if task:
                # increment the retry counter and decide whether to requeue
                task.retry_count = (task.retry_count or 0) + 1
                if task.retry_count <= self.max_retries:
                    task.status = TaskStatus.PENDING
                    evt = EventType.RETRIED
                    # Schedule a retry in the future (backoff) rather than
                    # requeueing immediately. This avoids tight busy-loops when
                    # a handler is missing or failing repeatedly.
                    backoff_s = min(60, 5 * task.retry_count)
                    task.scheduled_at = datetime.now(timezone.utc) + timedelta(seconds=backoff_s)
                else:
                    task.status = TaskStatus.FAILED
                    evt = EventType.FAILED

                task.worker_id = None
                task.updated_at = datetime.now(timezone.utc)
                ev = TaskEvents(task_id=task.id, event_type=evt, message=error_msg)
                db.add(ev)
                db.commit()
        except Exception:
            logger.exception("Error while retrying/failing task; rolling back")
            db.rollback()
        finally:
            db.close()