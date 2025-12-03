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
# for creating logs for dev
def configure_logging(log_file: str = "logs/app.log"):
    fmt = "%(asctime)s %(levelname)s %(name)s: %(message)s"
    logging.basicConfig(level=logging.INFO, format=fmt, handlers=[logging.StreamHandler(sys.stdout)])

    # ensure log directory exists
    log_dir = os.path.dirname(log_file)
    if log_dir:
        try:
            os.makedirs(log_dir, exist_ok=True)
        except Exception:
            # if we cannot create the directory, fallback to stdout-only logging
            logging.getLogger(__name__).warning(
                "Could not create log directory %s, continuing without file handler", log_dir
                )
    fh = RotatingFileHandler(log_file, maxBytes=10_000_000, backupCount=5)
    fh.setLevel(logging.INFO)
    fh.setFormatter(logging.Formatter(fmt))
    logging.getLogger().addHandler(fh)

# Call at startup
configure_logging()

# ====================================================================================


@app.get("/")
def root():
    return {
        "Welcome to TaskFlow"
    }