# Distributed Task Queue (TaskFlow)

[![Docker](https://img.shields.io/badge/docker-%230db7ed.svg?style=flat-square&logo=docker&logoColor=white)](https://www.docker.com/)
[![FastAPI](https://img.shields.io/badge/FastAPI-005571?style=flat-square&logo=fastapi)](https://fastapi.tiangolo.com/)
[![Python](https://img.shields.io/badge/python-3.11+-blue.svg?style=flat-square&logo=python&logoColor=white)](https://www.python.org/)
[![Redis](https://img.shields.io/badge/redis-%23DD0031.svg?style=flat-square&logo=redis&logoColor=white)](https://redis.io/)
[![PostgreSQL](https://img.shields.io/badge/postgresql-%23316192.svg?style=flat-square&logo=postgresql&logoColor=white)](https://www.postgresql.org/)

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

---

## Quick Production Deployment 

Deploy TaskFlow in production with pre-built Docker images from GitHub Container Registry:

### **One-Line Install:**

```bash
curl -sSL https://raw.githubusercontent.com/dhruvkshah75/TaskFlow/main/install.sh | bash
```

### **Manual Installation:**

**Prerequisites:**
- Docker 20.10+ and Docker Compose 2.0+
- 2GB RAM minimum
- Port 8000 available

**Step 1: Download Configuration Files**

```bash
mkdir taskflow && cd taskflow
curl -O https://raw.githubusercontent.com/dhruvkshah75/TaskFlow/main/docker-compose.prod.yml
curl -O https://raw.githubusercontent.com/dhruvkshah75/TaskFlow/main/.env.production.example
curl -O https://raw.githubusercontent.com/dhruvkshah75/TaskFlow/main/scripts/setup-production.sh
chmod +x setup-production.sh
```

**Step 2: Generate Secure Credentials**

```bash
./setup-production.sh
```

This automatically generates:
- Strong random database password
- Secure JWT secret key
- Redis authentication password

**Step 3: Deploy**

```bash
docker compose --env-file .env.production -f docker-compose.prod.yml up -d
```

**Step 4: Verify**

```bash
curl http://localhost:8000/status
# Expected: {"status":"ok","database":"connected","redis":"connected"}
```

### **Accessing the API:**

- **API Endpoint:** http://localhost:8000
- **Interactive Docs:** http://localhost:8000/docs
- **ReDoc:** http://localhost:8000/redoc

### **Example Usage:**

```bash
# Register a new user
curl -X POST http://localhost:8000/auth/register \
  -H "Content-Type: application/json" \
  -d '{"username":"johndoe","password":"secure123","email":"john@example.com"}'

# Login to get access token
TOKEN=$(curl -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=johndoe&password=secure123" | jq -r '.access_token')

# Submit a task
curl -X POST http://localhost:8000/tasks/ \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"task_type":"process_data","payload":{"data":"example"},"priority":"MEDIUM"}'

# Check task status
curl -X GET http://localhost:8000/tasks/1 \
  -H "Authorization: Bearer $TOKEN"
```

### **Managing Your Deployment:**

```bash
# View logs
docker compose -f docker-compose.prod.yml logs -f

# Stop services
docker compose -f docker-compose.prod.yml down

# Restart services
docker compose --env-file .env.production -f docker-compose.prod.yml restart

# Scale workers
docker compose --env-file .env.production -f docker-compose.prod.yml up -d --scale worker=8

# Update to latest version
docker compose -f docker-compose.prod.yml pull
docker compose --env-file .env.production -f docker-compose.prod.yml up -d
```

### **Documentation:**

- 📖 [Quick Start Guide](./QUICK_START.md) - Detailed deployment instructions
- 🔒 [Production Deployment Guide](./PRODUCTION_DEPLOYMENT.md) - Security best practices and advanced configuration
- 📋 [Environment Files Guide](./ENV_FILES_GUIDE.md) - Understanding environment configuration

---

## 🛠️ Development Setup (For Contributors)

If you want to develop or contribute to TaskFlow, follow these steps:

**Prerequisites:**
- Python 3.11+
- Docker & Docker Compose
- PostgreSQL (optional for local development)
- Redis (optional for local development)

### **Option 1: Docker Development Environment (Recommended)**

```bash
# Clone the repository
git clone https://github.com/dhruvkshah75/TaskFlow.git
cd TaskFlow

# Copy environment template
cp .env.docker.example .env.docker

# Build and start services
docker compose build
docker compose up -d

# View logs
docker compose logs -f api

# Run migrations
docker compose exec api alembic upgrade head
```

### **Option 2: Local Development (Without Docker)**

```bash
# Clone the repository
git clone https://github.com/dhruvkshah75/TaskFlow.git
cd TaskFlow

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Copy environment template
cp .env.example .env
# Edit .env with your local database and Redis credentials

# Run migrations
alembic upgrade head

# Start API server
uvicorn api.main:app --reload

# In another terminal, start worker
python -m worker.main
```

### **Common Development Commands:**

```bash
# Stop all services
docker compose down

# Full cleanup (remove volumes)
docker compose down --volumes

# Rebuild after code changes
docker compose build
docker compose up -d

# Access database
docker compose exec postgres psql -U postgres -d taskflow_db

# Run tests (if available)
docker compose exec api pytest

# View specific service logs
docker compose logs -f api
docker compose logs -f worker
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

## 📁 Repository Structure

```
TaskFlow/
├── 📄 Production Deployment Files
│   ├── docker-compose.prod.yml      # Production Docker configuration
│   ├── .env.production.example      # Production environment template
│   ├── install.sh                   # One-line installer script
│
├── 📄 Development Files
│   ├── docker-compose.yml          # Development Docker configuration
│   ├── .env.example                # Local dev environment template
│   ├── .env.docker.example         # Docker dev environment template
│   ├── requirements.txt            # Python dependencies                
│
├── 🗄️ Database Migrations
│   ├── alembic.ini                 # Alembic configuration
│   └── alembic/
│       ├── env.py                  # Migration environment
│       ├── script.py.mako          # Migration template
│       └── versions/               # Migration files
│           ├── 132dd8c3882b_create_users_table.py
│           ├── d9b244e43d98_create_api_keys_table.py
│           ├── a35d759eec0b_create_tasks_table.py
│           ├── 8af25adf8e4d_add_index_on_tasks.py
│           └── ff3b6a9d2c4e_create_task_events_table.py
│
├── 🌐 API Service (FastAPI)
│   └── api/
│       ├── Dockerfile              # API container image
│       ├── main.py                 # FastAPI application entry
│       ├── oauth2.py               # JWT authentication
│       ├── rate_limiter.py         # Rate limiting middleware
│       ├── schemas.py              # Pydantic models
│       ├── utils.py                # Helper functions
│       └── routers/
│           ├── auth.py             # Authentication endpoints
│           ├── tasks.py            # Task management endpoints
│           ├── keys.py             # API key management
│           └── users.py            # User management
│
├── ⚙️ Core Services
│   └── core/
│       ├── Dockerfile              # Queue manager container
│       ├── config.py               # Application settings (Pydantic)
│       ├── database.py             # SQLAlchemy database setup
│       ├── models.py               # Database models (Users, Tasks, etc.)
│       ├── redis_client.py         # Redis connection management
│       └── queue_manager.py        # Task queue orchestration & leader election
│
├── 👷 Worker Service
│   └── worker/
│       ├── Dockerfile              # Worker container image
│       ├── main.py                 # Worker process entry point
│       ├── heartbeat.py            # Worker health monitoring
│       ├── task_handler.py         # Task execution logic
│       └── tasks.py                # Task type definitions
│
├── 🔧 Utility Scripts
│   └── scripts/
│       ├── setup-production.sh     # Auto-generate production credentials
│       └── janitor_script.py       # Database cleanup utilities
│
├── 🌐 Nginx 
│   └── nginx/
│       └── nginx.conf              # Reverse proxy configuration
│
├── 📝 Documentation
│   ├── README.md                   # Main documentation
│   └── LICENSE                     # MIT License
│
└── 🔒 Security Files
    ├── .gitignore                  # Git ignore patterns
    ├── .dockerignore               # Docker ignore patterns
    └── .env* files                 # All .env files 
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


