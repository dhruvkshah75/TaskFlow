from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .routers import api_keys, auth, status, tasks, user
import logging
from logging.handlers import RotatingFileHandler
import os
import sys

app = FastAPI()

origins = ["*"]

app .add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_keys.router)
app.include_router(user.router)
app.include_router(auth.router)
app.include_router(tasks.router)
app.include_router(status.router)


# ==============================================================================
#               for creating logs for dev
# ==============================================================================
def configure_logging(log_file: str = "logs/app.log"):
    fmt = "%(asctime)s %(levelname)s %(name)s: %(message)s"
    # Base console handler (always present)
    console = logging.StreamHandler(sys.stdout)
    console.setLevel(logging.INFO)
    console.setFormatter(logging.Formatter(fmt))

    # ensure log directory exists
    log_dir = os.path.dirname(log_file) or "logs"
    try:
        os.makedirs(log_dir, exist_ok=True)
    except Exception:
        logging.getLogger(__name__).warning(
            "Could not create log directory %s, continuing without file handler", log_dir
        )

    # App log (general)
    app_handler = RotatingFileHandler(os.path.join(log_dir, "app.log"), maxBytes=10_000_000, backupCount=5)
    app_handler.setLevel(logging.INFO)
    app_handler.setFormatter(logging.Formatter(fmt))

    # Queue manager specific log file
    qm_handler = RotatingFileHandler(os.path.join(log_dir, "queue_manager.log"), maxBytes=10_000_000, backupCount=5)
    qm_handler.setLevel(logging.INFO)
    qm_handler.setFormatter(logging.Formatter(fmt))

    # Worker specific log file
    worker_handler = RotatingFileHandler(os.path.join(log_dir, "worker.log"), maxBytes=10_000_000, backupCount=5)
    worker_handler.setLevel(logging.INFO)
    worker_handler.setFormatter(logging.Formatter(fmt))

    # Root logger: console + app file
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    # remove any existing handlers to avoid duplicate logs in interactive reload
    for h in list(root.handlers):
        root.removeHandler(h)
    root.addHandler(console)
    root.addHandler(app_handler)

    # Configure named loggers for queue manager and worker so their logs go to files
    logging.getLogger("core.queue_manager").addHandler(qm_handler)
    logging.getLogger("core.queue_manager").setLevel(logging.INFO)

    logging.getLogger("worker").addHandler(worker_handler)
    logging.getLogger("worker").setLevel(logging.INFO)

    # Also route uvicorn loggers to the same handlers for consistency
    logging.getLogger("uvicorn.access").addHandler(app_handler)
    logging.getLogger("uvicorn.error").addHandler(app_handler)

# Call at startup
configure_logging()

# ====================================================================================
# ====================================================================================

@app.get("/")
def root():
    return {
        "Welcome to TaskFlow"
    }