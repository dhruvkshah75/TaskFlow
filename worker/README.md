# Worker — Task consumer for TaskFlow

This document explains the worker component located in the `worker/` folder. It describes what each file does, the runtime flow, important implementation details, salient features, known shortcomings, and how to run/debug the worker locally.

Files
-----

- `main.py`
  - Entry point for the async worker process.
  - Connects to the low-priority Redis instance via `core.redis_client.get_async_redis_client` and listens on a list-based queue named `default`.
  - Uses an atomic move from `default` to `processing:default` so payloads are not lost when a worker crashes after popping them. Implementation prefers `BLMOVE` (if supported) and falls back to `BRPOPLPUSH` for older Redis servers/clients.
  - After moving the payload into the processing list, it calls `TaskHandler.handle_task` and, when the handler returns, removes the payload from the processing list.
  - Starts and stops a `HeartbeatService` (see `heartbeat.py`) so the QueueManager can detect live workers.

- `task_handler.py`
  - Contains the `TaskHandler` class which performs the core claim → execute → finalize steps.
  - Claiming: the worker claims a task atomically in the database using an `UPDATE ... RETURNING` statement so `status`=IN_PROGRESS and `worker_id` are persisted in a single DB round-trip. This reduces races and ensures the `worker_id` column is populated reliably.
  - Execution: chosen handler (from `tasks.py`) is executed. The worker supports both sync and async handlers.
  - Finalization: on success the task is marked `COMPLETED`; on failure the task is either scheduled for retry (with an increasing backoff) or marked `FAILED` after `max_retries`.
  - Retry behavior: instead of immediately re-pushing failed tasks into Redis (which can cause tight retry loops), retries are scheduled via `scheduled_at` and the QueueManager's scheduler re-queues them when the timestamp arrives.
  - Auditing: `TaskEvents` rows are appended as the task transitions state. `TaskEvents.message` includes the worker id for traceability. Completed and failed tasks retain the `worker_id` so you can see who processed them.

- `tasks.py`
  - Small registry with example handlers and a `TaskResult` dataclass.
  - Contains example handlers (`dummy_handler` and `sync_echo_handler`) and a `HANDLERS` mapping used by the worker to find a handler for a task.
  - A `default` handler is provided and used when the payload doesn't contain a `type` and the task `title` doesn't match any key — this prevents immediate failures for you when creating dummy tasks.

- `heartbeat.py`
  - Runs a periodic async task that writes a short-lived key into Redis (for example `worker:<id>:heartbeat`).
  - The QueueManager checks heartbeats to decide if a worker is alive; if not, tasks claimed by that worker are candidates for recovery.

- `__init__.py`
  - Package marker — currently empty.


High-level runtime flow
-----------------------

1. QueueManager schedules tasks and pushes messages to Redis `default` queue. Each message is a JSON string with at least `{"task_id": <id>}`.
2. A worker uses an atomic blocking move to take messages off `default` into `processing:default`:
   - Prefer `BLMOVE default processing:default RIGHT LEFT timeout` (atomic).
   - Fallback to `BRPOPLPUSH default processing:default timeout` if `BLMOVE` is not available.
3. The worker claims the task in Postgres using an atomic UPDATE ... RETURNING that sets `status=IN_PROGRESS` and `worker_id=<worker_id>` and returns the payload/title.
4. Worker finds a handler from `tasks.HANDLERS` (or falls back to `default`) and runs it (async or sync).
5. On handler completion:
   - If successful: update `tasks` row to `COMPLETED` and create a `TaskEvents` row with EventType.COMPLETED. The `worker_id` is preserved for audit.
   - If failed: increment `retry_count`. If `retry_count <= max_retries` schedule the next attempt by setting `scheduled_at = now + backoff` (min(60, 5 * retry_count) seconds). If `retry_count > max_retries` mark `FAILED`. In both cases append a `TaskEvents` row that includes the worker id.
6. The worker removes the payload from `processing:default` once the handler has returned. (This avoids duplicates and ensures the reclaimer logic works.)


Important implementation details
--------------------------------

- Atomic DB claim
  - The claim uses `UPDATE ... RETURNING` on the `tasks` table to atomically set `IN_PROGRESS` + `worker_id` and fetch the payload/title in one round-trip. This avoids select-then-update races and ensures `worker_id` is persisted.

