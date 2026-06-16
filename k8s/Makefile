# =============================================================================
# GNONE — Kubernetes Deployment Makefile
#
# Usage:
#   make apply        Deploy all resources to the cluster
#   make delete       Remove all resources from the cluster
#   make status       Show resource status
#   make logs         Stream API pod logs
#   make port-forward Forward local port to API service
#   make restart      Rolling restart of the API deployment
#   make scale        Scale deployment to N replicas (make scale N=5)
#   make migrate      Run database migration job
# =============================================================================

NAMESPACE ?= gnone
CONTEXT ?=
KUBECTL = kubectl $(if $(CONTEXT),--context $(CONTEXT)) -n $(NAMESPACE)

.PHONY: help apply delete status logs port-forward restart scale migrate clean namespace secrets

help:
	@echo "GNONE Kubernetes Deployment Helper"
	@echo ""
	@echo "Usage: make <target> [OPTIONS]"
	@echo ""
	@echo "Targets:"
	@echo "  apply          Deploy all resources to the cluster"
	@echo "  delete         Remove all resources from the cluster"
	@echo "  status         Show resource status"
	@echo "  logs           Stream API pod logs"
	@echo "  port-forward   Forward local port 8000 to API service"
	@echo "  restart        Rolling restart of the API deployment"
	@echo "  scale          Scale deployment (set N=<replicas>)"
	@echo "  migrate        Run database migration job"
	@echo "  clean          Delete all resources including PVCs"
	@echo "  namespace      Create the namespace"
	@echo "  secrets        Show secret status (not values)"
	@echo ""
	@echo "Options:"
	@echo "  NAMESPACE      Kubernetes namespace (default: gnone)"
	@echo "  CONTEXT        Kubernetes context name"
	@echo "  N              Number of replicas for scale target"

namespace:
	@echo "Creating namespace $(NAMESPACE)..."
	$(KUBECTL) apply -f namespace.yaml

secrets: namespace
	@echo "Applying secrets..."
	@echo "WARNING: Verify secrets.yaml contains real base64-encoded values before applying."
	$(KUBECTL) apply -f secrets.yaml

apply: namespace secrets
	@echo "Deploying GNONE to namespace $(NAMESPACE)..."
	$(KUBECTL) apply -f configmap.yaml
	$(KUBECTL) apply -f service.yaml
	$(KUBECTL) apply -f deployment.yaml
	$(KUBECTL) apply -f hpa.yaml
	$(KUBECTL) apply -f ingress.yaml
	$(KUBECTL) apply -f networkpolicy.yaml
	$(KUBECTL) apply -f poddisruptionbudget.yaml
	$(KUBECTL) apply -f priorityclass.yaml
	@echo ""
	@echo "Deployment complete. Run 'make status' to verify."

delete:
	@echo "Removing GNONE resources from namespace $(NAMESPACE)..."
	-$(KUBECTL) delete -f deployment.yaml --ignore-not-found
	-$(KUBECTL) delete -f hpa.yaml --ignore-not-found
	-$(KUBECTL) delete -f ingress.yaml --ignore-not-found
	-$(KUBECTL) delete -f networkpolicy.yaml --ignore-not-found
	-$(KUBECTL) delete -f poddisruptionbudget.yaml --ignore-not-found
	-$(KUBECTL) delete -f priorityclass.yaml --ignore-not-found
	-$(KUBECTL) delete -f service.yaml --ignore-not-found
	-$(KUBECTL) delete -f configmap.yaml --ignore-not-found
	-$(KUBECTL) delete -f secrets.yaml --ignore-not-found
	@echo "Resources removed."

clean: delete
	@echo "Deleting PersistentVolumeClaims..."
	-$(KUBECTL) delete pvc --all --ignore-not-found
	@echo "Deleting namespace $(NAMESPACE)..."
	-kubectl delete namespace $(NAMESPACE) --ignore-not-found
	@echo "Clean complete."

status:
	@echo "=== Deployments ==="
	$(KUBECTL) get deployments -o wide
	@echo ""
	@echo "=== Pods ==="
	$(KUBECTL) get pods -o wide
	@echo ""
	@echo "=== Services ==="
	$(KUBECTL) get services
	@echo ""
	@echo "=== HPA ==="
	$(KUBECTL) get hpa
	@echo ""
	@echo "=== Ingress ==="
	$(KUBECTL) get ingress
	@echo ""
	@echo "=== PVCs ==="
	$(KUBECTL) get pvc

logs:
	$(KUBECTL) logs -l app=gnone-api -f --tail=100

port-forward:
	@echo "Forwarding localhost:8000 -> gnone-api:8000"
	@echo "Press Ctrl+C to stop"
	$(KUBECTL) port-forward svc/gnone-api 8000:8000

restart:
	@echo "Rolling restart of gnone-api..."
	$(KUBECTL) rollout restart deployment/gnone-api
	$(KUBECTL) rollout status deployment/gnone-api --timeout=300s

N ?= 3
scale:
	@echo "Scaling gnone-api to $(N) replicas..."
	$(KUBECTL) scale deployment/gnone-api --replicas=$(N)
	$(KUBECTL) get deployment gnone-api

migrate:
	@echo "Running database migration job..."
	$(KUBECTL) apply -f migration-job.yaml
	$(KUBECTL) wait --for=condition=complete job/gnone-migration --timeout=300s
	@echo "Migration complete."
	$(KUBECTL) delete -f migration-job.yaml
