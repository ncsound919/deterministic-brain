---
name: deploy-k8s
description: Deploy services to Kubernetes with safe, repeatable steps.
version: 1.0.0
metadata:
  hermes:
    tags: [devops, kubernetes]
    category: devops
---

# Deploy to Kubernetes

## When to Use
When you need to deploy a service to a Kubernetes cluster with proper validation and rollback support.

## Procedure
1. First, verify cluster access and current context.
2. Validate the deployment manifest against cluster requirements.
3. Generate the deployment YAML with proper labels and annotations.
4. Apply manifests in order: namespace, secrets, configmaps, then deployment.
5. Verify deployment status and check pod health.

## Pitfalls
- Don't skip namespace creation - resources will fail without it.
- Always validate YAML syntax before applying.

## Verification
- Run `kubectl get pods -n <namespace>` to confirm pods are running.
- Check `kubectl rollout status deployment/<name>` for rollout success.