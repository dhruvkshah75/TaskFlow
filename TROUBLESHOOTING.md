# TaskFlow Troubleshooting Guide

## Workers Not Picking Up Tasks

### Symptom
Tasks are being created and marked as QUEUED in the database, but workers are not processing them.

### Root Cause
This issue typically occurs when:
1. **Redis Low (port 6380) is not running** - Workers connect to Redis Low to pull tasks
2. **Tasks are marked QUEUED in DB but not in Redis** - This happens if Redis was down when tasks were queued

### Solution

#### 1. Ensure Both Redis Instances Are Running

For **local development**, run:
```bash
./scripts/start-local-redis.sh
```

Or manually start both Redis instances:
```bash
# Start Redis High (port 6379) - for auth, caching, rate limiting
redis-server --port 6379 --daemonize yes

# Start Redis Low (port 6380) - for task queue
redis-server --port 6380 --daemonize yes
```

Verify both are running:
```bash
redis-cli -p 6379 ping  # Should return PONG
redis-cli -p 6380 ping  # Should return PONG
```

For **Docker/production**, ensure all containers are running:
```bash
docker-compose ps
# or
docker-compose -f docker-compose.prod.yml ps
```

#### 2. Verify Queue Manager Is Running

The Queue Manager is responsible for:
- Moving PENDING tasks to QUEUED status
- Pushing tasks to Redis queue
- **Reconciling tasks** that are QUEUED in DB but missing from Redis (NEW FIX)

Check if it's running:
```bash
# For Docker
docker-compose logs queue_manager

# For local development
ps aux | grep queue_manager
```

Start it if not running:
```bash
# For Docker
docker-compose up -d queue_manager

# For local development
python -m core.queue_manager
```

#### 3. Verify Workers Are Running

Check worker status:
```bash
# For Docker
docker-compose ps worker
docker-compose logs worker

# For local development
ps aux | grep "worker.main"
```

Start workers if needed:
```bash
# For Docker
docker-compose up -d --scale worker=4

# For local development
python -m worker.main
```

### How the Fix Works

The system now includes a **Queued Reconciliation Loop** that:
- Runs every 30 seconds
- Checks for tasks marked as QUEUED in the database
- Ensures they are actually present in the Redis queue
- Re-pushes any missing tasks to Redis

This handles the edge case where:
1. Task is created with status PENDING
2. Queue Manager tries to push to Redis
3. Redis Low is down → push fails
4. Task is incorrectly marked as QUEUED in DB
5. **New reconciliation loop detects and fixes this**

### Verify the Fix

1. Check Redis queue length:
```bash
redis-cli -p 6380 LLEN default
```

2. Check task status in database:
```bash
# Count tasks by status
python -c "
from core.database import SessionLocal
from core.models import Tasks, TaskStatus

db = SessionLocal()
for status in TaskStatus:
    count = db.query(Tasks).filter(Tasks.status == status).count()
    print(f'{status.value}: {count}')
db.close()
"
```

3. Monitor queue manager logs for reconciliation:
```bash
tail -f logs/queue_manager.log | grep -i "reconcil"
```

You should see messages like:
```
Reconciling 15 QUEUED tasks with Redis
Successfully reconciled 15 tasks to Redis
```

### Diagnostic Commands

```bash
# Check both Redis instances
redis-cli -p 6379 INFO server | grep process_id
redis-cli -p 6380 INFO server | grep process_id

# Check queue contents
redis-cli -p 6380 LRANGE default 0 5

# Check processing queue
redis-cli -p 6380 LRANGE processing:default 0 5

# Monitor Redis commands in real-time
redis-cli -p 6380 MONITOR

# Check worker heartbeats
redis-cli -p 6380 KEYS "worker:*:heartbeat"
```

## Other Common Issues

### Tasks Stuck in IN_PROGRESS

If tasks are stuck in IN_PROGRESS status, the **PEL Scanner** should recover them automatically.

Check logs:
```bash
tail -f logs/queue_manager.log | grep -i "recover"
```

### High CPU Usage on Workers

Workers run a stress test function by default. To disable it, comment out this code in `worker/task_handler.py`:

```python
# --- STRESS TEST TRIGGER ---
# perform_heavy_computation()
# ---------------------------
```

### Connection Refused Errors

Ensure environment variables are set correctly in `.env`:
```bash
REDIS_HOST_HIGH="localhost"
REDIS_PORT_HIGH=6379

REDIS_HOST_LOW="localhost"
REDIS_PORT_LOW=6380

DATABASE_URL="postgresql://postgres:password123@localhost:5432/taskflow_db"
```

For Docker, use container names instead of localhost:
```bash
REDIS_HOST_HIGH="redis_high"
REDIS_HOST_LOW="redis_low"
DATABASE_URL="postgresql://postgres:password@postgres:5432/taskflow_db"
```
