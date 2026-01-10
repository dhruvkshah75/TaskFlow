# Distributed Task Queue (TaskFlow)

[![Docker](https://img.shields.io/badge/docker-%230db7ed.svg?style=flat-square&logo=docker&logoColor=white)](https://www.docker.com/)
[![Kubernetes](https://img.shields.io/badge/kubernetes-%23326ce5.svg?style=flat-square&logo=kubernetes&logoColor=white)](https://kubernetes.io/)
[![FastAPI](https://img.shields.io/badge/FastAPI-005571?style=flat-square&logo=fastapi)](https://fastapi.tiangolo.com/)
[![Python](https://img.shields.io/badge/python-3.11+-blue.svg?style=flat-square&logo=python&logoColor=white)](https://www.python.org/)
[![Redis](https://img.shields.io/badge/redis-%23DD0031.svg?style=flat-square&logo=redis&logoColor=white)](https://redis.io/)
[![PostgreSQL](https://img.shields.io/badge/postgresql-%23316192.svg?style=flat-square&logo=postgresql&logoColor=white)](https://www.postgresql.org/)
[![CI/CD](https://img.shields.io/badge/CI%2FCD-Automated-green?style=flat-square&logo=github-actions)](https://github.com/dhruvkshah75/TaskFlow/actions)

## Overview

**TaskFlow** is a robust, production-ready distributed task queue system built to handle asynchronous background processing at scale. Designed with a microservices architecture, it reliably manages, schedules, and executes jobs across multiple concurrent worker nodes with built-in auto-scaling capabilities.

The system leverages **FastAPI** for high-performance task submission and monitoring, **Redis** for efficient message brokering and state management, and **PostgreSQL** for durable persistence of task history and results. By implementing the "Competing Consumers" pattern, TaskFlow ensures load balancing and fault tolerance—if one worker fails, others seamlessly pick up the load.

**Key Capabilities:**
* **One-Command Deployment:** Automated Makefile system deploys the full Kubernetes stack with `make run`
* **Distributed Processing:** Horizontally scalable worker nodes process tasks in parallel
* **Reliable Scheduling:** Intelligent task distribution with Redis-based locking to prevent race conditions
* **Production Ready:** Docker Compose and Kubernetes deployments with automated CI/CD pipelines
* **Persistent & Observable:** Complete audit trail of task states (Queued → Processing → Completed/Failed) via REST endpoints
* **Auto-Scaling:** KEDA-powered autoscaling based on Redis queue depth (0 to 50+ workers dynamically)
* **Continuous Integration:** Automated end-to-end stress testing with 200+ concurrent tasks validation
* **Interactive Showcase:** Live demo website with project overview and system architecture

---

## See TaskFlow in Action

**[taskflow-io.vercel.app](https://taskflow-io.vercel.app/)** - Interactive demonstration with project overview, architecture, and demo videos


  <td style="width: 50%; vertical-align: top;">
    <img src="./assets/illustration.png" 
          style="width: 60%; object-fit: cover;" 
          alt="TaskFlow Scaling Proof">
  </td>
  <td style="width: 50%; vertical-align: top;">
    <img src="assets/output_high_res.gif" 
          style="width: 100%; aspect-ratio: 16 / 9; object-fit: cover;" 
          alt="TaskFlow Auto-Scaling Demo">
  </td>


## Quick Deployment (Docker)

Deploy TaskFlow in production using Docker Compose.

### **One-Line Install**
```bash
curl -sSL https://raw.githubusercontent.com/dhruvkshah75/TaskFlow/main/install.sh | bash
```

### **Manual Install**

1. **Download Configuration:**

```bash
curl -O https://raw.githubusercontent.com/dhruvkshah75/TaskFlow/main/docker-compose.prod.yml
curl -O https://raw.githubusercontent.com/dhruvkshah75/TaskFlow/main/.env.production.example
curl -O https://raw.githubusercontent.com/dhruvkshah75/TaskFlow/main/scripts/setup-production.sh
chmod +x setup-production.sh
```

2. **Generate Credentials & Deploy:**

```bash
./setup-production.sh
docker compose --env-file .env.production -f docker-compose.prod.yml up -d
```

3. **Verify:**

```bash
curl http://localhost:8000/status
```

-----

## CI/CD & Testing

TaskFlow includes automated continuous integration with comprehensive end-to-end testing:

### **Automated Stress Testing**
- **Workflow**: Triggered on every push to main (excluding README changes)
- **Test Coverage**: Deploys full Kubernetes stack with 200+ concurrent task submissions
- **Validation**: Automated verification of task processing, database persistence, and worker scaling
- **Caching**: Docker layer caching for faster builds (~50% reduction in CI time)

### **Run Tests Locally**
```bash
# Using Makefile (recommended)
make stress     # Submit 200 concurrent tasks

# Or directly with Python
python scripts/stress-test.py
```

View CI/CD workflows in `.github/workflows/`:
- `ci.yaml` - Standard integration tests
- `ci-caching.yaml` - Optimized workflow with Docker and pip caching
- `delivery.yaml` - Complete CI/CD pipeline with parallel jobs for building Docker images and deploying to Docker Hub and GHCR registry with end-to-end testing

-----

## Kubernetes Deployment (Minikube)

TaskFlow includes a **highly automated Makefile system** that streamlines the entire Kubernetes development lifecycle. Deploy the full stack with a single command.

### **Prerequisites**

- [Minikube](https://minikube.sigs.k8s.io/docs/start/) installed
- [kubectl](https://kubernetes.io/docs/tasks/tools/) CLI tool
- [Docker](https://docs.docker.com/get-docker/) (for Minikube driver)

### **Quick Start: One Command Deployment**

```bash
make run
```

That's it! This single command automatically:
1. Starts Minikube (if not already running)
2. Creates the `taskflow` namespace
3. Generates secrets with default development credentials (if missing)
4. Pulls pre-built images from GitHub Container Registry (GHCR)
5. Loads images into Minikube
6. Deploys all Kubernetes manifests (API, Workers, Redis, PostgreSQL, PgBouncer)
7. Starts Minikube tunnel for service access
8. Sets up port forwarding to `localhost:8080`

**Access the API:**
- Interactive Docs: http://localhost:8080/docs
- Health Check: http://localhost:8080/status

---

### **Makefile Command Reference**

The Makefile provides a complete set of utilities for managing your local Kubernetes environment:

#### **Core Workflow**

| Command | Description |
|---------|-------------|
| `make run` | **Start everything.** Full deployment pipeline (pull → load → apply → forward). |
| `make stop` | **Pause.** Stops Minikube and tunnels (data preserved in cluster). |
| `make clean` | **Reset.** Deletes the `taskflow` namespace and all resources (**data lost**). |
| `make restart` | **Refresh.** Equivalent to `make clean && make run`. |
| `make logs` | Stream **color-coded logs** from all services (API: cyan, Workers: green, Queue Manager: magenta). |
| `make db-shell` | Connect to PostgreSQL with an interactive `psql` session. |
| `make status` | Show running pods, services, and deployments in the `taskflow` namespace. |
| `make watch-scaling` | Monitor worker autoscaling in real-time. |
| `make stress` | Submit 200 concurrent tasks to stress test the system. |
| `make secrets` | Regenerate `k8s/01-secrets.yaml` with default development credentials (only if missing). |
| `make prune` | Free up disk space by deleting Docker build cache and dangling images. |
| `make help` | Display all available commands with descriptions. |

---

### **Secrets Management**

The Makefile intelligently handles secrets:
- **Auto-Generation:** If `k8s/01-secrets.yaml` doesn't exist, `make run` (or `make secrets`) creates it with safe default credentials for local development.
- **No Overwrites:** If the file already exists, it's never modified—ensuring your custom configurations remain intact.
- **Gitignored:** The secrets file is excluded from version control for security.

**Default Development Credentials:**
For production deployments, manually edit `k8s/01-secrets.yaml` or generate from your `.env` file:
```bash
kubectl create secret generic taskflow-db-secret \
  --from-env-file=.env \
  --dry-run=client -o yaml > k8s/01-secrets.yaml
```

---

### **Advanced Logging Features**

The `make logs` command includes production-grade logging enhancements:

- **Color-Coded Streams:** Instantly identify service outputs (API, Workers, Queue Manager).
- **Anti-Buffering:** Real-time log streaming with `awk` flush and `PYTHONUNBUFFERED=1`.
- **Concurrency Handling:** Supports up to 50 concurrent log streams (`--max-log-requests=50`) for autoscaling scenarios.

---

### **Disk Space Management**

If Docker consumes too much disk space:

```bash
make prune
```

This removes:
- All Docker build cache (`docker builder prune --all`)
- Dangling/unused images (`docker image prune`)

Verify reclaimed space with:
```bash
docker system df
```
-----

## Development Setup

If you want to develop or contribute to TaskFlow, follow these steps:

### **Option 1: Kubernetes Development (Recommended)**

Use the Makefile for a production-like local environment:

```bash
git clone https://github.com/dhruvkshah75/TaskFlow.git
cd TaskFlow

# Deploy full stack to Minikube
make run

# View logs while developing
make logs

# Access API at http://localhost:8080/docs

# Make code changes...
# Rebuild and redeploy
make restart

# Debug database
make db-shell

# Monitor autoscaling
make watch-scaling
```

### **Option 2: Docker Development**

```bash
git clone https://github.com/dhruvkshah75/TaskFlow.git
cd TaskFlow
cp .env.docker.example .env.docker

# Start services
docker compose build
docker compose up -d

# Run migrations
docker compose exec api alembic upgrade head

# Access API at http://localhost:8000/docs
```

-

## Repository Structure

```
TaskFlow/
├── .github/workflows/           # CI/CD Pipelines
│   ├── ci.yaml                  # Standard integration tests
│   ├── delivery.yaml            # Complete CI/CD pipeline with image builds and E2E tests
│   └── ci-caching.yaml          # Optimized builds with caching
│
├── Deployment
│   ├── docker-compose.prod.yml  # Production Docker Compose
│   ├── docker-compose.yml       # Development Docker Compose
│   ├── Makefile                 # **Automated Kubernetes workflow** (make run, make logs, etc.)
│   └── k8s/                     # Kubernetes Manifests
│       ├── 01-secrets.yaml      # Auto-generated secrets (gitignored)
│       ├── 02-configmaps.yaml   # Application configuration
│       ├── apps/                # API, Worker, Queue Manager deployments
│       ├── infrastructure/      # Redis, PostgreSQL, PgBouncer
│       └── autoscaling/         # KEDA autoscalers
│   
│
├── API Service
│   └── api/                     # FastAPI application
│       ├── routers/             # REST endpoints
│       ├── main.py              # Application entry point
│       └── Dockerfile 
│
├── Core Services
│   └── core/                    # Shared utilities
│       ├── database.py          # PostgreSQL connection
│       ├── redis_client.py      # Redis client wrapper
│       ├── queue_manager.py     # Queue distribution logic
│       ├── config.py            # Environment configuration
│       └── Dockerfile
│
├── Worker Service
│   └── worker/                  # Task execution engine
│       ├── main.py              # Worker process
│       ├── heartbeat.py         # Periodic health reporting
│       ├── tasks.py             # Task handlers
│       └── Dockerfile
│
├── Database Migrations
│   └── alembic/                 # Schema version control
│   
├── Project Website
│   └── public/                  # Static site (deployed to Vercel)
│       ├── index.html           # Interactive demo page
│       ├── architecture.html    # System architecture documentation
│       └── assets/              # Demo GIFs and illustrations
│
├── Testing & Scripts
│   └── scripts/
│       ├── stress-test.py       # Load testing (200 concurrent tasks)
│       ├── verify_jobs.py       # CI/CD validation script
│       └── setup-production.sh  # Production deployment helper
│
└── Configuration
    └── .env.production.example  # Production template
```

## Example `.env` Configuration

Create a `.env` file in the root directory:

```env
# Database Configuration
DATABASE_URL=postgresql://user:pass@localhost:5432/taskflow

# Security
SECRET_KEY=replace_with_secure_key
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=180

# Redis Configuration
# Note: In K8s, these are overridden by env vars in the deployment YAMLs
REDIS_HOST_HIGH=redis_high
REDIS_PORT_HIGH=6379
REDIS_HOST_LOW=redis_low
REDIS_PORT_LOW=6379
REDIS_PASSWORD=your_redis_password

# App Settings
RATE_LIMIT_PER_HOUR=1000
HEARTBEAT_INTERVAL_SECONDS=30
```

---


## Contributing

Contributions are welcome! Please feel free to submit a Pull Request. For major changes, please open an issue first to discuss what you would like to change.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---




