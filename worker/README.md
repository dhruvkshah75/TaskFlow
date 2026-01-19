# Worker — Modular Task Execution Engine for TaskFlow

This document explains the **modular worker component** located in the `worker/` folder. The worker dynamically loads and executes user-uploaded Python code at runtime without requiring container rebuilds. It describes what each file does, the runtime flow, important implementation details, salient features, known shortcomings, and how to run/debug the worker locally.

Files
-----

- `main.py`
  - Entry point for the async worker process with **dual-priority queue support**.
  - Connects to **both high and low priority Redis instances** via `core.redis_client.get_async_redis_client` and listens on a list-based queue named `default`.
  - **Priority-based polling**: Checks high-priority queue first, then falls back to low-priority queue for fair task distribution.
  - Uses an atomic move from `default` to `processing:default` so payloads are not lost when a worker crashes after popping them. Implementation prefers `BLMOVE` (if supported) and falls back to `BRPOPLPUSH` for older Redis servers/clients.
  - After moving the payload into the processing list, it calls `execute_dynamic_task` from `task_handler.py` to **dynamically load and execute user-uploaded Python code**.
  - Starts and stops a `HeartbeatService` (see `heartbeat.py`) so the QueueManager can detect live workers.
  - **Status tracking**: Updates task status to `IN_PROGRESS` → `COMPLETED` or `FAILED` with results/errors stored in the database.

- `task_handler.py` (formerly `loader.py`)
  - Contains the **dynamic task loading and execution logic** using Python's `importlib`.
  - **`load_task_handler(task_title)`**: Dynamically imports `.py` files from `worker/tasks/` directory at runtime.
  - **Module cache management**: Clears `sys.modules` before loading to prevent stale module issues when files are updated/deleted.
  - **`execute_dynamic_task(task_title, payload)`**: Executes the loaded handler function with intelligent async/sync detection.
  - **Async/Sync support**: Uses `inspect.iscoroutinefunction()` to detect whether the handler is `async def` or `def` and executes accordingly.
  - **Error handling**: Returns descriptive error messages for missing files, missing `handler()` function, or runtime exceptions.

- `loader.py` (deprecated, kept for reference)
  - Original task loading logic—retained for backward compatibility or migration reference.
  - New implementations should use `task_handler.py` instead.

- `tasks/` directory
  - **Shared storage volume** where user-uploaded Python task files are stored (mounted as ReadWriteMany PVC in Kubernetes).
  - Each file must contain a `handler(payload)` function (can be `def` or `async def`).
  - Workers dynamically import modules from this directory at runtime.
  - Files can be uploaded via the API endpoint `POST /tasks/upload_file`.
  - Files can be deleted via `DELETE /tasks/delete_file` or automatically after execution (configurable).

- `utils.py`
  - Contains database helper functions for task status updates.
  - **`update_task_status(task_id, status, result)`**: Async function to update task status and store execution results in PostgreSQL.

- `heartbeat.py`
  - Runs a periodic async task that writes a short-lived key into Redis (for example `worker:<id>:heartbeat`).
  - The QueueManager checks heartbeats to decide if a worker is alive; if not, tasks claimed by that worker are candidates for recovery.
  - Uses high-priority Redis connection with configurable TTL (default: 10 seconds) and interval (default: 3 seconds).

- `__init__.py`
  - Package marker — currently empty.


High-level runtime flow
-----------------------

### 1. User Uploads Task Logic
- User calls `POST /tasks/upload_file?file_name=process_data` with a Python file containing a `handler(payload)` function.
- API saves the file to `worker/tasks/process_data.py` (shared volume accessible by all workers).
- File can be `def handler(payload)` or `async def handler(payload)` — workers auto-detect.

### 2. User Creates Task
- User calls `POST /tasks/` with `{"title": "process_data", "payload": {...}, "priority": "low"}`.
- API validates that `worker/tasks/process_data.py` exists before creating the task.
- Task is created in PostgreSQL with status `PENDING` and a unique salted payload (`{"data": {...}, "_run_id": "uuid"}`).
- QueueManager schedules the task and pushes a message `{"task_id": <id>, "title": "process_data", "payload": {...}}` to the appropriate Redis queue (high or low priority).

### 3. Worker Claims Task
- Worker uses priority-based polling:
  1. First attempts atomic blocking move from **high-priority Redis** `default` → `processing:default` (using `BLMOVE` or fallback `BRPOPLPUSH`).
  2. If no high-priority tasks, attempts same from **low-priority Redis**.
- Updates task status to `IN_PROGRESS` in PostgreSQL via `update_task_status()`.

