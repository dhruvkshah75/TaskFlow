
# Queue Manager Documentation

## Overview
The Queue Manager serves as the central nervous system of TaskFlow. It bridges the gap between the Database (PostgreSQL) and the Message Broker (Redis). Unlike simple task queues, it actively manages the lifecycle of tasks, ensuring reliability, scheduling, and fault tolerance.


## Key Responsibilities
1.  **Task Dispatching (Client Interface):** Provides the `push_task` function used by the API to send jobs to Redis.
2.  **Leader Election:** Coordinates multiple manager instances to ensure only one is active (the "Leader") at any time, preventing duplicate scheduling or cleanup.
3.  **Task Scheduling:** Monitors the database for tasks marked `SCHEDULED` whose execution time has arrived and promotes them to `PENDING` (pushes to Redis).
4.  **Fault Recovery ("The Janitor"):** Monitors active tasks (`IN_PROGRESS`). If a task remains in this state for too long (indicating a worker crash), it resets the task to `PENDING` for another worker to pick up.

---

## Detailed Workflow

**1. Leader Election (High Availability)**
The Queue Manager uses a Redis-backed locking mechanism to elect a single leader. This prevents race conditions (e.g., two managers trying to schedule the same task twice).

* **Acquisition:** Each instance tries to set a specific key (`taskflow:leader`) in Redis using `SET NX` (Set if Not Exists) with a short TTL (Time-To-Live).
* **Renewal:** The elected leader runs a background thread that periodically "renews" this lease (extends the TTL) using a Lua script to ensure atomicity.
* **Failover:** If the leader crashes, it stops renewing the lease. Redis deletes the key after the TTL expires (10 seconds). Another standby instance then acquires the lock and becomes the new leader.

**2. The Scheduler Loop**
This loop runs every 5 seconds (configurable) and handles delayed execution.

1.  **Query:** It checks the `Tasks` table for rows where `status='SCHEDULED'` AND `scheduled_at <= NOW()`.
2.  **Transaction:** For each task found:
    * Updates status to `PENDING` in the database.
    * Calls `push_task` to send the task payload to the appropriate Redis queue (High/Low priority).
    * Commits the transaction.
3.  **Result:** The task becomes visible to workers immediately.

**3. The Recovery Loop (Janitor)**
This loop runs every 10 seconds to handle worker failures.

1.  **Detection:** It queries the `Tasks` table for rows where `status='IN_PROGRESS'` AND `updated_at < (NOW() - 5 minutes)`. This implies the worker picked up the task but stopped updating it (likely crashed).
2.  **Decision:**
    * **Retry:** If the task's `retry_count < MAX_RETRIES` (3), it resets the status to `PENDING`, increments the retry count, and pushes it back to Redis.
    * **Fail:** If the retry limit is reached, it marks the task as `FAILED` and logs an error.
3.  **Result:** Tasks are never lost, even if the infrastructure fails.

**4. Queue Sharding (Priority Support)**
The `push_task` function supports routing based on priority.
* **High Priority:** Critical tasks are sent to the `redis_high` instance.
* **Low Priority:** Bulk tasks are sent to the `redis_low` instance.
This ensures that critical operations (like sending an OTP) aren't blocked by a massive backlog of non-critical tasks (like generating reports).

---



---

## `Scheduler_loop` LOGIC

this function is a leader-only scheduler that finds *due* tasks in the DB, pushes them to Redis, and marks them as `QUEUED` in the DB. Below I walk through it step-by-step, explain why each part is there, point out important SQLAlchemy/DB semantics, and call out caveats and suggestions.

---

## Purpose

* Run periodically (leader only) to move tasks from `PENDING` → `QUEUED`.
* Only touches a small batch of tasks per iteration to avoid scanning the whole table.
* Ensures multiple scheduler instances can run safely without double-processing rows.

---

## High-level flow

1. Wait until this process is the current *leader*.
2. Open a DB session.
3. Query up to 100 `PENDING` tasks whose `scheduled_at` ≤ now, ordered by `scheduled_at`.
4. Lock rows with `FOR UPDATE SKIP LOCKED` to avoid races with other schedulers.
5. For each candidate:

   * Push a JSON payload (`{"task_id": id}`) to Redis via `push_task`.
   * Collect IDs that were successfully pushed.
6. Batch-update the DB for all successfully queued IDs to set `status = QUEUED` and `updated_at = now`.
7. Commit (or rollback if nothing queued or an error).
8. Close session and sleep until the next iteration.

---

## Line-by-line / block explanation

### Leadership check

```py
if not self.is_leader:
    time.sleep(SCHEDULER_INTERVAL_S)
    continue
```

* The scheduler only runs when the instance holds leadership (avoids duplicate work). Non-leaders sleep and skip the heavy work.

### Session and candidate selection

```py
db = SessionLocal()
now = datetime.now(timezone.utc)

candidates = (
    db.query(Tasks)
      .filter(Tasks.status == TaskStatus.PENDING,
              Tasks.scheduled_at != None,
              Tasks.scheduled_at <= now)
      .order_by(Tasks.scheduled_at.asc())
      .limit(100)
      .with_for_update(skip_locked=True)
      .all()
)
```

