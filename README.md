# Distributed Task Queue (TaskFlow)

[![Docker](https://img.shields.io/badge/docker-%230db7ed.svg?style=flat-square&logo=docker&logoColor=white)](https://www.docker.com/)
[![Kubernetes](https://img.shields.io/badge/kubernetes-%23326ce5.svg?style=flat-square&logo=kubernetes&logoColor=white)](https://kubernetes.io/)
[![FastAPI](https://img.shields.io/badge/FastAPI-005571?style=flat-square&logo=fastapi)](https://fastapi.tiangolo.com/)
[![Python](https://img.shields.io/badge/python-3.11+-blue.svg?style=flat-square&logo=python&logoColor=white)](https://www.python.org/)
[![Redis](https://img.shields.io/badge/redis-%23DD0031.svg?style=flat-square&logo=redis&logoColor=white)](https://redis.io/)
[![PostgreSQL](https://img.shields.io/badge/postgresql-%23316192.svg?style=flat-square&logo=postgresql&logoColor=white)](https://www.postgresql.org/)
[![CI/CD](https://img.shields.io/badge/CI%2FCD-Automated-brightgreen?style=flat-square&logo=github-actions)](https://github.com/dhruvkshah75/TaskFlow/actions)

## Overview

**TaskFlow** is a robust, production-ready distributed task queue system built to handle asynchronous background processing at scale. Designed with a microservices architecture, it reliably manages, schedules, and executes jobs across multiple concurrent worker nodes with built-in auto-scaling capabilities.

The system leverages **FastAPI** for high-performance task submission and monitoring, **Redis** for efficient message brokering and state management, and **PostgreSQL** for durable persistence of task history and results. By implementing the "Competing Consumers" pattern, TaskFlow ensures load balancing and fault tolerance—if one worker fails, others seamlessly pick up the load.

**Key Capabilities:**
* **Distributed Processing:** Horizontally scalable worker nodes process tasks in parallel
* **Reliable Scheduling:** Intelligent task distribution with Redis-based locking to prevent race conditions
* **Production Ready:** Docker Compose and Kubernetes deployments with automated CI/CD pipelines
* **Persistent & Observable:** Complete audit trail of task states (Queued → Processing → Completed/Failed) via REST endpoints
* **Auto-Scaling:** Kubernetes HPA (Horizontal Pod Autoscaler) support for dynamic worker scaling based on queue depth
* **Continuous Integration:** Automated end-to-end stress testing with 200+ concurrent tasks validation
* **Interactive Showcase:** Live demo website with project overview and system architecture

---

## See TaskFlow in Action

**[Live Showcase Website](https://taskflow-io.vercel.app/)** - Interactive demonstration with project overview, architecture, and demo videos

<table style="width: 100%;">
  <tr>
    <td style="width: 50%; vertical-align: top;">
      <img src="./assets/illustration.png" 
           style="width: 100%; aspect-ratio: 16 / 9; object-fit: cover;" 
           alt="TaskFlow Scaling Proof">
    </td>
    <td style="width: 50%; vertical-align: top;">
      <img src="./assets/demo.gif" 
           style="width: 100%; aspect-ratio: 16 / 9; object-fit: cover;" 
           alt="System Demo">
    </td>
  </tr>
</table>

## Live Demo

<img src="assets/output_high_res.gif" width="100%" alt="TaskFlow Auto-Scaling Demo">

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
# Submit 200 concurrent tasks to stress test the system
python stress-test.py

# Verify all tasks were processed correctly
python verify_jobs.py
```

View CI/CD workflows in `.github/workflows/`:
- `ci.yaml` - Standard integration tests
- `ci-caching.yaml` - Optimized workflow with Docker and pip caching

-----

## Kubernetes Deployment

Deploy TaskFlow to a local Minikube cluster or a production Kubernetes environment.

### **Prerequisites**

- Kubernetes Cluster (Minikube, EKS, GKE, etc.)
- `kubectl` CLI tool

### **1. Secrets Management (Important)**

> **Note:** The `secrets.yaml` file is gitignored to prevent sensitive data leaks. You must create it manually or generate it from your environment variables.

#### **Option A: Generate from .env (Recommended)**

If you have a local `.env` file with your credentials:

```bash
kubectl create secret generic taskflow-secrets \
  --from-env-file=.env \
  --dry-run=client -o yaml > k8s/secrets.yaml
```

#### **Option B: Manual Creation**

Create a file named `k8s/secrets.yaml` using the template below. **You must base64 encode your values** (e.g., `echo -n "mypassword" | base64`).

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: taskflow-secrets
  namespace: taskflow
type: Opaque
data:
  DATABASE_URL: <base64-encoded-url>
  SECRET_KEY: <base64-encoded-key>
  REDIS_PASSWORD: <base64-encoded-password>
```

### **2. Deploying the Stack**

```bash
# command to create a screts.yaml file
kubectl create secret generic taskflow-db-secret \
  --namespace=taskflow \
  --from-literal=POSTGRES_DB=taskflow_db \
  --from-literal=POSTGRES_USER=postgres \
  --from-literal=POSTGRES_PASSWORD=password \
  --from-literal=DATABASE_URL=postgresql://postgres:password@taskflow-pgbouncer:6432/taskflow_db \
  --dry-run=client -o yaml > secrets.yaml
echo "---" >> secrets.yaml
kubectl create secret generic taskflow-redis-secret \
  --namespace=taskflow \
  --from-literal=REDIS_PASSWORD=test_password \
  --from-literal=REDIS_HOST_HIGH=redis-high \
  --from-literal=REDIS_PORT_HIGH=6379 \
  --from-literal=REDIS_HOST_LOW=redis-low \
  --from-literal=REDIS_PORT_LOW=6379 \
  --dry-run=client -o yaml >> secrets.yam
echo "---" >> secrets.yaml
kubectl create secret generic taskflow-app-secret \
  --namespace=taskflow \
  --from-literal=SECRET_KEY=test_secret_key_for_ci_only \
  --from-literal=ALGORITHM=HS256 \
  --from-literal=ACCESS_TOKEN_EXPIRE_MINUTES=60 \
  --dry-run=client -o yaml >> secrets.yaml


# 1. Create Namespace & Configs
kubectl create namespace taskflow
kubectl apply -f k8s/secrets.yaml
kubectl apply -f k8s/configmap.yaml

# 2. Deploy Infrastructure (Postgres & Redis)
kubectl apply -f k8s/postgres.yaml
kubectl apply -f k8s/redis.yaml

# 3. Deploy Application (API, Worker, Queue Manager)
kubectl apply -f k8s/api.yaml
kubectl apply -f k8s/worker.yaml
kubectl apply -f k8s/queue-manager.yaml

# 4. Verify Pods
kubectl get pods -n taskflow -w

# 5. For port forwarding 
kubectl port-forward -n taskflow svc/taskflow-api 8080:80
```

### **3. Accessing the API**

If using **Minikube**, you need to tunnel the service to access it:

```bash
minikube tunnel
# Open http://localhost:8000/docs in your browser
```

-----

## Development Setup

If you want to develop or contribute to TaskFlow, follow these steps:

### **Option 1: Docker Development (Recommended)**

```bash
git clone https://github.com/dhruvkshah75/TaskFlow.git
cd TaskFlow
cp .env.docker.example .env.docker

# Start services
docker compose build
docker compose up -d

# Run migrations
docker compose exec api alembic upgrade head
```

### **Option 2: Local Development (No Docker)**

```bash
# Setup Python Env
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Configure Env
cp .env.example .env
# (Edit .env with your local DB/Redis credentials)

# Run
uvicorn api.main:app --reload
python -m worker.main
```

-----

## Architecture

**TaskFlow** implements a distributed microservices architecture optimized for reliability and scalability:

- **API Service:** FastAPI-based REST endpoints for task submission, status monitoring, and queue management
- **Queue Manager:** Intelligent task distributor with priority queue support (high/low priority)
- **Workers:** Auto-scaling Python workers with concurrent task execution
- **Redis (Dual Queues):** Separate high and low priority queues for task prioritization
- **PostgreSQL + PgBouncer:** Connection pooling for efficient database access and task persistence
- **Kubernetes HPA:** Automatic horizontal scaling based on queue depth and CPU metrics

### **Key Features:**
- **Priority Queuing:** Separate Redis instances for high and low priority tasks
- **Connection Pooling:** PgBouncer reduces PostgreSQL connection overhead
- **Fault Tolerance:** Worker pods automatically restart on failure
- **Observable:** Built-in health checks and status endpoints

## Repository Structure

```
TaskFlow/
├── Deployment
│   ├── docker-compose.prod.yml      # Production Docker Compose
│   ├── k8s/                         # Kubernetes Manifests
│   │   ├── apps/                    # API, Worker, Queue Manager
│   │   ├── infrastructure/          # Redis, Postgres, PgBouncer
│   │   ├── 02-configmaps.yaml       # Application configuration
│   │   └── secrets.yaml.example     # Secret templates (gitignored)
│   └── .github/workflows/           # CI/CD Pipelines
│       ├── ci.yaml                  # Standard integration tests
│       └── ci-caching.yaml          # Optimized builds with caching
│
├── API Service
│   └── api/                         # FastAPI application
│       ├── routers/                 # REST endpoints
│       └── main.py                  # Application entry point
│
├── Core Services
│   └── core/                        # Shared utilities
│       ├── database.py              # PostgreSQL connection
│       ├── redis_client.py          # Redis client wrapper
│       └── config.py                # Environment configuration
│
├── Worker Service
│   └── worker/                      # Task execution engine
│       ├── main.py                  # Worker process
│       └── tasks.py                 # Task handlers
│
├── Database
│   └── alembic/                     # Database migrations
│
└── public/                      # Project website (Vercel)
│     ├── index.html               # Interactive demo page
│     └── assets/                  # Demo GIFs and illustrations
│
├── stress-test.py               # Load testing (200 tasks)
└── verify_jobs.py               # CI/CD validation script
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

## Recent Updates

### Latest Features (Dec 2024)
- **CI/CD Automation**: Automated Kubernetes deployment and stress testing on every commit
- **Performance Optimization**: Docker layer caching reduces build time by ~50%
- **Live Showcase**: Deployed interactive website at [taskflow-io.vercel.app](https://taskflow-io.vercel.app/)
- **Enhanced Documentation**: Added Kubernetes secrets generation commands and deployment guides
- **Stress Testing**: Automated validation with 200+ concurrent task submissions
- **Smart CI Triggers**: Skip CI on documentation-only changes for faster iterations

---

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request. For major changes, please open an issue first to discuss what you would like to change.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---