### 4. Dynamic Code Execution
- Worker calls `execute_dynamic_task(task_title, payload)` from `task_handler.py`:
  1. **Module loading**: Uses `importlib.util.spec_from_file_location()` to load `worker/tasks/{task_title}.py`.
  2. **Cache clearing**: Removes module from `sys.modules` to prevent stale code issues.
  3. **Handler extraction**: Retrieves the `handler` function from the module.
  4. **Async/Sync detection**: Uses `inspect.iscoroutinefunction()` to determine execution mode.
  5. **Execution**: Calls `await handler(payload)` or `handler(payload)` accordingly.

### 5. Result Handling
- **On success**: 
  - Updates task status to `COMPLETED` with `result=json.dumps(handler_return_value)` in PostgreSQL.
  - Removes message from `processing:default` queue.
- **On failure**:
  - Updates task status to `FAILED` with `result=str(exception)` in PostgreSQL.
  - Exception details are logged and stored for debugging.
  - Removes message from `processing:default` queue.

### 6. Autoscaling (KEDA)
- **KEDA ScaledObject** monitors Redis queue depth (both high and low priority queues).
- Workers auto-scale from **2 to 20 pods** based on queue length:
  - Queue depth > 10: Scale up
  - Queue empty: Scale down to minimum 2 replicas
- Each worker pod has access to the shared `worker/tasks/` volume (ReadWriteMany PVC).


Important implementation details
--------------------------------

- **Dynamic module loading with importlib**
  - Workers use `importlib.util.spec_from_file_location()` to dynamically import user-uploaded Python files at runtime.
  - **Cache management**: Before loading, workers clear `sys.modules[task_title]` to prevent executing stale code from previous runs.
  - **Error isolation**: If a task file has syntax errors or import failures, only that specific task fails—other tasks continue executing.

- **Async/Sync handler auto-detection**
  - Workers use `inspect.iscoroutinefunction(handler)` to detect if the user's handler is `async def` or `def`.
  - **Async handlers**: Executed with `await handler(payload)`.
  - **Sync handlers**: Executed directly as `handler(payload)`.
  - This allows users to write either synchronous or asynchronous task logic without configuration.

- **Dual-priority queue support**
  - Workers poll from **two separate Redis instances** (high and low priority).
  - **Priority logic**: Always check high-priority queue first; if empty, check low-priority queue.
  - Enables task prioritization without starving low-priority tasks.

- **Atomic Redis move**
  - We use `BLMOVE` if possible for an atomic blocking move from `default` to `processing:default`. If not available we use `BRPOPLPUSH` which provides similar semantics.
  - Storing in `processing:default` ensures that even if the worker dies between pop and DB claim, the payload is still in Redis and can be reclaimed by the QueueManager.

- **Shared persistent volume (ReadWriteMany PVC)**
  - In Kubernetes, `worker/tasks/` is mounted as a shared volume accessible by all worker pods and the API server.
  - This allows users to upload files via the API that are immediately available to all workers without image rebuilds.
  - **File lifecycle**: Files persist until manually deleted via `DELETE /tasks/delete_file` endpoint.

- **UUID payload salting**
  - Each task payload is salted with a unique `_run_id` UUID to prevent caching issues and enable task deduplication tracking.
  - Original payload: `{"data": {...}}`
  - Salted payload: `{"data": {...}, "_run_id": "550e8400-e29b-41d4-a716-446655440000"}`

- **Database-driven status tracking**
  - Task status transitions: `PENDING` → `IN_PROGRESS` → `COMPLETED`/`FAILED`.
  - Results/errors are stored in the `result` column (JSONB) for later inspection.
  - Workers use async SQLAlchemy sessions via `utils.update_task_status()`.

- **Reclaimer in QueueManager**
  - `processing:default` is scanned by the QueueManager `processing_reclaimer_loop`. It examines the DB row for each item and if the DB row isn't `IN_PROGRESS` and is older than a threshold, re-queues the payload into `default` and updates the DB row back to `QUEUED`.


Salient features
----------------

- **Dynamic code execution without rebuilds**: Upload Python files at runtime via API—no Docker image rebuilds or pod restarts required.
- **Function-as-a-Service (FaaS) model**: Workers act as a serverless execution engine for user-defined Python functions.
- **Intelligent async/sync detection**: Automatically detects and executes both `async def` and `def` handlers using `inspect.iscoroutinefunction()`.
- **Dual-priority queues**: Separate high/low priority Redis queues with fair polling strategy to prevent task starvation.
- **KEDA-based autoscaling**: Workers automatically scale from 2 to 20 pods based on real-time Redis queue depth.
- **Shared persistent storage**: ReadWriteMany PVC ensures all worker pods access the same task files without synchronization issues.
- **Module cache management**: Clears Python's `sys.modules` before each import to prevent stale code execution.
- **Reliable claim semantics**: Atomic Redis move into a `processing` list reduces race conditions and enables crash recovery.
- **Heartbeat + recovery**: The QueueManager monitors heartbeats and recovers tasks from dead workers.
- **Minimal dependency on Redis features**: Uses `BLMOVE` when available and falls back to `BRPOPLPUSH` for compatibility.
- **Comprehensive error handling**: Stores detailed error messages and stack traces in the database for debugging.


