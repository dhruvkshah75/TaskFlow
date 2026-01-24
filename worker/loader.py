import importlib.util
import os
import logging
import sys

logger = logging.getLogger(__name__)

# Use absolute path - worker container has files at /app/worker/tasks/
BASE_DIR = os.path.dirname(os.path.abspath(__file__))  # /app/worker/
TASKS_DIR = os.path.join(BASE_DIR, "tasks")  # /app/worker/tasks/

def load_handler(task_title: str):
    file_path = os.path.join(TASKS_DIR, f"{task_title}.py")

    if not os.path.exists(file_path):
        logger.error(f"Worker could not find task file at: {file_path}")
        return None, f"File not found at {file_path}"

    try:
        # Prevent "Zombie Modules" by clearing cache if it was loaded before
        if task_title in sys.modules:
            del sys.modules[task_title]

        spec = importlib.util.spec_from_file_location(task_title, file_path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        if hasattr(module, "handler"):
            return module.handler, None
        return None, "No handler function found"

    except ImportError as e:
        logger.error(f"Missing dependency in {task_title}: {e}")
        return None, f"Dependency Error: {str(e)}"
    except Exception as e:
        logger.error(f"Failed to load {task_title}: {e}")
        return None, f"Runtime Error: {str(e)}"