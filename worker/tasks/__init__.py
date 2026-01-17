# This file exports HANDLERS for the modular worker system
# Dynamic handlers from uploaded files are loaded at runtime by task_handler.py

async def default_handler(payload: dict):
    """Default handler when no specific task file is found"""
    return {"status": "error", "message": "No handler found for this task"}

# HANDLERS dictionary - extended dynamically at runtime
HANDLERS = {
    "default": default_handler
}
