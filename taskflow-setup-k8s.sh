#!/bin/bash
# TaskFlow Kubernetes Setup Script
# Run this to deploy TaskFlow to minikube manually

set -e

NAMESPACE="taskflow"
K8S_DIR="/usr/share/taskflow-cli/k8s"

echo "TaskFlow Kubernetes Setup"
echo "=============================="
echo ""

# Check if commands exist
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

if ! command_exists minikube; then
    echo "minikube not found"
    echo "Install: https://minikube.sigs.k8s.io/docs/start/"
    exit 1
fi

if ! command_exists kubectl; then
    echo "kubectl not found"
    echo "Install: https://kubernetes.io/docs/tasks/tools/"
    exit 1
fi

if ! command_exists docker; then
    echo "docker not found"
    echo "Install: https://docs.docker.com/get-docker/"
    exit 1
fi

# Check if minikube is running
echo "Checking minikube status..."
if ! minikube status >/dev/null 2>&1; then
    echo "Starting minikube (this may take 2-3 minutes)..."
    minikube start --driver=docker || {
        echo "Failed to start minikube"
        echo "Try: minikube delete && minikube start"
        exit 1
    }
fi

echo "✓ Minikube is running"

# Create namespace
echo "Creating namespace: $NAMESPACE"
kubectl create namespace $NAMESPACE 2>/dev/null || echo "  (namespace already exists)"

# Generate secrets if not exists
SECRETS_FILE="$K8S_DIR/01-secrets.yaml"
if [ ! -f "$SECRETS_FILE" ]; then
    echo "Generating secrets..."
    
    # Generate generic secrets
    sudo bash -c "cat > '$SECRETS_FILE' << EOF
apiVersion: v1
kind: Secret
metadata:
  name: taskflow-db-secret
  namespace: $NAMESPACE
type: Opaque
stringData:
  POSTGRES_DB: \"taskflow_db\"
  POSTGRES_USER: \"postgres\"
  POSTGRES_PASSWORD: \"password\"
  DATABASE_URL: \"postgresql://postgres:password@taskflow-pgbouncer:6432/taskflow_db\"
---
apiVersion: v1
kind: Secret
metadata:
  name: taskflow-redis-secret
  namespace: $NAMESPACE
type: Opaque
stringData:
  REDIS_PASSWORD: \"\"  # No password for KEDA compatibility
  REDIS_HOST_HIGH: \"redis-high\"
  REDIS_PORT_HIGH: \"6379\"
  REDIS_HOST_LOW: \"redis-low\"
  REDIS_PORT_LOW: \"6379\"
---
apiVersion: v1
kind: Secret
metadata:
  name: taskflow-app-secret
  namespace: $NAMESPACE
type: Opaque
stringData:
  SECRET_KEY: \"test_secret_key_for_ci_only\"
  ALGORITHM: \"HS256\"
  ACCESS_TOKEN_EXPIRE_MINUTES: \"60\"
EOF"
    echo "✓ Secrets generated"
else
    echo "✓ Using existing secrets"
fi

# Apply Secrets
echo "Applying secrets..."
kubectl apply -f "$SECRETS_FILE" -n $NAMESPACE

# Apply ConfigMaps
echo "Applying ConfigMaps..."
if [ -f "$K8S_DIR/02-configmaps.yaml" ]; then
    kubectl apply -f "$K8S_DIR/02-configmaps.yaml" -n $NAMESPACE
else
    echo "Warning: 02-configmaps.yaml not found!"
fi

# Apply infrastructure (database, redis)
echo "Deploying infrastructure (postgres, redis)..."
kubectl apply -f "$K8S_DIR/infrastructure/" -n $NAMESPACE

# Wait for infrastructure
echo "Waiting for infrastructure to be ready (10 seconds)..."
sleep 10

# Apply applications (api, worker, queue-manager)
echo "Deploying applications (api, worker, queue-manager)..."
kubectl apply -f "$K8S_DIR/apps/" -n $NAMESPACE

# Wait for API to be ready
echo "Waiting for API to be ready (this may take 2-3 minutes)..."
kubectl wait --for=condition=ready pod -l app=taskflow-api -n $NAMESPACE --timeout=300s || {
    echo ""
    echo "Timeout waiting for API pod"
    echo "Check status with:"
    echo "  kubectl get pods -n $NAMESPACE"
    echo "  kubectl logs -n $NAMESPACE -l app=taskflow-api"
    echo ""
}

# Setup port forwarding as systemd service
echo "Setting up port forwarding service..."
# Detect the real user (who ran sudo)
REAL_USER=${SUDO_USER:-$USER}
USER_HOME=$(getent passwd "$REAL_USER" | cut -d: -f6)

sudo bash -c "cat > /etc/systemd/system/taskflow-port-forward.service << SERVICEEOF
[Unit]
Description=TaskFlow API Port Forward
After=network.target

[Service]
Type=simple
User=$REAL_USER
Environment=KUBECONFIG=$USER_HOME/.kube/config
ExecStart=/usr/bin/kubectl port-forward -n taskflow service/taskflow-api 8080:80
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
SERVICEEOF"

sudo systemctl daemon-reload
sudo systemctl enable taskflow-port-forward.service
sudo systemctl restart taskflow-port-forward.service

echo ""
echo "TaskFlow deployed successfully!"
echo ""
echo "API is accessible at: http://localhost:8080"
echo ""
echo "Quick Start:"
echo "  taskflow            # Start interactive CLI"
echo "  taskflow register   # Create an account"
echo "  taskflow login      # Login"
echo ""
echo "Management Commands:"
echo "  kubectl get pods -n $NAMESPACE                    # Check pod status"
echo "  kubectl logs -n $NAMESPACE -l app=taskflow-api    # View API logs"
echo "  sudo systemctl status taskflow-port-forward       # Check port forwarding"
echo "  sudo systemctl stop taskflow-port-forward         # Stop port forwarding"
echo ""
echo "Troubleshooting:"
echo "  kubectl describe pods -n $NAMESPACE               # Detailed pod info"
echo "  minikube dashboard                                # Open Kubernetes dashboard"
echo ""
