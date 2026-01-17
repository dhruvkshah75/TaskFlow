# TaskFlow Makefile
# Automates local development on Minikube.

# --- Configuration ---
NAMESPACE := taskflow
TAG := latest
# Registry URL
REPO := ghcr.io/dhruvkshah75

# --- Colors ---
BOLD := \033[1m
RESET := \033[0m
MSG_COLOR := \033[1;33m   # Yellow for status messages and Command names
LOG_API := \033[36m       # Cyan
LOG_WORKER := \033[32m    # Green
LOG_MANAGER := \033[35m   # Magenta
ERROR := \033[31m         # Red

.PHONY: all help run run-local start-minikube setup secrets login pull build-local load apply install-keda tunnel wait forward stop clean logs logs-api logs-worker logs-manager watch-scaling db-shell stress prune

# --- Main Commands ---

all: run

help: ## Show this help message
	@echo "$(BOLD)TaskFlow Management Commands:$(RESET)"
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {printf "  $(MSG_COLOR)%-20s$(RESET) %s\n", $$1, $$2}' $(MAKEFILE_LIST)

# Sequence: Start -> Setup -> Secrets -> PULL -> Load -> Apply -> Tunnel -> Wait -> Forward
run: start-minikube setup secrets pull load apply tunnel wait forward ## Start project (Pull from Registry)

run-local: start-minikube setup secrets build-local load apply tunnel wait forward ## Start project (Build locally)

# --- Individual Steps ---

start-minikube: ## Check and start Minikube
	@echo "$(MSG_COLOR)Checking Minikube status...$(RESET)"
	@if minikube status 2>&1 | grep -q "Running"; then \
		echo "   Minikube is already running."; \
	else \
		echo "   Minikube is not running. Starting it now..."; \
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

secrets: ## Generate k8s/01-secrets.yaml only if it doesn't exist
	@if [ ! -f k8s/01-secrets.yaml ]; then \
		echo "$(MSG_COLOR)Secrets file missing. Generating default dev secrets in k8s/01-secrets.yaml...$(RESET)"; \
		# 1. DB Secret \
		kubectl create secret generic taskflow-db-secret \
			--namespace=$(NAMESPACE) \
			--from-literal=POSTGRES_DB=taskflow_db \
			--from-literal=POSTGRES_USER=postgres \
			--from-literal=POSTGRES_PASSWORD=password \
			--from-literal=DATABASE_URL=postgresql://postgres:password@taskflow-pgbouncer:6432/taskflow_db \
			--dry-run=client -o yaml > k8s/01-secrets.yaml; \
		echo "---" >> k8s/01-secrets.yaml; \
		# 2. Redis Secret \
		kubectl create secret generic taskflow-redis-secret \
			--namespace=$(NAMESPACE) \
			--from-literal=REDIS_PASSWORD=test_password \
			--from-literal=REDIS_HOST_HIGH=redis-high \
			--from-literal=REDIS_PORT_HIGH=6379 \
			--from-literal=REDIS_HOST_LOW=redis-low \
			--from-literal=REDIS_PORT_LOW=6379 \
			--dry-run=client -o yaml >> k8s/01-secrets.yaml; \
		echo "---" >> k8s/01-secrets.yaml; \
		# 3. App Secret \
		kubectl create secret generic taskflow-app-secret \
			--namespace=$(NAMESPACE) \
			--from-literal=SECRET_KEY=test_secret_key_for_ci_only \
			--from-literal=ALGORITHM=HS256 \
			--from-literal=ACCESS_TOKEN_EXPIRE_MINUTES=60 \
			--dry-run=client -o yaml >> k8s/01-secrets.yaml; \
		echo "   Secrets generated successfully!"; \
	else \
		echo "$(MSG_COLOR)Secrets file found (k8s/01-secrets.yaml). Skipping generation.$(RESET)"; \
	fi

login: ## Authenticate Docker with GHCR
	@echo "$(MSG_COLOR)Authenticating Docker with GHCR...$(RESET)"
	@if command -v gh > /dev/null 2>&1 && gh auth status > /dev/null 2>&1; then \
		echo "   Using GitHub CLI token..."; \
		echo $$(gh auth token) | docker login ghcr.io -u dhruvkshah75 --password-stdin; \
	else \
		echo "$(ERROR)GitHub CLI not authenticated. Run 'gh auth login' first.$(RESET)"; \
		exit 1; \
	fi

pull: ## Pull Docker images from GHCR
	@echo "$(MSG_COLOR)Pulling Images from GHCR...$(RESET)"
	@echo "   Pulling API..."
	@docker pull $(REPO)/taskflow-api:$(TAG) > /dev/null
	@echo "   Pulling Worker..."
	@docker pull $(REPO)/taskflow-worker:$(TAG) > /dev/null
	@echo "   Pulling Queue Manager..."
	@docker pull $(REPO)/taskflow-queue-manager:$(TAG) > /dev/null
	@echo "   Pull Complete!"

build-local: ## Build Docker images locally
	@echo "$(MSG_COLOR)Building Images Locally...$(RESET)"
	@echo "   Building API..."
	@docker build --no-cache -t $(REPO)/taskflow-api:$(TAG) -f api/Dockerfile .
	@echo "   Building Worker..."
	@docker build --no-cache -t $(REPO)/taskflow-worker:$(TAG) -f worker/Dockerfile .
	@echo "   Building Queue Manager..."
	@docker build --no-cache -t $(REPO)/taskflow-queue-manager:$(TAG) -f core/Dockerfile .
	@echo "   Build Complete!"

load: ## Load pulled images into Minikube
	@echo "$(MSG_COLOR)Loading images into Minikube...$(RESET)"
	@minikube image load $(REPO)/taskflow-api:$(TAG)
	@minikube image load $(REPO)/taskflow-worker:$(TAG)
	@minikube image load $(REPO)/taskflow-queue-manager:$(TAG)

apply: ## Apply all Kubernetes manifests
	@echo "$(MSG_COLOR)Applying Manifests...$(RESET)"
	@kubectl apply -f k8s/ --recursive -n $(NAMESPACE) || \
		(echo "$(ERROR)Warning: Some manifests failed (possibly KEDA autoscaling). Core services should still work.$(RESET)" && \
		kubectl apply -f k8s/ --recursive -n $(NAMESPACE) --validate=false 2>/dev/null || true)

install-keda: ## Install KEDA for autoscaling (optional)
	@echo "$(MSG_COLOR)Installing KEDA...$(RESET)"
	@kubectl apply --server-side -f https://github.com/kedacore/keda/releases/download/v2.16.1/keda-2.16.1.yaml
	@echo "   KEDA installed! You can now apply autoscaling manifests."

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

logs: ## Stream ALL logs (Color-coded)
	@echo "$(MSG_COLOR)Streaming logs (Ctrl+C to stop)...$(RESET)"
	@echo "   $(LOG_API)API Logs$(RESET) | $(LOG_WORKER)Worker Logs$(RESET) | $(LOG_MANAGER)Manager Logs$(RESET)"
	@kubectl logs -n $(NAMESPACE) -l 'app in (api, worker, queue-manager)' -f --prefix=true --max-log-requests=50 | \
	awk '\
	/pod\/api/ { print "$(LOG_API)" $$0 "$(RESET)"; fflush(); next } \
	/pod\/worker/ { print "$(LOG_WORKER)" $$0 "$(RESET)"; fflush(); next } \
	/pod\/queue-manager/ { print "$(LOG_MANAGER)" $$0 "$(RESET)"; fflush(); next } \
	{ print; fflush() }'

stress: ## Run the stress test (200 tasks)
	@echo "$(MSG_COLOR)Unleashing 200 tasks...$(RESET)"
	@python3 ./tests/stress-test.py

prune: ## Free up space (Deletes Build Cache & Unused Images)
	@echo "$(MSG_COLOR)Cleaning up unused Docker data...$(RESET)"
	@# 1. Delete Build Cache (The "Invisible" space)
	@docker builder prune --all --force
	@# 2. Delete Dangling Images (Old versions that were overwritten)
	@docker image prune --force
	@echo "$(MSG_COLOR)Cleanup complete!$(RESET)"