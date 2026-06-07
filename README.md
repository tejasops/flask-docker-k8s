# Flask REST API — Docker + Kubernetes + Prometheus + Grafana

A production-style Python Flask REST API containerized with Docker (multi-stage build, non-root user, Gunicorn), orchestrated on Kubernetes (Minikube) with rolling updates and health probes, and fully observable with **Prometheus metrics** and a **Grafana dashboard**.

## Architecture

```
                        ┌─────────────────────────────────────┐
                        │         Docker Compose Stack         │
                        │                                      │
  HTTP Request ──────▶  │  flask-api :5000                     │
                        │       │  /metrics endpoint           │
                        │       ▼                              │
                        │  prometheus :9090  ◀─── scrapes      │
                        │       │                              │
                        │       ▼                              │
                        │  grafana :3000  ◀─── queries PromQL  │
                        └─────────────────────────────────────┘
```

## Live Demo Screenshots

### Grafana Monitoring Dashboard
![Grafana Dashboard](screenshots/Screenshot%202026-06-08%20005748.png)

### Prometheus Targets
![Prometheus Targets](screenshots/Screenshot%202026-06-08%20005622.png)

### Flask REST API
![Flask API](screenshots/Screenshot%202026-06-08%20005422.png)

## What's New in v2.0 (Prometheus + Grafana)

| Addition | Details |
|---|---|
| `/metrics` endpoint | Prometheus scrape endpoint on the Flask app |
| `flask_request_count_total` | Counter — total requests by method, endpoint, status code |
| `flask_request_latency_seconds` | Histogram — p50/p95/p99 latency per endpoint |
| `flask_tasks_total` | Gauge — live count of tasks in the store |
| `flask_tasks_completed_total` | Gauge — live count of completed tasks |
| Prometheus container | Scrapes Flask every 15s, stores 7 days of data |
| Grafana container | Auto-provisioned datasource + pre-built dashboard |
| K8s monitoring namespace | `prometheus.yaml` + `grafana.yaml` with RBAC for pod discovery |

## Project Structure

```
flask-docker-k8s/
├── app.py                    # Flask app with Prometheus instrumentation
├── requirements.txt          # Added prometheus-client==0.20.0
├── Dockerfile                # Multi-stage build, non-root user
├── docker-compose.yml        # Flask + Prometheus + Grafana
├── .gitignore
├── monitoring/
│   ├── prometheus.yml        # Scrape config (Flask job)
│   └── grafana/
│       ├── dashboards/
│       │   └── flask-api.json          # Pre-built dashboard (auto-loaded)
│       └── provisioning/
│           ├── datasources/
│           │   └── prometheus.yml      # Auto-connects Grafana → Prometheus
│           └── dashboards/
│               └── dashboard.yml       # Dashboard provider config
└── k8s/
    ├── deployment.yaml       # Flask — 2 replicas, rolling updates
    ├── service.yaml          # ClusterIP service
    └── monitoring/
        ├── prometheus.yaml   # Prometheus deployment + RBAC for pod discovery
        └── grafana.yaml      # Grafana deployment + secret
```

## API Endpoints

| Method | Path | Description |
|---|---|---|
| GET | `/` | API info |
| GET | `/health` | Health check (K8s probes) |
| GET | `/info` | System/env info |
| **GET** | **`/metrics`** | **Prometheus scrape endpoint** |
| GET | `/tasks` | List all tasks |
| POST | `/tasks` | Create task `{ "title": "..." }` |
| GET | `/tasks/:id` | Get task by ID |
| PATCH | `/tasks/:id` | Update task |

## Quick Start — Docker Compose

```bash
git clone https://github.com/tejasops/flask-docker-k8s.git
cd flask-docker-k8s

docker compose up --build
```

| Service | URL |
|---|---|
| Flask API | http://localhost:5000 |
| Prometheus | http://localhost:9090 |
| Grafana | http://localhost:3000 (admin / admin123) |

### Generate some traffic to see metrics

```bash
# Create tasks
curl -X POST http://localhost:5000/tasks \
  -H "Content-Type: application/json" -d '{"title":"Learn Prometheus"}'

curl -X POST http://localhost:5000/tasks \
  -H "Content-Type: application/json" -d '{"title":"Build Grafana dashboard"}'

# Hit several endpoints
curl http://localhost:5000/tasks
curl http://localhost:5000/health
curl http://localhost:5000/info

# Trigger a 404
curl http://localhost:5000/tasks/999

# View raw metrics
curl http://localhost:5000/metrics
```

Then open Grafana at **http://localhost:3000** → Dashboards → Flask API.

## Kubernetes Deployment (Minikube)

```bash
# Start Minikube
minikube start

eval $(minikube docker-env)
docker build -t tejasops/flask-api:latest .

# Deploy Flask app
kubectl apply -f k8s/deployment.yaml
kubectl apply -f k8s/service.yaml

# Deploy monitoring namespace (Prometheus + Grafana)
kubectl apply -f k8s/monitoring/prometheus.yaml
kubectl apply -f k8s/monitoring/grafana.yaml

# Check everything is running
kubectl get pods -n monitoring
kubectl get pods

# Access Flask API
kubectl port-forward service/flask-api-service 8080:80

# Access Prometheus
kubectl port-forward -n monitoring service/prometheus 9090:9090

# Access Grafana
kubectl port-forward -n monitoring service/grafana 3000:3000
```

### Grafana login: admin / admin123
> In production, replace the secret: `kubectl create secret generic grafana-secret --namespace monitoring --from-literal=admin-password='StrongPassword'`

## PromQL Queries to Try in Prometheus

```promql
# Total request rate across all endpoints
sum(rate(flask_request_count_total[1m]))

# Error rate (4xx + 5xx)
sum(rate(flask_request_count_total{status_code=~"4..|5.."}[1m]))

# p95 latency per endpoint
histogram_quantile(0.95, sum(rate(flask_request_latency_seconds_bucket[5m])) by (le, endpoint))

# Current task count
flask_tasks_total

# Requests broken down by status code
sum(flask_request_count_total) by (status_code)
```

## What I Learned

**Prometheus instrumentation:** The `prometheus_client` library instruments Flask via a `/metrics` endpoint. Counters track totals that only increase (requests, errors). Histograms bucket latency observations to compute percentiles. Gauges track values that go up and down (task count).

**Why p95/p99 matters:** Average latency hides tail latency. If 95% of requests are under 50ms but 5% take 2 seconds, the average looks fine but users are suffering. p95/p99 expose this.

**Grafana provisioning:** Rather than manually clicking through the UI, datasources and dashboards can be declared as YAML/JSON files and mounted into the container — meaning the monitoring setup is version-controlled and reproducible.

**Kubernetes RBAC for Prometheus:** In K8s, Prometheus needs permission to call the API server to discover pods. The `ClusterRole` + `ClusterRoleBinding` + `ServiceAccount` in `prometheus.yaml` grant exactly the permissions needed (get/list/watch pods, endpoints, services) — nothing more.

## Skills Demonstrated

- Python Flask REST API + Prometheus instrumentation
- Docker multi-stage builds, Compose, networking
- Kubernetes Deployments, Services, RBAC, health probes
- Prometheus (metrics types, scrape config, PromQL)
- Grafana (dashboard provisioning, datasource config)
- Observability best practices (RED method: Rate, Errors, Duration)