Known shortcomings and limitations
---------------------------------

- **Security: No code validation or sandboxing**
  - **Critical limitation**: User-uploaded code is executed directly without validation or sandboxing.
  - **Risk**: Malicious code can access the filesystem, make network requests, consume excessive resources, or compromise the worker pod.
  - **Mitigation plan**: See `CLI_ROADMAP.md` for proposed validation architecture with staging directories and sandbox pools (gVisor/Firecracker).
  - **Recommended for**: Trusted environments only (internal teams, controlled users).

- **No dependency management**
  - If a user's task requires third-party packages (e.g., `pandas`, `requests`), those packages must be pre-installed in the worker Docker image.
  - **Workaround**: Rebuild the worker image with additional dependencies in `requirements.txt`.
  - **Future enhancement**: Per-task virtual environments or container-per-task isolation.

- **Module namespace collisions**
  - If two users upload tasks with the same filename, the second upload overwrites the first.
  - **Current behavior**: Latest upload wins—no versioning or multi-tenancy.
  - **Mitigation**: User-specific namespaces (e.g., `worker/tasks/{user_id}/{task_name}.py`) could be implemented.

- **No retry logic in worker**
  - Unlike the original design with `retry_count` and exponential backoff, the current implementation marks tasks as `FAILED` immediately on error.
  - **Impact**: Transient errors (network timeouts, temporary DB unavailability) result in permanent failures.
  - **Future**: Re-implement retry scheduling with backoff via QueueManager (as outlined in the original architecture).

- **No task execution timeouts**
  - Workers will wait indefinitely for a task's `handler()` function to complete.
  - **Risk**: Infinite loops or long-running tasks can block worker processes.
  - **Mitigation**: Implement `asyncio.wait_for()` with configurable timeouts.

- **File cleanup is manual**
  - Uploaded task files persist indefinitely unless manually deleted via `DELETE /tasks/delete_file`.
  - **Impact**: Shared volume can grow unbounded with orphaned files.
  - **Original design note**: The docstring mentions "automatically deleted after execution," but this is not currently implemented.

- **Not using Redis Streams yet**
  - The current list-based approach works well and was chosen for simplicity, but Redis Streams + consumer groups provide stronger delivery semantics (pending-entry list, id-based acknowledgement) and richer tooling for production workloads.
  - **Consideration**: For high-throughput, ordering guarantees, or per-consumer pending management, consider migrating to Streams.

- **Reclaimer may be coarse**
  - The processing reclaimer scans the `processing` list and checks the DB row; this is sufficient for many cases, but can be slow if the list grows very large.
  - **Optimization**: Adding timestamps to messages or using per-worker processing lists can make reclamation more efficient.

- **Single-step claim relies on Postgres features**
  - The original atomic `UPDATE ... RETURNING` logic has been simplified to basic status updates.
  - If you change the DB backend you must adapt claim logic. Also ensure your SQLAlchemy + psycopg2 versions support async/await semantics.


How to run the worker locally (quick steps)
------------------------------------------

### Prerequisites:
- Python 3.11+/3.12
- Redis for both high and low priority queues (configured in `.env` via `REDIS_HOST_HIGH`/`REDIS_PORT_HIGH` and `REDIS_HOST_LOW`/`REDIS_PORT_LOW`)
- Postgres as configured by `DATABASE_URL` in `.env`
- Shared directory `worker/tasks/` accessible by both API and worker processes

### Start QueueManager (recommended)
Start the QueueManager in a terminal to ensure scheduled tasks are pushed and processing reclaimer runs:

```bash
python3 -m core.queue_manager
```

### Start a Worker
Start a worker in another terminal:

```bash
python3 -m worker.main
```

You should see logs like:
```
2026-01-19 19:43:00 - [Worker] - INFO - Async worker:a3f2d8e1 starting up on modular-worker branch...
2026-01-19 19:43:00 - [Worker] - INFO - Worker:a3f2d8e1 listening for dynamic tasks on Redis.
2026-01-19 19:43:00 - [Worker] - INFO - Started the heartbeat of the worker:a3f2d8e1 asyncronously
```

### Upload a Custom Task
Create a simple task file `hello_world.py`:

```python
# hello_world.py
async def handler(payload):
    name = payload.get("data", {}).get("name", "World")
    return {"message": f"Hello, {name}!"}
```

Upload it via the API:

```bash
curl -X POST "http://localhost:8080/tasks/upload_file?file_name=hello_world" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -F "file=@hello_world.py"
```

### Create and Execute the Task
Submit a task that uses the uploaded logic:

