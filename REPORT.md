# Healthcare Microservices — Technical Report

Date: 2026-01-18

## Executive Summary

This repository contains a small healthcare microservices demo composed of these services:
- `auth-service` (FastAPI) — user registration, login, JWT verification
- `patient-service` (FastAPI) — patient-facing views and patient list
- `doctor-service` (FastAPI) — doctor dashboard and doctor profiles
- `appointment-service` (FastAPI) — appointment scheduling and lookup
- `medical-records-service` (FastAPI) — medical records API
- `billing-service` (FastAPI) — billing/invoice API
- `postgres` — PostgreSQL database

Each service exposes a small static frontend under `/static` (HTML/CSS/JS) and a JSON REST API. Services run within Docker and are coordinated with `docker-compose` for local development. OpenShift manifests are provided in the `openshift/` directory and a `deploy.sh` script automates applying them to a cluster.

This report documents the architecture, key implementation details, and contains an expanded deployment section showing how to run in OpenShift, how to prepare images, and operational tips.

---

## Architecture Overview

- Services: each service is a self-contained FastAPI app; each service manages its own endpoints and static assets.
- Data: a single PostgreSQL instance (database `healthcare`) is used by services (via DB host/env variables). Services use SQLAlchemy ORM and local DB migrations were not included — schema creation happens via SQLAlchemy `Base.metadata.create_all()` during startup.
- Auth: `auth-service` issues JWT tokens and provides a `/verify` endpoint used by other services via an HTTP call to validate Authorization headers.
- Frontends: static files served by each service at `/` and `/static/*`. Frontend scripts talk to other services via http://<service>:<port> internal URLs or to `/` for static content when tested locally.
- Local orchestration: `docker-compose.yml` runs all services and Postgres.

High-level diagram (text):

```
Browser <-> auth:8000 (login/register)
        <-> appointment:8003 (booking, appointments)
        <-> patient:8001 (patient UI)
        <-> doctor:8002 (doctor UI)
        <-> records:8004
        <-> billing:8006
All services <-> Postgres (5432)
```

---

## Key Implementation Notes

- JWT-based auth and token storage: frontends store `access_token`, `role`, and `user_id` in `localStorage` and send `Authorization: Bearer <token>` on protected calls.
- Registration: the `register` page collects role-specific fields and posts to `auth-service`. Some profile metadata (doctor/patient details) may be forwarded to other services by the frontend, but the core `auth` DB stores the basic user record — consider adding dedicated profile tables for full persistence.
- Error handling: frontends now show backend error messages for easier debugging (e.g., token invalid, missing auth header).
- Health checks: services expose `/health` endpoints used in OpenShift readiness/liveness probes.

---

## Deployment (OpenShift) — Detailed Guide (emphasis)

This project contains an `openshift/` directory with:
- `auth-service-dc.yaml`, `patient-service-dc.yaml`, `all-services-dc.yaml` — DeploymentConfigs and Service specs for each service
- `postgres.yaml` and `persistent-volumes.yaml` — Postgres Secret, PVC, Deployment and Service
- `secrets-configmap.yaml` — `app-secrets` Secret for JWT and `app-config` ConfigMap for service URLs
- `routes.yaml` — Routes to expose services externally (doctor, appointment, records, billing)
- `deploy.sh` — deployment helper script (applies manifests and waits for rollouts)

### Pre-requisites

- Access to an OpenShift cluster and `oc` CLI installed and logged in.
- Container images for each service made available to the OpenShift cluster. The provided manifests reference images using simple names like `auth-service:latest`. These will not work unless the cluster can pull these names (common options below).
- Appropriate resource quotas/limits on the cluster (manifests include modest resource requests/limits which may need tuning).

### Image options (pick one)

1. Push images to a registry (recommended):
   - Build and tag locally, then push to Docker Hub / Quay / private registry.
   - Update the `image` fields in the OpenShift YAMLs to `registry.example.com/your-repo/auth-service:tag` (or use parameter substitution). Example commands:

```bash
# Build and push (example)
docker build -t your-registry/your-org/auth-service:latest ./auth-service
docker push your-registry/your-org/auth-service:latest
# Repeat for other services
```

