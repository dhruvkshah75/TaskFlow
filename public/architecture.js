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
  // A self-contained illustrative workload: one clock drives traffic, queue depth,
  // worker capacity and completion counts. It never contacts a running cluster.
  const map = document.querySelector(".system-map");
  const pause = document.getElementById("map-pause");
  const reducedMotion = matchMedia("(prefers-reduced-motion: reduce)");
  const svg = map.querySelector("svg");
  const workerNode = map.querySelector(".node-worker");
  const pods = [...map.querySelectorAll(".node-pods i")];
  const fields = Object.fromEntries(
    [
      "high-queued",
      "low-queued",
      "map-worker-count",
      "keda-action",
      "simulation-phase",
      "simulation-queued",
      "simulation-workers",
      "simulation-completed",
    ].map((id) => [id, document.getElementById(id)]),
  );
  const routes = [
    ...svg.querySelectorAll(".map-edge:not(.map-edge-control)"),
  ].map((path) => {
    const length = path.getTotalLength();
    return Array.from({ length: 65 }, (_, index) =>
      path.getPointAtLength((length * index) / 64),
    );
  });
  const tasks = Array.from({ length: 160 }, (_, index) => {
    const packet = document.createElementNS(
      "http://www.w3.org/2000/svg",
      "circle",
    );
    const high = index % 8 === 0;
    packet.setAttribute("r", "3");
    packet.setAttribute("class", "edge-packet" + (high ? " priority" : ""));
    svg.append(packet);
    return { birth: 1.5 + index * 0.025, high, start: null, packet };
  });
  let elapsed = 0,
    workers = 2,
    nextPoll = 2,
    idleSince = null;
  let userPaused = false,
    inView = false,
    frame = null,
    previousTime = null;
  let accumulator = 0,
    previousPhase = "";
  const setText = (id, value) => {
    if (fields[id].textContent !== String(value))
      fields[id].textContent = value;
  };
  function reset() {
    elapsed = 0;
    workers = 2;
    nextPoll = 2;
    idleSince = null;
    tasks.forEach((task) => {
      task.start = null;
      task.packet.style.opacity = "0";
    });
  }
  function queue() {
    return tasks.filter(
      (task) => task.birth + 3 <= elapsed && task.start === null,
    );
  }
  function step() {
    elapsed += 0.1;
    if (elapsed >= 40) reset();
    const waiting = queue();
    const executing = tasks.filter(
      (task) => task.start !== null && elapsed < task.start + 2.4,
    );
    const outstanding = tasks.some(
      (task) =>
        task.birth + 3 > elapsed ||
        task.start === null ||
        elapsed < task.start + 3.2,
    );
    if (!outstanding) idleSince ??= elapsed;
    if (elapsed >= nextPoll) {
      nextPoll += 2;
      const target = Math.min(
        20,
        Math.max(2, Math.ceil(waiting.filter((task) => !task.high).length / 5)),
      );
      workers = Math.max(workers, target);
      if (idleSince !== null && elapsed - idleSince >= 4) workers = 2;
    }
    // Both queues share capacity; high priority messages are claimed first.
    waiting.sort(
      (a, b) => Number(b.high) - Number(a.high) || a.birth - b.birth,
    );
    waiting
      .slice(0, Math.max(0, workers - executing.length))
      .forEach((task, index) => (task.start = elapsed + index * 0.02));
  }
  function renderMetrics(high, low, completed, busy, phase) {
    setText("high-queued", high + " queued");
    setText("low-queued", low + " queued");
    setText("map-worker-count", workers);
    setText("simulation-workers", workers);
    setText("simulation-queued", high + low);
    setText("simulation-completed", completed);
    setText(
      "keda-action",
      workers === 2
        ? "baseline capacity"
        : idleSince !== null
          ? "cooling down"
          : "scaling capacity",
    );
    if (phase !== previousPhase) {
      setText("simulation-phase", phase);
      previousPhase = phase;
    }
    workerNode.classList.toggle("is-scaling", workers > 2);
    pods.forEach((pod, index) => {
      pod.classList.toggle("active", index < workers);
      pod.classList.toggle("busy", index < busy);
    });
  }
  // Resolve the shared cubic-bezier(.22,1,.36,1) curve for the sampled paths.
  function decelerate(progress) {
    let left = 0,
      right = 1;
    for (let i = 0; i < 10; i++) {
      const t = (left + right) / 2;
      const x =
        3 * (1 - t) ** 2 * t * 0.22 + 3 * (1 - t) * t * t * 0.36 + t ** 3;
      if (x < progress) left = t;
      else right = t;
    }
    return 1 - (1 - (left + right) / 2) ** 3;
  }
  function position(task, route, progress) {
    const points = routes[route];
    const sample = decelerate(Math.max(0, Math.min(1, progress))) * 64;
    const index = Math.min(63, Math.floor(sample)),
      fraction = sample - index;
    const a = points[index],
      b = points[index + 1];
    task.packet.style.transform = `translate(${a.x + (b.x - a.x) * fraction}px, ${a.y + (b.y - a.y) * fraction}px)`;
    task.packet.style.opacity = "1";
  }
  function render() {
    const waiting = queue(),
      completed = tasks.filter(
        (task) => task.start !== null && elapsed >= task.start + 3.2,
      ).length;
    const busy = tasks.filter(
      (task) => task.start !== null && elapsed < task.start + 2.4,
    ).length;
    const submitted = tasks.filter((task) => elapsed >= task.birth).length;
    const phase =
      submitted === 0
        ? "Ready for the next burst"
        : submitted < 160
          ? "Submitting a burst of tasks"
          : completed === 160
            ? workers === 2
              ? "All tasks complete · back to 2 workers"
              : "Queue clear · cooling down"
            : waiting.length
              ? workers < 20
                ? "Queue builds · adding workers"
                : "20 workers processing the burst"
              : "Finishing tasks in flight";
    renderMetrics(
      waiting.filter((task) => task.high).length,
      waiting.filter((task) => !task.high).length,
      completed,
      busy,
      phase,
    );
    tasks.forEach((task) => {
      const age = elapsed - task.birth;
      if (age >= 0 && age < 0.5) position(task, 0, age / 0.5);
      else if (age >= 0.5 && age < 1.3) position(task, 1, (age - 0.5) / 0.8);
      else if (age >= 1.3 && age < 2.2) position(task, 2, (age - 1.3) / 0.9);
      else if (age >= 2.2 && age < 3)
        position(task, task.high ? 3 : 4, (age - 2.2) / 0.8);
      else if (
        task.start !== null &&
        elapsed >= task.start &&
        elapsed < task.start + 0.6
      )
        position(task, task.high ? 5 : 6, (elapsed - task.start) / 0.6);
      else if (
        task.start !== null &&
        elapsed >= task.start + 2.4 &&
        elapsed < task.start + 3.2
      )
        position(task, 7, (elapsed - task.start - 2.4) / 0.8);
      else task.packet.style.opacity = "0";
    });
  }
  function tick(time) {
    if (previousTime !== null)
      accumulator += Math.min((time - previousTime) / 1000, 0.1);
    previousTime = time;
    while (accumulator >= 0.1) {
      step();
      accumulator -= 0.1;
    }
    render();
    frame = requestAnimationFrame(tick);
  }
  function syncPlayback() {
    if (frame !== null) cancelAnimationFrame(frame);
    frame = null;
    previousTime = null;
    pause.disabled = reducedMotion.matches;
    pause.textContent = reducedMotion.matches || userPaused ? "Play" : "Pause";
    pause.setAttribute(
      "aria-pressed",
      String(userPaused || reducedMotion.matches),
    );
    pause.setAttribute(
      "aria-label",
      reducedMotion.matches
        ? "Animation disabled by reduced motion preference"
        : userPaused
          ? "Play task simulation"
          : "Pause task simulation",
    );
    if (!reducedMotion.matches && !userPaused && inView && !document.hidden)
      frame = requestAnimationFrame(tick);
  }
  function motionPreference() {
    reset();
    accumulator = 0;
    if (reducedMotion.matches) {
      workers = 16;
      renderMetrics(4, 72, 40, 12, "Scaling under load · static snapshot");
    } else render();
    syncPlayback();
  }
  pause.addEventListener("click", () => {
    userPaused = !userPaused;
    syncPlayback();
  });
  new IntersectionObserver(
    (entries) => {
      inView = entries[0].isIntersecting;
      syncPlayback();
    },
    { threshold: 0.1 },
  ).observe(map);
  document.addEventListener("visibilitychange", syncPlayback);
  reducedMotion.addEventListener("change", motionPreference);
  motionPreference();
})();