* `filter(...)` finds only pending tasks that are due.
* `order_by(Tasks.scheduled_at.asc())` is index-friendly if you have an index on `(status, scheduled_at)`.
* `limit(100)` bounds batch size so it doesn’t fetch thousands per run.
* `with_for_update(skip_locked=True)` issues `SELECT ... FOR UPDATE SKIP LOCKED`:

  * **FOR UPDATE** locks each returned row so another transaction cannot claim it concurrently.
  * **SKIP LOCKED** means if another scheduler already locked a row, that row is skipped (no blocking). Great for multiple-process concurrency.

### No candidates short path

```py
if not candidates:
    db.close()
    time.sleep(SCHEDULER_INTERVAL_S)
    continue
```

* If nothing to do, close the session and sleep. Closing early avoids holding DB resources.

### Push to Redis and collect successes

```py
queued_ids = []
for task in candidates:
    payload = {"task_id": task.id}
    priority = getattr(task, "priority", "low") or "low"
    success = push_task("default", payload, priority=priority)
    if success:
        queued_ids.append(task.id)
    else:
        logger.error(...)
```

* `push_task` pushes a JSON string into the Redis queue; it returns `True` on success.
* Only tasks that were actually pushed to Redis are collected for DB update. That avoids showing tasks as queued if Redis push failed.

### Batch DB update

```py
if queued_ids:
    now_upd = datetime.now(timezone.utc)
    db.query(Tasks).filter(Tasks.id.in_(queued_ids)).update(
        { Tasks.status: TaskStatus.QUEUED, Tasks.updated_at: now_upd },
        synchronize_session=False
    )
    db.commit()
```

* Uses a single `UPDATE ... WHERE id IN (...)` for all queued IDs — much faster than per-row updates.
* `synchronize_session=False` tells SQLAlchemy not to try to keep in-memory ORM objects in sync (good for performance when you close the session anyway).
* `db.commit()` persists the status changes and releases row locks.

### Rollback on nothing queued

```py
else:
    db.rollback()
```

* If nothing was queued (e.g., Redis failure for every candidate), rollback to release the FOR UPDATE locks.

### Exception handling and cleanup

```py
except Exception as e:
    logger.error(...)
    db.rollback()
finally:
    try: db.close()
    except: pass
```

* On any exception, a rollback occurs and the session is closed in `finally` to avoid leaking connections.

### Sleep & loop

```py
time.sleep(SCHEDULER_INTERVAL_S)
```

* Throttles the polling frequency.

---

## Important semantics & concurrency notes

* **Locking window**: You hold DB row locks from the `SELECT FOR UPDATE` until you `commit()` or `rollback()`. During that time the rows are reserved — that prevents two schedulers from queueing same task. Keep the work done while holding the lock small (this code pushes to Redis while holding the lock; that’s generally OK but increases lock duration).
* **Push-first then update**: The code pushes to Redis while holding the DB lock, then does a single DB update and commits. If the process crashes after pushing to Redis but before updating DB, the only harm: Redis contains the task but DB still shows `PENDING`. You’d have a duplicate processing risk if a worker uses DB state; in your pattern workers read from Redis so it's likely fine. If you require strict atomicity (no risk of dupes), consider a different pattern (see suggestions).
* **synchronize_session=False**: Good for bulk update performance; but ORM instances in that session (like `candidates`) are not updated to reflect the new DB values. You close the session immediately so that's fine.

---

## Caveats & potential issues

1. **Lock duration**: Pushing to Redis inside the lock extends lock time. If Redis is slow/unreachable, other schedulers might skip these rows because they remain locked. If Redis latency is a concern, consider:

   * Remove push from inside lock: record `to_queue` then release locks and push. But that opens a race.
   * Use a short lock + use an atomic Redis Lua script / separate scheduled index (Redis ZSET) — see suggestions below.

2. **Small atomicity gap**: There is a small window between pushing to Redis and updating DB. If process dies in that window, the item is in Redis but DB is still `PENDING`. Usually acceptable if workers rely on Redis only.

3. **Enum mapping**: Ensure `TaskStatus.QUEUED` maps correctly to DB enum value. Otherwise use raw string `'QUEUED'` in update.

4. **Batch size tuning**: `limit(100)` is arbitrary — tune to throughput and worker speed.

5. **DB scaling**: This approach is OK with a proper index. If your system needs to schedule millions of jobs, consider moving scheduling metadata into Redis (ZSET) and only touch DB for status updates.

---

## Suggested improvements (short list)

* **Verify index usage** with `EXPLAIN ANALYZE` and ensure an index on `(status, scheduled_at)`.
* **Add monitoring** (counts: scanned, queued, push failures).
* **Consider Redis ZSET schedule**:

  * Keep `scheduled:<priority>` ZSET with score = timestamp.
  * Scheduler pops due IDs from ZSET (atomic via Lua), pushes to queue, then marks DB — avoids DB scans.
* **(Optional)** Push to Redis via a small Lua script that returns success/failure quickly, reducing time inside DB locks.
* **Retry & backoff**: On Redis push failure, add limited retry with exponential backoff rather than immediate rollback for the whole batch.
* **Idempotency**: Ensure workers handle possible duplicate `task_id` gracefully.

---

## Tests to run

1. Create many `PENDING` tasks and run `EXPLAIN ANALYZE` on the query to confirm it uses the index.
2. Start 2 schedulers concurrently and confirm each task is queued only once (inspect Redis and DB).
3. Simulate Redis outage: tasks should remain `PENDING` (not marked `QUEUED`) and locks should not be held too long.
4. Measure scheduler latency (time from scheduled_at to actual queue push) and tune `SCHEDULER_INTERVAL_S` and `limit`.

---


