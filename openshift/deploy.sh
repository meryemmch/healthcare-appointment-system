#!/usr/bin/env bash
set -euo pipefail

# Deploy the healthcare microservices to OpenShift using the YAML manifests in this directory.
# Usage: ./deploy.sh [project-name]
# Example: ./deploy.sh clinic-app

PROJECT=${1:-clinic-app}
ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"

oc project ${PROJECT} >/dev/null 2>&1 || {
  echo "Creating project ${PROJECT}..."
  oc new-project ${PROJECT}
}

echo "Applying secrets and configmaps..."
oc apply -f "${ROOT_DIR}/secrets-configmap.yaml"

echo "Applying persistent volumes and Postgres..."
oc apply -f "${ROOT_DIR}/persistent-volumes.yaml" || true
oc apply -f "${ROOT_DIR}/postgres.yaml"

echo "Applying auth and patient deploymentconfigs..."
oc apply -f "${ROOT_DIR}/auth-service-dc.yaml"
oc apply -f "${ROOT_DIR}/patient-service-dc.yaml"

echo "Applying remaining services (doctor, appointment, records, billing)..."
oc apply -f "${ROOT_DIR}/all-services-dc.yaml"

echo "Applying routes (exposes services)"
oc apply -f "${ROOT_DIR}/routes.yaml"

# Wait for deploymentconfigs to roll out
DC_LIST=(auth-service patient-service doctor-service appointment-service medical-records-service billing-service)
for dc in "${DC_LIST[@]}"; do
  echo "Waiting for deploymentconfig/${dc} to be ready..."
  # Some resources may be Kubernetes Deployments (postgres), handle both
  if oc get dc/${dc} >/dev/null 2>&1; then
    oc rollout status dc/${dc} --watch=true || true
  elif oc get deploy/${dc} >/dev/null 2>&1; then
    oc rollout status deploy/${dc} --watch=true || true
  else
    echo "No deploymentconfig/deployment named ${dc} found yet"
  fi
done

# Print routes
echo "Deployment complete. Routes:"
oc get routes -o wide

echo "You can now access the services via the listed routes (or use port-forwarding for local clusters)."
