# core — shared infrastructure for TaskFlow

This folder contains low-level, reusable components used across the API, worker, and queue manager processes.

Contents
--------

- `config.py` — application settings (Pydantic `BaseSettings`).
  - `settings` object exposes values loaded from `.env` (for example `DATABASE_URL`, Redis host/ports, JWT secret, heartbeat interval, rate limits).
  - Use `from core.config import settings` to access configuration values across the codebase.

- `database.py` — SQLAlchemy database bindings and session helpers.
  - `engine` — the synchronous SQLAlchemy Engine (used by scripts or sync code).
  - `SessionLocal` — sync session factory (typical FastAPI dependency via `get_db`).
  - `Base` — declarative base for model classes (imported by `models.py`).
  - `get_db()` — generator dependency that yields a `SessionLocal` instance and closes it afterwards. Use in sync FastAPI routes:

    ```py
    from core.database import get_db

    def my_route(db = Depends(get_db)):
        # db is a sqlalchemy Session
        ...
    ```

  - `async_engine` and `AsyncSessionLocal` — the async engine and session factory built with `asyncpg` for async workers and background tasks.
    - Use `AsyncSessionLocal()` to create async sessions and call `await session.commit()` / `await session.execute(...)` etc.

- `models.py` — SQLAlchemy ORM models and enums.
  - Models included:
    - `User` — basic user table (id, email, username, password, created_at).
    - `Tasks` — core task table (id, title, payload, priority, owner_id, status, created_at, worker_id, retry_count, scheduled_at, updated_at) with relationships to `User` and `TaskEvents`.
    - `TaskEvents` — audit trail for task lifecycle events (event_type, message, created_at).
    - `ApiKey` — stored API key hashes and metadata (owner, created_at, is_active, last_used_at, expires_at).
    - `Webhook` — small table to register callback URLs for events.
  - Enums (SQLAlchemy `Enum` columns): `TaskStatus`, `EventType`, `PriorityType`.
  - Note: When changing enum values or enum types, be careful with Alembic migrations — Postgres enum types require special handling (see `alembic/` folder).

- `redis_client.py` — helpers for Redis connections.
  - `redis_high` and `redis_low` — two synchronous `redis.Redis` clients configured from settings for high- and low-priority uses.
  - `get_redis_client(priority: str = "low") -> redis.Redis` — select the appropriate sync client.
  - `get_redis()` — convenience dependency that returns the high-priority client (used in FastAPI for rate-limiting and auth-critical paths).
  - `get_async_redis_client(priority: str = "low") -> aioredis.Redis` — small helper that creates and returns an async redis client (calls `aioredis.from_url(...)`).

- `queue_manager.py` — leader/scheduler that scans DB and pushes tasks into Redis queues.
  - Responsibilities (typical design):
    - Leader election (e.g. via Redis SET NX + TTL) so one instance performs scheduling.
    - Scheduler loop: periodically select tasks with `scheduled_at <= now()` and move them to Redis queues (set DB status to `QUEUED` or `PENDING` as appropriate) and write `TaskEvents` entries.
    - PEL / stuck-task scanner: find `IN_PROGRESS` tasks without recent heartbeats and either re-queue them or mark them failed after retries exhausted.
    - Routing by `priority` into different Redis instances/queues (use `get_redis_client` in this module to pick `redis_high` or `redis_low`).

Usage notes
-----------

- Environment / settings
  - Provide a `.env` (root of repo) with at least the following values used by `core.config.Settings`:
    - `DATABASE_URL` — Postgres connection string (e.g. `postgresql://user:pass@host:5432/dbname`).
    - `REDIS_HOST_HIGH`, `REDIS_PORT_HIGH`, `REDIS_HOST_LOW`, `REDIS_PORT_LOW` — Redis instances for high and low priority traffic.
    - `SECRET_KEY`, `ALGORITHM`, `ACCESS_TOKEN_EXPIRE_MINUTES` — JWT/Auth settings used by the API.
    - `HEARTBEAT_INTERVAL_SECONDS` — how often workers send heartbeats (QueueManager uses this to detect stuck tasks).

- Database migrations
  - The project uses Alembic (`alembic/`) for migrations. If you modify `models.py` (particularly enums or enum labels), update or create Alembic migrations carefully — Postgres enum types are global in the DB and may cause `type already exists` errors if migrations attempt to create the same enum twice.

- Sync vs Async
  - `database.py` exposes both sync (`SessionLocal`) and async (`AsyncSessionLocal`) tools. Use the sync session for API endpoints (FastAPI dependencies currently use `get_db()`), and prefer async sessions for long-running worker logic if you use async DB code.

- Redis
  - Keep `redis_high` dedicated to auth, rate-limiting, and low-latency user-facing operations so that heavy worker queues on `redis_low` do not impact auth performance.

