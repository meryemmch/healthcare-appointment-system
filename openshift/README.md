OpenShift deployment

This folder contains OpenShift manifests and a one-shot deploy script to deploy the healthcare microservices to an OpenShift cluster.

Files included:
- `auth-service-dc.yaml` — DeploymentConfig, Service and Route for the auth service.
- `patient-service-dc.yaml` — DeploymentConfig, Service and Route for the patient service.
- `all-services-dc.yaml` — DeploymentConfigs and Services for doctor, appointment, medical-records and billing services.
- `postgres.yaml` — Postgres Secret, PVC and Deployment and Service.
- `persistent-volumes.yaml` — Persistent volumes claims / PVs (if applicable to your cluster).
- `secrets-configmap.yaml` — Secrets and ConfigMap used by services.
- `routes.yaml` — Routes for doctor/appointment/medical-records/billing (auth and patient routes are in their DC YAMLs).
- `deploy.sh` — Helper script to apply resources to an OpenShift project.

Quick deployment

1. Log in to your OpenShift cluster using the `oc` CLI:

```bash
oc login --server=https://api.your-openshift:6443 -u <user> -p <pass>
```

2. Deploy to a new project (defaults to `clinic-app`):

```bash
cd openshift
chmod +x deploy.sh
./deploy.sh clinic-app
```

Notes & assumptions

- The manifests reference container images with names like `auth-service:latest` and `doctor-service:latest`. You must ensure these images are available to the OpenShift cluster (push them to a registry the cluster can pull from, or build within OpenShift using `oc new-build`).
- The script applies resources in an order intended to satisfy dependencies (secrets/configmaps -> DB -> services -> routes).
- For production use, update secrets, resource requests/limits, number of replicas and image references appropriately.
- If your OpenShift cluster uses a different namespace/project naming policy, pass the project name to the script.
