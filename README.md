# 🛡️ Sentinel Ops: AI-Powered Kubernetes Healer

**Sentinel Ops** is an autonomous infrastructure monitoring system that uses Artificial Intelligence to predict server failures before they happen.

Unlike traditional monitoring tools that alert you *after* a crash, Sentinel Ops uses a predictive model to forecast CPU spikes in real-time. If the predicted load exceeds a critical threshold, the system autonomously triggers a "Scaling Event" alert, visualizing the threat on a live React dashboard.

---

## 🏗️ Architecture

The system consists of four decoupled microservices running inside a **Kubernetes (Minikube)** cluster:

[Image of Sentinel Ops architecture diagram]

1.  **The Victim (Target App):** A Python container designed to simulate unstable workloads and sudden CPU spikes.
2.  **The Observer (Prometheus):** Scrapes raw CPU metrics from the Kubernetes kernel in real-time.
3.  **The Brain (AI Engine):** A FastAPI microservice that:
    * Queries Prometheus for historical data.
    * Runs a **Momentum-based Predictive Model** to forecast future load.
    * Determines system health (`NORMAL` vs `CRITICAL`).
4.  **The Dashboard (Frontend):** A React.js application that polls the Brain, visualizes "Actual vs. Predicted" CPU usage, and displays autonomous decision logs.

---

## 🚀 Features

* **Real-Time Forecasting:** Predicts CPU usage 2-3 steps into the future.
* **Autonomous Alerting:** Instantly flags system status as **CRITICAL** if predicted load > 50%.
* **Live Visualization:** Interactive charts built with `Recharts` showing the AI's "thought process" vs. reality.
* **Chaos Engineering Ready:** Includes tools to inject synthetic CPU loads ("CPU Burn") to test the system's reaction.

---

## 🛠️ Tech Stack

* **Orchestration:** Kubernetes (Minikube)
* **Metrics & Monitoring:** Prometheus
* **Backend / AI:** Python, FastAPI, Prometheus-API-Client
* **Frontend:** React.js, Axios, Recharts
* **Containerization:** Docker

---

## 📦 Project Structure

```bash
sentinel-ops/
├── k8s/                    # Kubernetes Manifests
│   ├── deployment.yaml     # Defines the Victim App & Brain
│   ├── prometheus.yaml     # Prometheus Configuration
│   └── service.yaml        # Networking & Load Balancing
├── ml-predictor/           # The AI Brain (Backend)
│   ├── src/
│   │   ├── main.py         # FastAPI Server & CORS Logic
│   │   ├── model.py        # Predictive Algorithm
│   │   └── prometheus.py   # Data Fetching Logic
│   └── Dockerfile
├── sentinel-dashboard/     # The React Frontend
│   ├── src/
│   │   ├── App.js          # UI Logic & Visualization
│   └── package.json
└── README.md
