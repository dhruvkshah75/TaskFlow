
import asyncio, logging, json
from datetime import datetime, timezone
from core.database import SessionLocal 
from core.models import Tasks, TaskStatus, TaskEvents
from .tasks import HANDLERS

logging.basicConfig(
    level=logging.INFO, 
    format='%(asctime)s - [Worker] - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class TaskHandler:
    def __init__(self, worker_id: str):
        self.worker_id = worker_id


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
            # Mark FAILED in DB
            await loop.run_in_executor(None, self._fail_task_sync, task_id, f"No handler: {handler_key}")
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
            task = db.query(Tasks).filter(Tasks.id == task_id).with_for_update(skip_locked=True).first()
            if not task or task.status not in (TaskStatus.PENDING, TaskStatus.QUEUED):
                return None
            
            task.status = TaskStatus.IN_PROGRESS
            task.worker_id = self.worker_id
            task.updated_at = datetime.now(timezone.utc)
            db.commit()
            
            # Parse payload
            try:
                payload = json.loads(task.payload) if task.payload else {}
            except:
                payload = {}
                
            return (payload.get("type"), payload, task.title)
        except Exception as e:
            logger.error(f"Claim failed: {e}")
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
                ev = TaskEvents(task_id=task.id, event_type='FAILED', message=error_msg)
                db.add(ev)
                db.commit()
                logger.info(f"Task {task_id} marked FAILED in DB")
        except Exception as e:
            logger.error(f"DB Fail Error: {e}")
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
                    
                    # SAVE THE RESULT TO THE MAIN TABLE
                    task.result = final_output  # <--- THIS WAS MISSING
                    
                    # 2. Add to Event Log (History)
                    ev = TaskEvents(
                        task_id=task.id, 
                        event_type='COMPLETED', 
                        message=final_output[:500] # Cap length for the log
                    )
                    db.add(ev)
                    
                    # Commit both changes (Task Update + Event Insert)
                    db.commit()
                    logger.info(f"Task:{task_id} marked COMPLETED (Result Saved)")
            except Exception as e:
                logger.error(f"DB Complete Error: {e}")
                db.rollback()
            finally:
                db.close()


    def _retry_or_fail_sync(self, task_id, error_msg):
        db = SessionLocal()
        try:
            task = db.query(Tasks).filter(Tasks.id == task_id).first()
            if task:
                task.retry_count = (task.retry_count or 0) + 1
                if task.retry_count <= 3:
                    task.status = TaskStatus.PENDING
                    evt = "RETRY"
                else:
                    task.status = TaskStatus.FAILED
                    evt = "FAILED"
                task.worker_id = None
                task.updated_at = datetime.now(timezone.utc)
                ev = TaskEvents(task_id=task.id, event_type=evt, message=error_msg)
                db.add(ev)
                db.commit()
        except Exception:
            db.rollback()
        finally:
            db.close()