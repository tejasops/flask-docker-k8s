from flask import Flask, jsonify, request, Response
from prometheus_client import (
    Counter, Histogram, Gauge,
    generate_latest, CONTENT_TYPE_LATEST
)
from datetime import datetime
import platform
import time
import os

app = Flask(__name__)

# ─── Prometheus Metrics ───────────────────────────────────────────────────────
REQUEST_COUNT = Counter(
    "flask_request_count_total",
    "Total HTTP request count",
    ["method", "endpoint", "status_code"]
)

REQUEST_LATENCY = Histogram(
    "flask_request_latency_seconds",
    "HTTP request latency in seconds",
    ["method", "endpoint"],
    buckets=[0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5]
)

TASKS_TOTAL = Gauge(
    "flask_tasks_total",
    "Current total number of tasks in the store"
)

TASKS_COMPLETED = Gauge(
    "flask_tasks_completed_total",
    "Current number of completed tasks"
)

# ─── Metrics middleware ───────────────────────────────────────────────────────
@app.before_request
def start_timer():
    request._start_time = time.time()

@app.after_request
def record_metrics(response):
    # Skip recording metrics for the /metrics endpoint itself
    if request.path == "/metrics":
        return response
    latency = time.time() - getattr(request, "_start_time", time.time())
    REQUEST_COUNT.labels(
        method=request.method,
        endpoint=request.path,
        status_code=response.status_code
    ).inc()
    REQUEST_LATENCY.labels(
        method=request.method,
        endpoint=request.path
    ).observe(latency)
    return response

# ─── Prometheus scrape endpoint ───────────────────────────────────────────────
@app.route("/metrics", methods=["GET"])
def metrics():
    return Response(generate_latest(), mimetype=CONTENT_TYPE_LATEST)

# ─── Health check ─────────────────────────────────────────────────────────────
@app.route("/health", methods=["GET"])
def health():
    return jsonify({
        "status":    "healthy",
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "hostname":  platform.node(),
    }), 200


# ─── Root ─────────────────────────────────────────────────────────────────────
@app.route("/", methods=["GET"])
def index():
    return jsonify({
        "message": "Flask REST API — Containerized with Docker, orchestrated with Kubernetes",
        "author":  "Tejaswararao Allada",
        "version": "2.0.0",
        "endpoints": {
            "GET  /":          "This response",
            "GET  /health":    "Health check",
            "GET  /info":      "System info",
            "GET  /metrics":   "Prometheus metrics scrape endpoint",
            "GET  /tasks":     "List all tasks",
            "POST /tasks":     "Create a task  { title: str }",
            "GET  /tasks/:id": "Get task by ID",
            "PATCH /tasks/:id":"Update task",
        }
    }), 200


# ─── System info ──────────────────────────────────────────────────────────────
@app.route("/info", methods=["GET"])
def info():
    return jsonify({
        "python_version": platform.python_version(),
        "os":             platform.system(),
        "hostname":       platform.node(),
        "env":            os.environ.get("APP_ENV", "development"),
    }), 200


# ─── In-memory task store ─────────────────────────────────────────────────────
tasks = {}
task_counter = 1


def _sync_task_gauges():
    """Keep Prometheus gauges in sync with the task store."""
    TASKS_TOTAL.set(len(tasks))
    TASKS_COMPLETED.set(sum(1 for t in tasks.values() if t["done"]))


@app.route("/tasks", methods=["GET"])
def get_tasks():
    return jsonify({
        "tasks": list(tasks.values()),
        "count": len(tasks),
    }), 200


@app.route("/tasks", methods=["POST"])
def create_task():
    global task_counter
    data = request.get_json()

    if not data or "title" not in data:
        return jsonify({"error": "Request body must include 'title'"}), 400

    task = {
        "id":         task_counter,
        "title":      data["title"],
        "done":       False,
        "created_at": datetime.utcnow().isoformat() + "Z",
    }
    tasks[task_counter] = task
    task_counter += 1
    _sync_task_gauges()

    return jsonify(task), 201


@app.route("/tasks/<int:task_id>", methods=["GET"])
def get_task(task_id):
    task = tasks.get(task_id)
    if not task:
        return jsonify({"error": f"Task {task_id} not found"}), 404
    return jsonify(task), 200


@app.route("/tasks/<int:task_id>", methods=["PATCH"])
def update_task(task_id):
    task = tasks.get(task_id)
    if not task:
        return jsonify({"error": f"Task {task_id} not found"}), 404

    data = request.get_json()
    if "done" in data:
        task["done"] = bool(data["done"])
    if "title" in data:
        task["title"] = data["title"]
    _sync_task_gauges()

    return jsonify(task), 200


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