```bash
curl -X POST "http://localhost:8080/tasks/" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "title": "hello_world",
    "payload": {"name": "TaskFlow"},
    "priority": "low",
    "scheduled_at": 0
  }'
```

Watch the worker logs to see:
```
2026-01-19 19:43:15 - [Worker] - INFO - Worker:a3f2d8e1 processing Dynamic Task: 42
2026-01-19 19:43:15 - [Worker] - INFO - Task 42 COMPLETED successfully.
```

Query the task result:
```bash
curl -X GET "http://localhost:8080/tasks/42" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

Response:
```json
{
  "id": 42,
  "title": "hello_world",
  "status": "COMPLETED",
  "result": "{\"message\": \"Hello, TaskFlow!\"}"
}
```


Debugging tips
--------------

### General Debugging
- **Enable verbose logging**: Set `logging.basicConfig(level=logging.DEBUG)` in `worker/main.py` to see detailed import and execution logs.
- **Check worker heartbeat**: Run `redis-cli -h <HIGH_HOST> -p <HIGH_PORT> KEYS "worker:*:heartbeat"` to verify workers are alive.
- **Inspect queue contents**: If tasks disappear quickly, stop workers and run:
  ```bash
  redis-cli -h <HOST> -p <PORT> LRANGE default 0 -1
  redis-cli -h <HOST> -p <PORT> LRANGE processing:default 0 -1
  ```

### Dynamic Task Execution Issues
- **"File not found" error when creating task**:
  - Verify the file exists: `ls worker/tasks/your_task.py`
  - Check file permissions (must be readable by worker process)
  - In Kubernetes, verify the shared PVC is mounted correctly on both API and worker pods

- **"Missing 'handler' function" error**:
  - Ensure your `.py` file has a top-level `handler` function:
    ```python
    def handler(payload):  # or async def handler(payload):
        return {"result": "success"}
    ```
  - Common mistake: Defining handler inside a class or another function

- **Module import errors (e.g., "No module named 'pandas'")**:
  - The worker pod doesn't have the required dependency installed
  - **Solution**: Add the package to `requirements.txt` and rebuild the worker Docker image:
    ```bash
    make build-local
    make restart
    ```

- **Stale code executing after file update**:
  - Python's module cache was not cleared properly
  - **Verify**: Check `task_handler.py` has this line before importing:
    ```python
    if task_title in sys.modules:
        del sys.modules[task_title]
    ```
  - **Workaround**: Restart worker pods to clear all caches

- **Task stuck in IN_PROGRESS**:
  - Worker crashed mid-execution
  - Check worker logs for exceptions: `make logs` or `kubectl logs -n taskflow -l app=worker`
  - The QueueManager's reclaimer should eventually recover the task (check `processing:default` queue)

- **Async/sync execution errors**:
  - If you get `TypeError: object NoneType can't be used in 'await' expression`, you likely have:
    ```python
    def handler(payload):  # Missing async keyword
        await some_async_call()  # Can't await in sync function
    ```
  - **Fix**: Change to `async def handler(payload):`

### Kubernetes-Specific Issues
- **Workers not seeing uploaded files**:
  - Verify PVC is mounted: `kubectl exec -n taskflow deployment/worker -- ls /app/worker/tasks`
  - Check PVC access mode is `ReadWriteMany` (required for multiple pods)
  - Restart worker pods after upload if using `ReadWriteOnce`

- **Autoscaling not working**:
  - Verify KEDA is installed: `kubectl get scaledobject -n taskflow`
  - Check Redis queue metrics: `kubectl get --raw /apis/external.metrics.k8s.io/v1beta1`
  - See autoscaling test: `make autoscale-test`

### Performance Issues
- **Tasks processing slowly**:
  - Check if workers are at max capacity: `kubectl top pods -n taskflow -l app=worker`
  - Increase autoscaling max replicas in `k8s/06-autoscaling.yaml`
  - Verify database connection pool isn't exhausted (check PgBouncer logs)

- **Redis connection timeouts**:
  - If `BLMOVE`/`BRPOPLPUSH` raises "syntax error", your Redis version is too old (< 6.2 for BLMOVE)
  - Worker automatically falls back to `BRPOPLPUSH`, but check logs for warnings

- **OOM errors in worker pods**:
  - User task consumed too much memory
  - **Mitigation**: Increase worker memory limits in `k8s/04-worker.yaml`
  - **Long-term**: Implement per-task memory limits (requires sandboxing)

### Security Debugging
- **Suspicious task behavior**:
  - Check worker logs for unusual network activity or file access
  - Review uploaded files: `ls -la worker/tasks/`
  - **Remember**: Current implementation has NO sandboxing—any uploaded code runs with worker pod permissions
  - See `CLI_ROADMAP.md` for planned sandbox validation architecture



