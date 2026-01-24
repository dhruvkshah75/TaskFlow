import sys
import importlib.util
import os
import logging
import inspect
from typing import Callable, Optional, Tuple, Any

logger = logging.getLogger(__name__)
TASKS_DIR = "/app/worker/tasks"


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

    try:
        # --- FIX FOR ASYNC/SYNC CONFLICT ---
        # Check if the user's handler is async or a regular function
        if inspect.iscoroutinefunction(handler):
            result = await handler(payload)
        else:
            result = handler(payload)
        
        return result

    except Exception as e:
        logger.error(f"Runtime error in {task_title}: {e}")
        raise e