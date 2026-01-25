<div align="center">
  <br>
  <img src="public/assets/logo1.png" alt="logo" width="100" height="auto" />
  <br>
  <br>
  <h1>TaskFlow</h1>
  
  <p>
    <b>Streamline your workflow with intelligent task management ⚡️</b>
  </p>
  
  ![Docker](https://img.shields.io/badge/docker-%230db7ed.svg?style=flat-square&logo=docker&logoColor=white)
  ![Kubernetes](https://img.shields.io/badge/kubernetes-%23326ce5.svg?style=flat-square&logo=kubernetes&logoColor=white)
  ![FastAPI](https://img.shields.io/badge/FastAPI-005571?style=flat-square&logo=fastapi)
  ![Python](https://img.shields.io/badge/python-3.11+-blue.svg?style=flat-square&logo=python&logoColor=white)
  ![Redis](https://img.shields.io/badge/redis-%23DD0031.svg?style=flat-square&logo=redis&logoColor=white)
  ![PostgreSQL](https://img.shields.io/badge/postgresql-%23316192.svg?style=flat-square&logo=postgresql&logoColor=white)
  ![CI/CD](https://img.shields.io/badge/CI%2FCD-Automated-green?style=flat-square&logo=github-actions)

   
  <br />
</div>

## Overview

**TaskFlow v2.1.0** is a production-ready distributed task execution platform featuring **dynamic code execution**, **intelligent autoscaling**, and a **unified CLI command center**. Upload custom Python tasks at runtime and execute them across a fleet of auto-scaling workers—no container rebuilds or manual `kubectl` commands required.

The system leverages **FastAPI** for high-performance task submission, **Redis** for message brokering, **PostgreSQL** for persistence, and **KEDA** for event-driven autoscaling based on queue depth.

### **Key Capabilities**

* **Unified CLI Interface**: Manage the entire lifecycle—from account registration to task deployment and cluster health—directly via the `taskflow` command.
* **One-Click Debian Installer**: Distributed as a `.deb` package that bundles the CLI and automatically bootstraps the Kubernetes environment on the user's host.
* **Modular Workers**: Upload and execute custom Python code dynamically without redeploying or rebuilding images.
* **Smart Autoscaling**: KEDA scales workers from 2 to 20 pods based on real-time Redis queue length.
* **Dual-Priority Queues**: Separate high/low priority Redis queues with intelligent routing for critical tasks.
* **Async & Sync Support**: Native support for executing both `def handler()` and `async def handler()` functions.
* **Persistent Storage**: Shared task files across API and worker pods enabled by ReadWriteMany PVCs.
* **Production Native**: Fully orchestrated with automated health checks, graceful shutdowns, and persistent port-forwarding services.

---

## Debian Package Installation of taskflow-cli
The **TaskFlow CLI** is the primary interface for users to interact with the TaskFlow distributed orchestration system. It is a Python-based command-line tool designed to manage the full lifecycle of distributed tasks—from registration and authentication to monitoring and execution.  

TaskFlow offers a `.deb` package for easy installation on Debian/Ubuntu systems.

### **Prerequisites**
Before installing the package, ensure you have the following installed:
- [Docker](https://docs.docker.com/get-docker/) (Daemon must be running)
- [Minikube](https://minikube.sigs.k8s.io/docs/start/)
- [kubectl](https://kubernetes.io/docs/tasks/tools/)

### **Installation**
Install the `.deb` package from the github release section

```bash
  sudo dpkg -i ../taskflow-cli.deb
```
This will automatically:
-   Deploy TaskFlow to your local Minikube cluster
-   Set up required secrets and infrastructure
-   Start a system service to forward the API to `localhost:8080`

### **Running**
Once installed, you can use the CLI immediately:
```bash
taskflow             # Start interactive session
taskflow> register   # Create an account
taskflow> login      # Login
taskflow> help       # to view all the commands 
```

### **Troubleshooting**
If you cannot connect to the API, you may need to run port forwarding manually:
```bash
kubectl port-forward -n taskflow svc/taskflow-api 8080:80
```

---

**Workers Auto-Scale & Execute:**
- Queue builds up → Workers scale from 2 to 20 pods
- Each worker loads `process_data.py` and executes `handler()`
- Results stored in database
- Queue empties → Workers scale back to 2 pods

**Task Requirements:**
- Must contain `handler(payload)` function (sync or async)
- Task `title` must match filename (without `.py`)
- Payload passed as dictionary to handler

---

## See TaskFlow in Action

**[taskflow-io.vercel.app](https://taskflow-io.vercel.app/)** - Interactive demonstration with project overview, architecture, and demo videos


  <td style="width: 50%; vertical-align: top;">
    <img src="./public/assets1/illustration.png" 
          style="width: 60%; object-fit: cover;" 
          alt="TaskFlow Scaling Proof">
  </td>
  <td style="width: 50%; vertical-align: top;">
    <img src="./public/assets1/output_high_res.gif" 
          style="width: 100%; aspect-ratio: 16 / 9; object-fit: cover;" 
          alt="TaskFlow Auto-Scaling Demo">
  </td>


-----


## Kubernetes local Deployment (Minikube)

TaskFlow includes a **highly automated Makefile system** that streamlines the entire Kubernetes development lifecycle. Deploy the full stack with a single command.

### **Prerequisites**

- [Minikube](https://minikube.sigs.k8s.io/docs/start/) installed
- [kubectl](https://kubernetes.io/docs/tasks/tools/) CLI tool
- [Docker](https://docs.docker.com/get-docker/) (for Minikube driver)

### **Makefile Command Reference**

The Makefile provides a complete set of utilities for managing your local Kubernetes environment:

#### **Make commands**

| Command | Description |
|---------|-------------|
| `make run-local` | **Full local deployment.** Builds images, loads to Minikube, deploys all services with autoscaling. |
| `make build-local` | **Parallel builds.** Builds API, Worker, Queue Manager images simultaneously (3x faster). |
| `make build-local-sequential` | **Sequential builds.** Builds images one-by-one (safer for limited resources). |
| `make load` | Load Docker images into Minikube cluster. |
| `make apply` | Deploy all Kubernetes manifests (ConfigMaps, Infrastructure, Apps, Autoscaling). |
| `make clean` | **Reset.** Deletes the `taskflow` namespace and all resources (**data lost**). |
| `make restart` | **Refresh.** Equivalent to `make clean && make run-local`. |
| `make forward` | Start port forwarding (API: 8080, PgBouncer: 6432). |
| `make stop` | Stop Minikube tunnel and port forwarding. |
| `make logs` | Stream **color-coded logs** from all services (API, Workers, Queue Manager). |
| `make db-shell` | Connect to PostgreSQL with interactive `psql` session. |
| `make status` | Show running pods, services, and deployments. |
| `make watch-scaling` | Monitor worker autoscaling in real-time (HPA + pod count). |
| `make stress` | Submit 200 concurrent tasks via `tests/stress-test.py`. |
| `make autoscale-test` | Run autoscaling test (creates 200 tasks, monitors scaling). |
| `make pull` | Pull pre-built images from GHCR (for production deployment). |
| `make prune` | Free up disk space by deleting Docker build cache. |
| `make secrets` | Generate `k8s/01-secrets.yaml` with development credentials. |
| `make install-keda` | Install KEDA autoscaling operator via Helm. |
| `make help` | Display all available commands with descriptions. |

---

### **Disk Space Management**

If Docker consumes too much disk space:

```bash
make prune
```

This removes:
- All Docker build cache (`docker builder prune --all`)
- Dangling/unused images (`docker image prune`)

Verify reclaimed space with:
```bash
docker system df
```

---


## Contributing

Contributions are welcome! Please feel free to submit a Pull Request. For major changes, please open an issue first to discuss what you would like to change.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---




