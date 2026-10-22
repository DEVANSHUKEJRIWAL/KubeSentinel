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
    * Runs a **statsmodels ARIMA model** (with 90% prediction intervals) to forecast future load.
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
```

---

## 📊 Methodology & Benchmarks

> **Ground rule: no number in this README is written unless it was measured on a
> committed run.** Cells below marked _pending_ are filled by running the command
> shown — they are not estimated or invented.

### 1. Forecast accuracy (`ml-predictor`)

* **Model:** `statsmodels` ARIMA(2,1,1), re-fit on the recent Prometheus CPU
  window each request; emits a one-step forecast plus a 90% prediction interval
  (the control plane scales on the interval's **upper bound**, not current CPU).
  Naive last-value fallback if a fit fails.
* **Evaluation:** walk-forward, one-step-ahead, re-fit at every step (strict
  held-out, no look-ahead). Metrics **sMAPE / MAPE / RMSE** for ARIMA vs a
  **naive (last-value)** and a **seasonal-naive** baseline — `ml-predictor/src/evaluate.py`.
* **Reproduce:** `make eval-prom` (real Prometheus capture → the résumé number)
  or `make eval` (committed *synthetic* sample, illustrative only).

### 2. Predictive vs reactive experiment (`loadtest/`, `benchmarks/`)

* **Identical spike** (k6 `loadtest/k6/spike.js` or Locust `loadtest/locust/locustfile.py`):
  30s warm-up → 30s ramp → 60s sustained peak → 30s ramp-down.
* **Reactive baseline:** the plain CPU HPA (`k8s-manifests/hpa-victim.yaml`) alone
  — it scales out *after* CPU crosses target.
* **Predictive:** same HPA **plus** the Sentinel agent, which raises the HPA's
  `minReplicas` *ahead* of the forecast spike (guardrails: floor 1, max cap,
  15s rate-limit, 60s stabilization window), then relaxes it.
* `loadtest/capture.sh` records the replica timeline + p95/p99 + error rate;
  `benchmarks/compare.py` overlays both runs into `compare.png` + `compare.md`.
  Step-by-step runbook: `loadtest/README.md`.

### 3. Results

⏳ **Pending a cluster run — not yet measured.** The only figure measured so far
is ARIMA on a *synthetic* series (sMAPE **8.04%** vs naive **11.25%**), which is
illustrative only and **not** résumé-grade until re-run on real data.

| Metric | Reactive | Predictive | Fill with |
|---|---|---|---|
| One-step CPU sMAPE | naive: _pending_ | ARIMA: _pending_ | `make eval-prom` |
| p99 latency during spike | _pending_ | _pending_ | `capture.sh` → `make compare` |
| Error rate during spike | _pending_ | _pending_ | `capture.sh` → `make compare` |
| Failed requests | _pending_ | _pending_ | `capture.sh` → `make compare` |

Verify forecasting code locally (no cluster): `make test` (11 unit tests) and `make eval`.
