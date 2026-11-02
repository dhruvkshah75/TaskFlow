(() => {
  const root = "https://github.com/dhruvkshah75/TaskFlow/blob/main/";
  const components = {
    client: {
      label: "PRODUCER",
      name: "Your client",
      description:
        "The TaskFlow CLI or a REST client uploads Python handlers, submits tasks with a payload, and queries execution status.",
      source: "taskflow_cli/taskflow/cli.py",
    },
    api: {
      label: "ENTRY POINT",
      name: "FastAPI",
      description:
        "Authenticates requests, accepts Python file uploads, and persists submitted tasks in PostgreSQL. Dispatch is handled by the queue manager.",
      source: "api/routers/tasks.py",
    },
    database: {
      label: "PERSISTENCE",
      name: "PostgreSQL",
      description:
        "Stores task metadata, schedule, priority, worker identity, and execution status. PgBouncer pools the connections used by the API, queue manager, and workers.",
      source: "core/models.py",
    },
    manager: {
      label: "COORDINATION",
      name: "Queue manager",
      description:
        "The leased leader polls for due tasks every 5 seconds and dispatches them to the Redis instance matching their priority. Recovery loops inspect worker heartbeats and reconcile queued tasks.",
      source: "core/queue_manager.py",
    },
    high: {
      label: "PRIORITY QUEUE",
      name: "Redis · high",
      description:
        "Holds high priority tasks. Workers check this queue before the low priority queue. This Redis instance also holds worker heartbeats, leadership leases, and rate limiting data.",
      source: "core/redis_client.py",
    },
    low: {
      label: "BULK QUEUE",
      name: "Redis · low",
      description:
        "Holds low priority tasks in the default list. KEDA measures the depth of this queue to scale the shared worker deployment.",
      source: "core/redis_client.py",
    },
    worker: {
      label: "EXECUTION",
      name: "Python workers",
      description:
        "Moves a message atomically to a processing list, records IN_PROGRESS, and executes the uploaded handler. On completion or error, it records status and removes the processing message.",
      source: "worker/main.py",
    },
    keda: {
      label: "AUTOSCALING",
      name: "KEDA",
      description:
        "Observes the low priority Redis list every 2 seconds and scales the Kubernetes worker deployment from 2 to 20 replicas. The configured list length target is 5.",
      source: "k8s/autoscaling/worker-scaledobject.yaml",
    },
  };
  function selectComponent(key) {
    const component = components[key];
    document
      .querySelectorAll("[data-component]")
      .forEach((button) =>
        button.setAttribute(
          "aria-pressed",
          String(button.dataset.component === key),
        ),
      );
    document.getElementById("component-label").textContent = component.label;
    document.getElementById("component-name").textContent = component.name;
    document.getElementById("component-description").textContent =
      component.description;
    document.getElementById("component-source").href = root + component.source;
  }
  document
    .querySelectorAll("[data-component]")
    .forEach((button) =>
      button.addEventListener("click", () =>
        selectComponent(button.dataset.component),
      ),
    );
  const steps = [
    {
      kicker: "01 / Shared code, ready to run",
      title: "Your code has a home.",
      description:
        "Upload a Python file with a handler(payload) function. The API and workers share the task files volume, so workers can load new code without an image rebuild.",
      code: "async def handler(payload):\n    return await process(payload)",
      state: "FILE READY",
      component: "api",
    },
    {
      kicker: "02 / A task becomes a record",
      title: "Tell the system what to run.",
      description:
        "Submit a task title matching the Python filename, a payload, a priority, and a schedule delay. The API creates a PENDING task in PostgreSQL.",
      code: 'POST /tasks/\n{ "title": "process_data",\n  "payload": { "batch": 42 },\n  "priority": "low", "scheduled_at": 0 }',
      state: "PENDING",
      component: "database",
    },
    {
      kicker: "03 / The scheduler takes over",
      title: "The right queue. At the right time.",
      description:
        "Every 5 seconds, the leading queue manager claims due tasks from PostgreSQL. It pushes each message to the high or low priority Redis instance, then marks the task QUEUED.",
      code: "PostgreSQL: due PENDING tasks\n        ↓\nRedis: RPUSH default <task message>\n        ↓\nPostgreSQL: QUEUED",
      state: "QUEUED",
      component: "manager",
    },
    {
      kicker: "04 / Python does the work",
      title: "A worker picks up the thread.",
      description:
        "Workers check the high priority queue first. BRPOPLPUSH moves a message into a processing list. The worker records its identity and IN_PROGRESS status, then loads and executes the Python handler.",
      code: "default → processing:default\n\nload_task_handler(task_title)\nawait execute_dynamic_task(title, payload)",
      state: "IN_PROGRESS",
      component: "worker",
    },
    {
      kicker: "05 / The outcome is recorded",
      title: "You can follow what happened.",
      description:
        "A successful execution is marked COMPLETED; an exception is marked FAILED. The worker removes the processing message. The current implementation stores status, not the handler’s returned value.",
      code: "PostgreSQL: COMPLETED / FAILED\nRedis: remove processing message\n\nGET /tasks/{task_id}",
      state: "COMPLETED / FAILED",
      component: "database",
    },
  ];
  document.querySelectorAll("[data-step]").forEach((button) =>
    button.addEventListener("click", () => {
      const step = steps[Number(button.dataset.step)];
      document
        .querySelectorAll("[data-step]")
        .forEach((item) =>
          item.setAttribute("aria-pressed", String(item === button)),
        );
      for (const [id, key] of [
        ["journey-kicker", "kicker"],
        ["journey-title", "title"],
        ["journey-description", "description"],
        ["journey-code", "code"],
        ["journey-state", "state"],
      ])
        document.getElementById(id).textContent = step[key];
      selectComponent(step.component);
    }),
  );
  const pause = document.getElementById("map-pause");
  pause.addEventListener("click", () => {
    const paused = pause.getAttribute("aria-pressed") !== "true";
    pause.setAttribute("aria-pressed", String(paused));
    pause.textContent = paused ? "Play" : "Pause";
    document
      .querySelector(".system-map")
      .classList.toggle("map-paused", paused);
  });
})();
