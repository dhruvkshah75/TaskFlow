**Serverless Function-as-a-Service (FaaS)** platform. 

### Roadmap: The "Serverless Task" Evolution

---

#### Phase 1: The "Pro" Upload Endpoint

You need a way to receive files and save them where the workers can find them. We will use `task_title` as the unique identifier for the script.

* **API Change:** Add a `POST /upload-task` endpoint.
* **Logic:**
1. Receive `UploadFile` via FastAPI.
2. Check if a task with this `task_title` already exists.
3. Save the file to a shared directory (e.g., `worker/tasks/{task_title}.py`).


* **Result:** The file `website_check.py` becomes available as a task titled `website_check`.

---

#### Phase 2: Title-Based Dynamic Execution

Modify the worker to stop looking for a "type" and start looking for a "file" matching the title.

* **Worker Change:** Update `TaskHandler`.
* **The "Protocol":** 1.  Worker sees `task_title: "p1"`.
2.  It looks for `worker/tasks/p1.py`.
3.  It dynamically imports `p1.py` and runs the `handler` function.
* **Safety Check:** If the file isn't there, the worker marks the task as **FAILED** with an error message: "Task logic file not found."

---

#### Phase 3: Bypassing Duplication via "Randomized Payload"

Since you have logic preventing duplicate tasks (same title + same payload), we will "salt" the payload for the user.

* **API Change:** In the `POST /tasks` endpoint, if a user sends a task, automatically inject a `request_id` or `timestamp` into the payload before saving to the DB.
* **Logic:**
```python
payload["_uid"] = str(uuid.uuid4()) # Makes every request unique

```


* **Result:** The user can call `p1` a hundred times in a row, and your "duplicate prevention" will see them as unique requests because of the hidden ID.

---

#### Phase 4: Automatic Cleanup (The Garbage Collector)

Once a task is finished, we want to delete the user's code to save space and keep the system clean.

* **Worker Change:** In the `finally` block of `handle_task`:
1. Check if the task is finished (`COMPLETED` or `FAILED`).
2. Identify the file: `worker/tasks/{task_title}.py`.
3. Delete the file using `os.remove()`.


* **Important:** This assumes the user uploads the file **every time** they want to run a task.

---

### Technical Architecture Diagram

### The New "User Experience" (The Cloud Workflow)

1. **Step 1 (Upload):** User uploads their logic.
```bash
curl -F "file=@myscript.py" http://api.taskflow.com/upload-task?title=p1

```


2. **Step 2 (Execute):** User triggers the task by title.
```bash
curl -X POST http://api.taskflow.com/tasks -d '{"task_title": "p1", "payload": {"data": "hello"}}'

```


3. **Step 3 (Cleanup):** The worker runs the code, saves the result to Postgres, and **deletes** `p1.py` from the disk.

### 📂 File Structure Changes

```text
TaskFlow/
├── api/
│   └── main.py          <-- Added POST /upload-task
├── worker/
│   ├── main.py
│   ├── loader.py        <-- Updated to load by Title
│   └── tasks/           <-- This folder now acts as a temporary cache
└── k8s/
    └── shared-pvc.yaml  <-- NEW: A Shared Volume so API and Worker see same files

```


Actually, no—and this is the "magic" of the architecture we are building. **The user does NOT need to build a new Docker image.**

If you forced a Docker build every time a user uploaded a script, the system would be incredibly slow. Imagine waiting 2 minutes for an image to build just to run a 5-second Python script.

Instead, we use **Dynamic Loading** and **Shared Volumes**. Here is how we avoid the "rebuild" entirely:

---

### 1. The "Pre-Baked" Engine

You build your Docker image **once**. This image contains:

* The Python runtime.
* The Redis and Database connection logic.
* Your `AsyncWorker` loop.
* Common libraries like `requests`, `pandas`, or `numpy` (the "standard library" for your platform).

### 2. The Shared Volume (The Bridge)

In the cloud (Kubernetes), we use a **Persistent Volume Claim (PVC)** with `ReadWriteMany` access.

* **The API** has this volume mounted at `/app/worker/tasks`. When a user uploads `p1.py`, the API writes it directly to this disk.
* **The Workers** also have this exact same volume mounted at `/app/worker/tasks`.
* Because they share the same disk, the moment the file is written by the API, it "appears" inside the running Worker containers instantly.

### 3. Dynamic Execution (The "Hot Swap")

Since Python is an interpreted language, we can use `importlib` (as shown in the previous code) to load that file while the worker is already running.

1. Worker stays alive 24/7.
2. Task arrives in Redis.
3. Worker sees the file on the shared disk.
4. Worker imports and runs it.
5. Worker deletes the file.

**No `docker build`, no `docker push`, no `kubectl rollout`. It is instantaneous.**

---

### When *would* you need a new image?

The only time you or the user would need to build a new image is if a user needs a **system-level dependency** that isn't already installed.

* *Example:* If a user wants to use `OpenCV` but you didn't include it in your worker's `requirements.txt`.
* *Solution:* As the platform owner, you periodically update the "Base Image" to include the most popular libraries requested by your users.

---

### 🛠️ The Kubernetes Configuration for this

To make this work in the cloud, you need this specific `shared-pvc.yaml`. This is what allows the "no-rebuild" flow:

```yaml
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: task-logic-pvc
spec:
  accessModes:
    - ReadWriteMany  # This allows both API and Workers to connect at once
  resources:
    requests:
      storage: 1Gi

```

In your **Deployment** files, you simply mount this:

```yaml
volumeMounts:
  - name: task-storage
    mountPath: /app/worker/tasks
volumes:
  - name: task-storage
    persistentVolumeClaim:
      claimName: task-logic-pvc

```

### 💡 Why this is better for you

* **Speed:** Tasks start executing in milliseconds after upload.
* **Cost:** Building Docker images in the cloud consumes huge amounts of CPU and storage.
* **Simplicity:** Your CI/CD pipeline only runs when *you* change the core engine, not when a user adds a task.