2. Build inside OpenShift using `oc new-build` / ImageStreams:
   - Use `oc new-build --strategy=docker --binary --name=auth-service` and `oc start-build` with local context to build images inside the cluster (useful if registry access is restricted). This can be scripted into CI.

3. Use local registry or mirror images into the cluster's registry (if available).

### Using the provided `deploy.sh`

1. Make sure `oc` is logged in:
```bash
oc login --server=https://api.your-openshift:6443 -u <user> -p <pass>
```
2. Run the script (default project name `clinic-app`):
```bash
cd openshift
chmod +x deploy.sh
./deploy.sh clinic-app
```

What `deploy.sh` does:
- Creates or switches to the project
- Applies `secrets-configmap.yaml`
- Applies persistent volumes and Postgres
- Applies `auth` and `patient` DeploymentConfigs and other services
- Applies `routes.yaml`
- Waits for each deploymentconfig or deployment to roll out and displays routes at the end

### Important deployment considerations

- Secrets: change `app-secrets.jwt-secret` (and DB credentials) to secure values for production. The example secret in `postgres.yaml` should be updated.
- Database startup: Postgres must be ready before services rely on it. The script waits for rollouts but you should confirm DB readiness and run migrations if you move to a production-ready schema (SQLAlchemy `create_all` is OK for demo only).
- Persistent storage: `postgres.yaml` uses a PVC (`postgres-pvc`); the cluster must have storage class and PVs available.
- Routes vs Ingress: manifests use OpenShift `Route` resources. If your cluster uses Ingress (Kubernetes), convert to `Ingress` resources or expose via a load balancer.

### Rollbacks and updates

- Update images by pushing a new tag and editing the DeploymentConfig `image` field, then trigger a rollout: `oc rollout latest dc/auth-service`.
- Check status: `oc get pods`, `oc rollout status dc/auth-service` and `oc logs dc/auth-service-<id>`.

---

## CI/CD Recommendations (brief)

- Build and push images on each commit using GitHub Actions / GitLab CI.
- Example GitHub Actions steps:
  - Build Docker images for all services
  - Tag and push to a registry
  - Use `oc apply` (or `kubectl apply`) in a deployment job to update manifests and trigger rollouts
- For Blue/Green or Canary: use OpenShift routes and separate DeploymentConfigs to traffic-shift gradually.

---

## Operational & Troubleshooting Tips

- Useful `oc` commands:
  - `oc get pods -o wide`
  - `oc logs dc/auth-service --follow` or `oc logs <pod>`
  - `oc rollout status dc/<service>`
  - `oc get routes` to see external endpoints
- Health check endpoints: call `http://<pod-ip>:<port>/health` to verify readiness/liveness.
- If `Invalid token` shows in frontends: ensure `localStorage.access_token` is present and that `auth-service` `/verify` endpoint is reachable from the caller.

---

## Security Considerations

- Use TLS termination at the cluster edge (Routes can have TLS config).
- Do not store secrets in plaintext in manifests for production; integrate with an external secrets manager (e.g., Vault) or use OpenShift secrets with appropriate RBAC.
- Harden resource limits and enable network policies to restrict service-to-service communication if required.

---

## Next Steps / Improvements

- Add DB migrations (Alembic) and a migration job during deployment.
- Persist extended user profile fields into dedicated patient/doctor tables; migrate frontend flows to POST into those endpoints.
- Add authentication/authorization checks server-side for all admin/protected endpoints and introduce role-based access control (RBAC) in code.
- Add monitoring (Prometheus metrics endpoints) and logging/aggregator (ELK or EFK stack) integration.
- Add automated tests and CI pipeline to run unit/integration tests and deploy to a staging project before production.

---

## Appendix: Useful commands

- Build & push images (example):
```bash
# build
docker build -t registry.example.com/your-org/auth-service:latest ./auth-service
# push
docker push registry.example.com/your-org/auth-service:latest
```

- Apply OpenShift manifests (manual):
```bash
oc project clinic-app
oc apply -f openshift/secrets-configmap.yaml
oc apply -f openshift/postgres.yaml
oc apply -f openshift/auth-service-dc.yaml
oc apply -f openshift/all-services-dc.yaml
oc apply -f openshift/routes.yaml
```

- Check rollouts:
```bash
oc rollout status dc/auth-service
oc get pods -o wide
oc logs dc/auth-service --follow
```

---

