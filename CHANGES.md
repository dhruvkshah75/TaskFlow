# Roadmap for Modular Worker Task File Validation

This document outlines the proposed changes to implement a more secure and scalable task file validation mechanism, addressing the risk of directly executing user-uploaded code. The core idea is to introduce a sandbox pool for testing task files before they are made available to the main worker cluster.

## 1. Core Architectural Changes

### 1.1 Staging Directory for Uploaded Files
*   **Current:** User-uploaded task files (`.py`) are directly saved to `worker/tasks`.
*   **Proposed:** Introduce an `UPLOAD_STAGING_DIR` where all uploaded task files will initially reside. This directory will be separate from `worker/tasks` and will not be directly accessible by the main worker process until validation is complete.
*   **Configuration:** Add `UPLOAD_STAGING_DIR` to `core/config.py` (e.g., `/app/temp_task_uploads`).

### 1.2 Task Validation Queue
*   **Current:** No explicit validation queue.
*   **Proposed:** When a file is uploaded to the `UPLOAD_STAGING_DIR`, a message will be pushed to a dedicated Redis queue, e.g., `task_validation_queue`. This message will contain metadata about the uploaded file (e.g., staging path, original filename, user ID, a unique validation ID).
*   **Configuration:** Add `TASK_VALIDATION_QUEUE_NAME` to `core/config.py`.

### 1.3 Dedicated Validation Worker/Service
*   **Current:** No dedicated validation logic.
*   **Proposed:** Implement a new worker process or enhance an existing one (e.g., `worker/main.py`) to consume messages from the `task_validation_queue`.
    *   This worker will be responsible for orchestrating the validation process.
    *   **Sandbox Integration (Conceptual):** The validation worker will interact with a pool of isolated sandbox environments (e.g., using `gVisor` or `Firecracker`). The actual creation and management of these sandbox containers are outside the immediate scope of this roadmap but are crucial for the long-term solution. For initial implementation, a simpler mock sandbox or a basic `subprocess` with strict resource limits can be considered.
    *   **Execution in Sandbox:** The uploaded task file will be mounted into a sandbox container and executed with predefined test payloads or dummy data.
    *   **Monitoring & Analysis:** The sandbox execution will be monitored for:
        *   Resource limits (CPU, memory, execution time).
        *   Forbidden system calls or suspicious activities.
        *   Expected output/behavior for basic functionality tests (e.g., checking for the `handler` function).
    *   **Result Reporting:** The validation worker will report the outcome of the validation (safe/unsafe) and store it in the database or another Redis key for the user to query.

### 1.4 File Promotion (Safe Files)
*   **Current:** Files are immediately available to workers.
*   **Proposed:** If the validation worker determines a task file is "safe," it will move the file from `UPLOAD_STAGING_DIR` to `worker/tasks`, making it available for subsequent task execution.
*   **Cleanup:** Staging files will be cleaned up after validation (moved or deleted if unsafe).

## 2. API Modifications

### 2.1 `POST /tasks/upload_file` Endpoint
*   **Current:** Saves file directly to `worker/tasks`.
*   **Proposed:**
    1.  Save the uploaded file to the `UPLOAD_STAGING_DIR`.
    2.  Enqueue a message to the `task_validation_queue` with details about the file.
    3.  Return an initial response indicating that the file has been received and is pending validation, perhaps including a `validation_id`.

### 2.2 `POST /tasks/` (Create Task) Endpoint
*   **Current:** Checks `os.path.exists(f"worker/tasks/{task.title}.py")`.
*   **Proposed:** Before creating a task, verify that the corresponding `.py` file has successfully passed validation and has been moved to the `worker/tasks` directory. This might involve:
    *   Querying the database for the validation status associated with the `task.title`.
    *   Waiting for a specific event or status update indicating readiness.
    *   If the file is not yet validated and moved, return a `404 NOT FOUND` or `412 PRECONDITION FAILED` error.

### 2.3 New Endpoint: `GET /tasks/validation_status/{validation_id}` (Optional but Recommended)
*   **Proposed:** Allow users to query the status of their uploaded task file validation using the `validation_id` returned by the `upload_file` endpoint. This could return `PENDING`, `VALIDATED`, `REJECTED`, along with any relevant messages.

## 3. Worker (`worker/main.py`, `worker/task_handler.py`) Adjustments

*   **Task Loading:** The `worker/loader.py` will continue to load files from `worker/tasks` but will implicitly rely on the fact that only validated files exist there.
*   **Heartbeat/Monitoring:** The existing heartbeat mechanism will continue, but the validation worker will also need its own health checks.

## 4. Database Changes (Optional, but useful for tracking)

*   Consider adding a `task_files` table to track uploaded files, their `validation_id`, `status` (pending, validated, rejected), and a reference to the `user_id`. This would allow for persistent tracking and querying of validation outcomes.

## 5. Security Enhancements

*   **Resource Limits:** Implement strict CPU, memory, and time limits for sandbox execution.
*   **Network Isolation:** Sandboxes should have minimal to no network access unless explicitly required and carefully controlled.
*   **Filesystem Restrictions:** Sandboxes should only have access to their designated working directories and the task file itself, preventing access to sensitive system files.
*   **System Call Filtering:** Utilize `seccomp` or similar mechanisms to restrict dangerous system calls.

## 6. Scalability Considerations

*   **Sandbox Pool Management:** Implement a robust mechanism to manage a pool of reusable sandbox containers (e.g., 5-10 pre-warmed containers). This reduces the overhead of creating new sandboxes for each validation request.
*   **Queue-based Processing:** The Redis queue ensures that validation requests are processed asynchronously and can handle bursts of uploads without overwhelming the sandbox pool.
*   **Horizontal Scaling:** The validation worker itself should be horizontally scalable, allowing multiple instances to consume from the `task_validation_queue` in parallel.

## 7. Development Steps (High-Level)

1.  Update `core/config.py` with new settings.
2.  Modify `api/routers/tasks.py` for `upload_file` to stage files and enqueue messages.
3.  Implement a basic "validation" function in a new worker (or part of `worker/main.py`) that consumes from the queue, performs minimal checks (e.g., checks for `async def handler`), and moves safe files.
4.  Adjust `api/routers/tasks.py` for `create_task` to check for validated files.
5.  (Optional) Add database schema for task file validation status.
6.  (Future) Integrate with actual sandbox technologies like `gVisor` or `Firecracker` for true isolation.
7.  Add comprehensive unit and integration tests for the new validation flow.