- Atomic Redis move
  - We use `BLMOVE` if possible for an atomic blocking move from `default` to `processing:default`. If not available we use `BRPOPLPUSH` which provides similar semantics.
  - Storing in `processing:default` ensures that even if the worker dies between pop and DB claim, the payload is still in Redis and can be reclaimed.

- Reclaimer in QueueManager
  - `processing:default` is scanned by the QueueManager `processing_reclaimer_loop`. It examines the DB row for each item and if the DB row isn't `IN_PROGRESS` and is older than a threshold, re-queues the payload into `default` and updates the DB row back to `QUEUED`.

- Retry scheduling vs immediate requeue
  - To avoid tight retry loops (task pushed → worker picks → failure → pushed back immediately → worker picks again), we schedule retries via `scheduled_at`. The QueueManager will re-push tasks when `scheduled_at <= now`.

- Worker id preservation
  - Completed and Failed tasks preserve the `worker_id` so audits show who processed the task.


Salient features
----------------

- Reliable claim semantics: atomic DB `UPDATE ... RETURNING` + atomic Redis move into a `processing` list reduces race conditions.
- Configurable backoff and retry logic: retries are scheduled with an increasing backoff (configurable later via Settings).
- Heartbeat + PEL (partial) recovery: the QueueManager monitors heartbeats and recovers tasks from dead workers.
- Minimal dependency on Redis features: uses `BLMOVE` when available and falls back to `BRPOPLPUSH` for compatibility.
- Out-of-the-box demo handlers: `dummy` and `echo` handlers let you run the worker without adding custom code.


Known shortcomings and limitations
---------------------------------

- Not using Redis Streams yet
  - The current list-based approach works well and was chosen for simplicity, but Redis Streams + consumer groups provide stronger delivery semantics (pending-entry list, id-based acknowledgement) and richer tooling for production workloads. If you need high-throughput, ordering guarantees, or per-consumer pending management, consider migrating to Streams.

- Reclaimer may be coarse
  - The processing reclaimer scans the `processing` list and checks the DB row; this is sufficient for many cases, but can be slow if the list grows very large. Adding timestamps to messages or using per-worker processing lists can make reclamation more efficient.

- Single-step claim relies on Postgres features
  - Atomic `UPDATE ... RETURNING` is Postgres-specific. If you change the DB backend you must adapt claim logic. Also ensure your SQLAlchemy + psycopg2 versions support returning() semantics.

- Worker-side retries currently use a simple backoff
  - The backoff formula is simple (min(60, 5 * retry_count)). You may want exponential backoff with jitter for production.

- Event schema is lightweight
  - `TaskEvents.message` stores a short string that includes worker id and an error message. For large task outputs, offload to object storage and store a pointer/summary in the DB instead of long text blobs.


How to run the worker locally (quick steps)
------------------------------------------

Prerequisites:
- Python 3.11+/3.12
- Redis for low-priority queue (configured in `.env` via `REDIS_HOST_LOW` / `REDIS_PORT_LOW`)
- Postgres as configured by `DATABASE_URL` in `.env`

Start QueueManager (recommended) in a terminal to ensure scheduled tasks are pushed and processing reclaimer and PEL scanner run:

```bash
python3 -m core.queue_manager
```

Start a worker in another terminal:

```bash
python3 -m worker.main
```

Create tasks using the API or insert into the `tasks` table and watch the worker logs. If you stop the worker and push a task, you can inspect the message with `redis-cli -p <LOW_PORT> LRANGE default 0 -1`.


Debugging tips
--------------

- If you see items disappear from `default` quickly, that is normal: workers pop items from Redis very fast. Stop the worker and push a task to inspect the queue.
- If `worker_id` remains NULL, make sure your DB claim code is the updated version that uses `UPDATE ... RETURNING`. Confirm a successful commit by checking task `updated_at` and `status`.
- If you see repeated immediate retries (tight loop) ensure your code uses `scheduled_at` backoff rather than immediate re-push.
- If Redis raises "syntax error" for `BLMOVE`, your server version likely doesn't support the command; the worker falls back to `BRPOPLPUSH` automatically.



