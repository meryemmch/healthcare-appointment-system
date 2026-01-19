#!/usr/bin/env bash
set -euo pipefail

PROJECT=${1:-clinic-app}

# 1️⃣ Log in and create project
oc login <your-cluster-url>   # replace with your OpenShift cluster
oc new-project $PROJECT || echo "Project $PROJECT already exists"

# 2️⃣ Create secrets
echo "Creating secrets..."
oc create secret generic healthcare-db-secret \
  --from-literal=username=healthcare_user \
  --from-literal=password=supersecurepassword \
  --dry-run=client -o yaml | oc apply -f -

oc create secret generic app-secrets \
  --from-literal=jwt-secret="your-super-secret-jwt-key-change-this" \
  --dry-run=client -o yaml | oc apply -f -

# 3️⃣ Deploy Postgres DB
echo "Deploying Postgres..."
oc new-app postgres:15 \
  --name=healthcare-db \
  -e POSTGRES_DB=healthcare \
  -e POSTGRES_USER=healthcare_user \
  -e POSTGRES_PASSWORD=supersecurepassword

# Optional: expose internally
oc expose svc/healthcare-db --port=5432

# 4️⃣ Deploy microservices from GitHub
GIT_REPO="https://github.com/yosseer/DevOps-Incident-Board"

echo "Deploying Auth Service..."
oc new-app $GIT_REPO \
  --name=auth-service \
  --context-dir=auth-service \
  --strategy=docker \
  -e DB_HOST=healthcare-db \
  -e DB_PORT=5432 \
  -e DB_NAME=healthcare \
  -e DB_USER=healthcare_user \
  -e DB_PASSWORD=supersecurepassword \
  -e SECRET_KEY="your-super-secret-jwt-key-change-this"

echo "Deploying Patient Service..."
oc new-app $GIT_REPO \
  --name=patient-service \
  --context-dir=patient-service \
  --strategy=docker \
  -e DB_HOST=healthcare-db \
  -e DB_PORT=5432 \
  -e DB_NAME=healthcare \
  -e DB_USER=healthcare_user \
  -e DB_PASSWORD=supersecurepassword \
  -e AUTH_SERVICE_URL=http://auth-service:8000

echo "Deploying Doctor Service..."
oc new-app $GIT_REPO \
  --name=doctor-service \
  --context-dir=doctor-service \
  --strategy=docker \
  -e AUTH_SERVICE_URL=http://auth-service:8000

echo "Deploying Appointment Service..."
oc new-app $GIT_REPO \
  --name=appointment-service \
  --context-dir=appointment-service \
  --strategy=docker \
  -e DB_HOST=healthcare-db \
  -e DB_PORT=5432 \
  -e DB_NAME=healthcare \
  -e DB_USER=healthcare_user \
  -e DB_PASSWORD=supersecurepassword \
  -e AUTH_SERVICE_URL=http://auth-service:8000 \
  -e NOTIFICATION_SERVICE_URL=http://notification-service:8005

echo "Deploying Medical Records Service..."
oc new-app $GIT_REPO \
  --name=medical-records-service \
  --context-dir=medical-records-service \
  --strategy=docker \
  -e DB_HOST=healthcare-db \
  -e DB_PORT=5432 \
  -e DB_NAME=healthcare \
  -e DB_USER=healthcare_user \
  -e DB_PASSWORD=supersecurepassword \
  -e AUTH_SERVICE_URL=http://auth-service:8000

echo "Deploying Billing Service..."
oc new-app $GIT_REPO \
  --name=billing-service \
  --context-dir=billing-service \
  --strategy=docker \
  -e DB_HOST=healthcare-db \
  -e DB_PORT=5432 \
  -e DB_NAME=healthcare \
  -e DB_USER=healthcare_user \
  -e DB_PASSWORD=supersecurepassword \
  -e AUTH_SERVICE_URL=http://auth-service:8000

# 5️⃣ Expose routes
echo "Exposing routes..."
oc expose svc/auth-service --port=8000 --name=auth-route
oc expose svc/patient-service --port=8001 --name=patient-route
oc expose svc/doctor-service --port=8002 --name=doctor-route
oc expose svc/appointment-service --port=8003 --name=appointment-route
oc expose svc/medical-records-service --port=8004 --name=records-route
oc expose svc/billing-service --port=8006 --name=billing-route

# 6️⃣ Wait for pods to be ready
echo "Waiting for pods..."
for svc in auth-service patient-service doctor-service appointment-service medical-records-service billing-service healthcare-db; do
  echo "Waiting for $svc..."
  oc rollout status deployment/$svc || true
done

# 7️⃣ Print routes
echo "Deployment complete. Routes:"
oc get routes
