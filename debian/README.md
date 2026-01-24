# Building TaskFlow CLI Debian Package

## Overview
This debian package automates the complete setup of TaskFlow CLI including:
- Creating Kubernetes secrets
- Pulling Docker images (api, worker, queue-manager)
- Loading images into minikube
- Creating taskflow namespace
- Applying all k8s manifests
- Setting up port forwarding via systemd
- Installing `taskflow` command globally

## Prerequisites

Before installing the package, ensure you have:
- **minikube** - [Install Guide](https://minikube.sigs.k8s.io/docs/start/)
- **kubectl** - [Install Guide](https://kubernetes.io/docs/tasks/tools/)
- **docker** - [Install Guide](https://docs.docker.com/get-docker/)



## Building the Package

1. **Prepare the debian structure:**
   ```bash
   cd ~/TaskFlow
   bash setup_debian.sh
   ```

2. **Build the package:**
   ```bash
   dpkg-buildpackage -us -uc
   ```

3. **Package will be created in parent directory:**
   ```bash
   ls ../ | grep taskflow-cli
   # taskflow-cli_2.1.0-1_all.deb
   ```

## Installation

```bash
sudo dpkg -i ../taskflow-cli_2.1.0-1_all.deb
```

### What happens during installation:
1. Checks for minikube, kubectl, docker
2. Starts minikube if not running
3. Creates `taskflow` namespace
4. Generates `01-secrets.yaml` with random credentials
5. Pulls Docker images with `:latest` tag
6. Loads images into minikube
7. Applies all k8s manifests from `k8s/` directory
8. Creates systemd service for port forwarding (port 8080)
9. Installs `taskflow` command globally

#
## Verification

```bash
# Check if namespace exists
kubectl get namespace taskflow

# Check pods
kubectl get pods -n taskflow

# Check port forwarding service
systemctl status taskflow-port-forward

# Test API
curl http://localhost:8080/health
```

## Uninstallation

```bash
# Remove package
sudo apt remove taskflow-cli

# Purge (removes namespace and user data)
sudo apt purge taskflow-cli
```

## Troubleshooting

**Port forwarding not working:**
```bash
sudo systemctl restart taskflow-port-forward
sudo systemctl status taskflow-port-forward
```

**Images not loading:**
```bash
# Manually load images
minikube image load your-registry/taskflow-api:latest
```

**Pods not starting:**
```bash
kubectl logs -n taskflow deployment/taskflow-api
kubectl describe pod -n taskflow
```

## Files Generated

- `/usr/bin/taskflow` - CLI executable
- `/usr/lib/python3/dist-packages/taskflow_cli/` - Python package
- `/usr/share/taskflow-cli/k8s/` - Kubernetes manifests
- `/etc/systemd/system/taskflow-port-forward.service` - Port forwarding service
- `~/.taskflow/` - User data and history

## Development

To rebuild after changes:
```bash
# Clean previous build
rm -rf debian/taskflow-cli debian/.debhelper debian/files

# Rebuild
dpkg-buildpackage -us -uc
```

## Notes

- The package uses systemd for port forwarding, so it works on systemd-based Linux distributions
- Secrets are auto-generated with secure random values
- The namespace and resources persist after uninstall unless you use `purge`
