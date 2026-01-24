import sys
import importlib.util
import os
import logging
import inspect
import asyncio
from typing import Callable, Optional, Tuple, Any

logger = logging.getLogger(__name__)
TASKS_DIR = "/app/worker/tasks"
TASK_TIMEOUT_SECONDS = 180  # 3 minutes


def load_task_handler(task_title: str) -> Tuple[Optional[Callable], Optional[str]]:
    file_path = os.path.join(TASKS_DIR, f"{task_title}.py")
    
    logger.info(f"[DEBUG] Loading task: title='{task_title}', path='{file_path}'")
    logger.info(f"[DEBUG] TASKS_DIR='{TASKS_DIR}', exists={os.path.exists(file_path)}")

    if not os.path.exists(file_path):
        logger.error(f"File not found: {file_path}")
        return None, "File not found"

    # --- FIX FOR ZOMBIE MODULES ---
    # If the module was loaded before, remove it from the cache
    if task_title in sys.modules:
        del sys.modules[task_title]
    # ------------------------------

    try:
        spec = importlib.util.spec_from_file_location(task_title, file_path)
        if spec is None:
            return None, "Invalid file location"
            
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        if hasattr(module, "handler"):
            handler_func = getattr(module, "handler")
            return handler_func, None
        return None, "Missing 'handler' function"

    except Exception as e:
        return None, str(e)

async def execute_dynamic_task(task_title: str, payload: dict) -> Any:
    handler, error = load_task_handler(task_title)
    
    if error:
        raise Exception(f"Loading Error: {error}")

    # DEBUG: Log the payload type and content
    logger.info(f"[DEBUG] Payload type: {type(payload)}")
    logger.info(f"[DEBUG] Payload content: {payload}")

    try:
        # --- TIMEOUT PROTECTION ---
        # Wrap task execution with a timeout to prevent infinite loops
        logger.info(f"Starting task '{task_title}' with {TASK_TIMEOUT_SECONDS}s timeout")
        
        if inspect.iscoroutinefunction(handler):
            # Async handler with timeout
            result = await asyncio.wait_for(
                handler(payload),
                timeout=TASK_TIMEOUT_SECONDS
            )
        else:
            # Sync handler - run in executor with timeout
            loop = asyncio.get_event_loop()
            result = await asyncio.wait_for(
                loop.run_in_executor(None, handler, payload),
                timeout=TASK_TIMEOUT_SECONDS
            )
        
        logger.info(f"Task '{task_title}' completed successfully")
        return result

    except asyncio.TimeoutError:
        error_msg = f"Task '{task_title}' exceeded {TASK_TIMEOUT_SECONDS}s timeout and was terminated"
        logger.error(error_msg)
        raise Exception(error_msg)
    except Exception as e:
        logger.error(f"Runtime error in {task_title}: {e}")
        raise e