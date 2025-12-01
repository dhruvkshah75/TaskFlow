# Distributed Task Queue (TaskFlow)

## Overview

TaskFlow is a distributed task queue system designed to manage, schedule, and execute background jobs across multiple worker processes. It supports both Python and C++ workers, allowing for flexible and scalable task processing.

## Architecture

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

## Directory Structure


```
TaskFlow/
├── alembic.ini
├── docker-compose.yml
├── notes.md
├── README.md
├── requirements.txt
├── alembic/
├── api/
│   ├── __init__.py
│   ├── dockerfile
│   ├── main.py
│   ├── oauth2.py
│   ├── rate_limiter.py
│   ├── schemas.py
│   ├── utils.py
│   └── routers/
│       ├── __init__.py
│       ├── api_keys.py
│       ├── auth.py
│       ├── status.py
│       ├── tasks.py
│       └── user.py
├── core/
│   ├── __init__.py
│   ├── config.py
│   ├── database.py
│   ├── models.py
│   ├── queue_manager.py
│   └── redis_client.py
├── scripts/
│   ├── __init__.py
│   └── janitor.py
├── worker/
│   ├── __init__.py
│   ├── dockerfile
│   └── worker.py
├── worker_cpp/
│   ├── dockerfile
│   └── worker.cpp
```

## Maintenance

- **Janitor Script**: Run `python3 -m scripts.janitor` to deactivate stale API keys and delete old inactive keys.

## Getting Started

1. **Install dependencies**:  
	`pip install -r requirements.txt`
2. **Run database migrations**:  
	`alembic upgrade head`
3. **Start API service**:  
	`uvicorn api.main:app`
4. **Start worker(s)**:  
	`python3 worker/worker.py`
5. **Build and run C++ worker**:  
	See `worker_cpp/worker.cpp` and `worker_cpp/dockerfile`.


