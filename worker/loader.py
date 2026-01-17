import importlib.util
import os
import logging

logger = logging.getLogger(__name__)

def load_handler(task_title: str):
    file_path = f"worker/tasks/{task_title}.py"

    if not os.path.exists(file_path):
        return None, "File not found"

    try:
        spec = importlib.util.spec_from_file_location(task_title, file_path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        if hasattr(module, "handler"):
            return module.handler, None
        return None, "No handler function found"

    except ImportError as e:
        # This catches "No module named 'pandas'" etc.
        logger.error(f"Missing dependency in {task_title}: {e}")
        return None, f"Dependency Error: {str(e)}"
    except Exception as e:
        logger.error(f"Failed to load {task_title}: {e}")
        return None, f"Runtime Error: {str(e)}"