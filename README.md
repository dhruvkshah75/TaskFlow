# Distributed Task Queue (TaskFlow)

## Overview

**TaskFlow** is a robust, distributed task queue system built to handle asynchronous background processing at scale. Designed with a microservices architecture, it reliably manages, schedules, and executes jobs across multiple concurrent worker nodes.

The system leverages **FastAPI** for high-performance task submission and monitoring, **Redis** for efficient message brokering and state management, and **PostgreSQL** for durable persistence of task history and results. By implementing the "Competing Consumers" pattern, TaskFlow ensures load balancing and fault tolerance—if one worker fails, others seamlessly pick up the load.

**Key Capabilities:**
* **Distributed Processing:** Horizontally scalable worker nodes process tasks in parallel, significantly reducing execution time for batched operations.
* **Reliable Scheduling:** Intelligent task distribution ensures jobs are executed as resources become available, with Redis-based locking to prevent race conditions.
* **Full Docker Integration:** The entire stack (API, Database, Broker, Workers) is containerized, enabling single-command deployment and consistent environments.
* **Persistent & Observable:** Every task state change (Queued → Processing → Completed/Failed) is logged in PostgreSQL, providing a complete audit trail and real-time status tracking via REST endpoints.

**Technical Stack:**
* **Language:** Python 3.11+
* **API Framework:** FastAPI
* **Message Broker:** Redis
* **Database:** PostgreSQL (with SQLAlchemy & Alembic)
* **Containerization:** Docker & Docker Compose

## Quick start — run the stack with Docker

If you want to run the full stack locally (recommended for development), use Docker Compose. Make sure you have a `.env` in the project root (see example below).

Build images (installs dependencies into images once):

```bash
docker compose build
```

Start the stack (foreground):

```bash
docker compose up
```

Start in the background (detached):

```bash
docker compose up -d
```

Tail logs for a service:

```bash
docker compose logs -f api
```

Stop and remove containers and network (keeps named volumes by default):

```bash
docker compose down
```

Full cleanup (remove images and named volumes) — use with caution:

```bash
docker compose down --rmi local --volumes --remove-orphans
```

Run database migrations via the entrypoint (uses the project entrypoint to run alembic):

```bash
SERVICE_TYPE=alembic-upgrade ALEMBIC_TARGET=head docker compose run --rm api
```

Alternatively run alembic locally if you have Python and DB access:

```bash
alembic upgrade head
```


## Architecture

![TaskFlow architecture](images/architecture.jpeg)

- **API Service (`api/`)**: Exposes endpoints for task submission, status checks, API key management, and authentication.
- **Worker Service (`worker/`, `worker_cpp/`)**: Processes tasks from the queue. Python workers are implemented in `worker/worker.py`, and C++ workers are scaffolded in `worker_cpp/worker.cpp`.
- **Database (`core/database.py`, models)**: Stores users, API keys, and task metadata.
- **Queue Manager (`core/queue_manager.py`)**: Handles task queuing and dispatching.
- **Redis (`core/redis_client.py`)**: Used for fast in-memory task queueing and rate limiting.
- **Janitor Script (`scripts/janitor.py`)**: Cleans up expired or inactive API keys from the database.

## Key Features

- **Task Submission**: Submit tasks via REST API endpoints.
- **API Key Management**: Create, list, and delete API keys for secure access.
- **Rate Limiting**: Prevents abuse by limiting the number of requests per user.
- **Worker Support**: Python and C++ workers for flexible task execution.
- **Soft and Hard Delete for API Keys**: Inactive keys are first deactivated, then permanently deleted after a retention period.
- **Database Migrations**: Managed with Alembic.

## Directory structure

Below is the actual repository layout (trimmed to key files and folders):

```
.
├── .dockerignore
├── docker-compose.yml
├── README.md
├── requirements.txt
├── alembic.ini
├── alembic/
│   ├── env.py
│   └── versions/
├── api/
│   ├── Dockerfile
│   ├── main.py
│   ├── oauth2.py
│   ├── rate_limiter.py
│   ├── routers/
│   ├── schemas.py
│   └── utils.py
├── core/
│   ├── Dockerfile
│   ├── config.py
│   ├── database.py
│   ├── models.py
│   ├── queue_manager.py
│   └── redis_client.py
├── scripts/
│   ├── __init__.py
│   └── janitor_script.py
├── worker/
│   ├── Dockerfile
│   ├── README.md
│   ├── heartbeat.py
│   ├── main.py
│   ├── task_handler.py
│   └── tasks.py

```

Notes:
- The `Dockerfile` files under `api/`, `core/`, and `worker/` are per-service Dockerfiles used for local development images.
- `alembic/versions/` contains DB migration scripts.
- `TaskFlow/` is a folder with API examples / Postman collections and test scenarios.


## Maintenance

- **Janitor Script**: Run `python3 -m scripts.janitor` to deactivate stale API keys and delete old inactive keys.

## Example `.env` (minimal)

Create a `.env` file in the repository root with the following values for local development (adjust secrets for production):

```env
DATABASE_URL=""
SECRET_KEY=replace_with_a_secure_random_key
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=180

REDIS_HOST_HIGH=redis_high
REDIS_PORT_HIGH=6379
REDIS_HOST_LOW=redis_low
REDIS_PORT_LOW=6379

RATE_LIMIT_PER_HOUR=1000
USER_RATE_LIMIT_PER_HOUR=500
MAX_FAILED_ATTEMPTS=10
LOCKOUT_DURATION_SECONDS=900
HEARTBEAT_INTERVAL_SECONDS=30
```

Note: Use the service names (`postgres`, `redis_low`, `redis_high`) when running inside Docker so services can discover each other on the Compose network.

## Getting Started

If you prefer to run services without Docker (directly on your machine), follow these steps.

1. Install dependencies:

```bash
pip install -r requirements.txt
```

2. Run database migrations (requires DATABASE_URL in your environment):

```bash
alembic upgrade head
```

3. Start the API service locally:

```bash
uvicorn api.main:app --reload
```

4. Start a worker locally (for development):

```bash
python -m worker.main
```

5. C++ worker: build the `worker_cpp` project as appropriate for your platform — see `worker_cpp/` for guidance.


