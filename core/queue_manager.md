
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
