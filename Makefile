# TaskFlow Makefile
# Automates local development on Minikube.

# --- Configuration ---
NAMESPACE := taskflow
TAG := latest
REPO := ghcr.io/dhruvkshah75

# --- Colors ---
BOLD := \033[1m
RESET := \033[0m
MSG_COLOR := \033[1;33m   # Yellow for status messages and Command names
LOG_API := \033[36m       # Cyan
LOG_WORKER := \033[32m    # Green
LOG_MANAGER := \033[35m   # Magenta
ERROR := \033[31m         # Red

.PHONY: all help run start-minikube setup build load apply tunnel wait forward stop clean logs logs-api logs-worker logs-manager watch-scaling db-shell stress

# --- Main Commands ---

all: run

help: ## Show this help message
	@echo "$(BOLD)TaskFlow Management Commands:$(RESET)"
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {printf "  $(MSG_COLOR)%-20s$(RESET) %s\n", $$1, $$2}' $(MAKEFILE_LIST)

run: start-minikube setup build load apply tunnel wait forward ## Start the full project (One-click)

# --- Individual Steps ---

start-minikube: ## Check and start Minikube
	@echo "$(MSG_COLOR)Checking Minikube status...$(RESET)"
	@if minikube status > /dev/null 2>&1; then \
		echo "   Minikube is already running."; \
	else \
		echo "   Minikube is stopped. Starting it now..."; \
		minikube start; \
	fi

setup: ## Create namespace if missing
	@echo "$(MSG_COLOR)Checking Namespace...$(RESET)"
	@if kubectl get namespace $(NAMESPACE) > /dev/null 2>&1; then \
		echo "   Namespace '$(NAMESPACE)' exists. Picking it up..."; \
	else \
		echo "   Creating namespace '$(NAMESPACE)'..."; \
		kubectl create namespace $(NAMESPACE); \
	fi

build: ## Build all Docker images locally
	@echo "$(MSG_COLOR)Building Images (using local cache)...$(RESET)"
	@echo "   Building API..."
	@docker build -t $(REPO)/taskflow-api:$(TAG) -f api/Dockerfile . > /dev/null
	@echo "   Building Worker..."
	@docker build -t $(REPO)/taskflow-worker:$(TAG) -f worker/Dockerfile . > /dev/null
	@echo "   Building Queue Manager..."
	@docker build -t $(REPO)/taskflow-queue-manager:$(TAG) -f core/Dockerfile . > /dev/null
	@echo "   Build Complete!"

load: ## Load built images into Minikube
	@echo "$(MSG_COLOR)Loading images into Minikube...$(RESET)"
	@minikube image load $(REPO)/taskflow-api:$(TAG)
	@minikube image load $(REPO)/taskflow-worker:$(TAG)
	@minikube image load $(REPO)/taskflow-queue-manager:$(TAG)

apply: ## Apply all Kubernetes manifests
	@echo "$(MSG_COLOR)Applying Manifests...$(RESET)"
	@kubectl apply -f k8s/ --recursive -n $(NAMESPACE)

tunnel: ## Start Minikube tunnel in background
	@echo "$(MSG_COLOR)Starting Minikube tunnel in background...$(RESET)"
	@if pgrep -f "minikube tunnel" > /dev/null; then \
		echo "   Tunnel already running."; \
	else \
		nohup minikube tunnel > /dev/null 2>&1 & \
		echo "   Tunnel started."; \
	fi

wait: ## Wait for API pod to be ready
	@echo "$(MSG_COLOR)Waiting for API pod to be ready...$(RESET)"
	@kubectl wait --namespace $(NAMESPACE) --for=condition=ready pod -l app=api --timeout=120s > /dev/null
	@echo "   API is UP!"

forward: ## Port-forward API to localhost:8080
	@echo "$(MSG_COLOR)System Ready! Forwarding taskflow-api:80 -> localhost:8080...$(RESET)"
	@echo "$(ERROR)Press Ctrl+C to stop forwarding (Cluster remains running).$(RESET)"
	@kubectl port-forward -n $(NAMESPACE) svc/taskflow-api 8080:80

# --- Stop & Clean ---

stop: ## Stop Minikube and cleanup tunnels (Preserves Data)
	@echo "$(MSG_COLOR)Stopping Project...$(RESET)"
	@echo "   Killing background tunnel..."
	@-pkill -f "minikube tunnel" || true
	@echo "   Stopping Minikube cluster..."
	@minikube stop
	@echo "$(MSG_COLOR)Project stopped successfully. (Namespace preserved)$(RESET)"

clean: ## Delete the namespace and all data
	@echo "$(MSG_COLOR)Deleting TaskFlow namespace...$(RESET)"
	@-kubectl delete namespace $(NAMESPACE) --timeout=60s
	@echo "$(MSG_COLOR)Namespace deleted.$(RESET)"

# --- Utilities ---

watch-scaling: ## Watch worker deployment scale up/down
	@echo "$(MSG_COLOR)Watching worker autoscaling...$(RESET)"
	@kubectl get deployment worker -n $(NAMESPACE) -w

db-shell: ## Connect to the PostgreSQL database shell
	@echo "$(MSG_COLOR)Connecting to PostgreSQL...$(RESET)"
	@kubectl exec -it -n $(NAMESPACE) $$(kubectl get pod -n $(NAMESPACE) -l app=postgres -o jsonpath="{.items[0].metadata.name}") -- psql -U postgres -d taskflow_db

logs-api: ## Stream API logs only
	@kubectl logs -n $(NAMESPACE) -l app=api -f

logs-worker: ## Stream Worker logs only
	@kubectl logs -n $(NAMESPACE) -l app=worker -f

logs-manager: ## Stream Queue Manager logs only
	@kubectl logs -n $(NAMESPACE) -l app=queue-manager -f

logs: ## Stream ALL logs (Can cause throttling because of many concurrent runs)
	@echo "$(MSG_COLOR)Streaming logs (Ctrl+C to stop)...$(RESET)"
	@echo "   $(LOG_API)API Logs$(RESET) | $(LOG_WORKER)Worker Logs$(RESET) | $(LOG_MANAGER)Manager Logs$(RESET)"
	@# Increased max-log-requests to 50 to handle autoscaled workers
	@kubectl logs -n $(NAMESPACE) -l 'app in (api, worker, queue-manager)' -f --prefix=true --max-log-requests=50 | \
	awk '\
	/pod\/api/ { print "$(LOG_API)" $$0 "$(RESET)"; fflush(); next } \
	/pod\/worker/ { print "$(LOG_WORKER)" $$0 "$(RESET)"; fflush(); next } \
	/pod\/queue-manager/ { print "$(LOG_MANAGER)" $$0 "$(RESET)"; fflush(); next } \
	{ print; fflush() }'

stress: ## Run the stress test (200 tasks)
	@echo "$(MSG_COLOR)Unleashing 200 tasks...$(RESET)"
	@python3 ./tests/stress-test.py