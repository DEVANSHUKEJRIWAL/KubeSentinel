# Load-test harness (Phase 0)

Repeatable spike against `victim-app`, plus a capture script that records the
failed-request %, p95/p99 latency, and the replica count over time. Running the
**same** spike against (a) the reactive HPA alone and (b) the predictive system
is what Phase 4's `compare.py` turns into the predictive-vs-reactive chart.

## Spike profile (identical in both tools)
30s warm-up → 30s ramp to 80 → 60s sustained peak → 30s ramp down.
See [`k6/spike.js`](k6/spike.js) and [`locust/locustfile.py`](locust/locustfile.py).

## One-time cluster setup
```bash
# metrics-server (the HPA needs it to read CPU)
kubectl apply -f https://github.com/kubernetes-sigs/metrics-server/releases/latest/download/components.yaml
# (kind/minikube: add  --kubelet-insecure-tls  to the metrics-server args)

kubectl apply -f ../deploy/02-victim-app.yaml
kubectl apply -f ../k8s-manifests/hpa-victim.yaml      # reactive baseline HPA
kubectl expose deploy victim-app --name victim-app --port 80 --target-port 80 || true
```

## Run the experiment
Install a load tool: `brew install k6`  or  `pip install locust`.

```bash
# Route traffic to victim-app (leave running in another terminal)
kubectl port-forward svc/victim-app 8080:80

# (a) REACTIVE baseline -- HPA only, Sentinel agent NOT running
./capture.sh reactive k6          # or: ./capture.sh reactive locust

# (b) PREDICTIVE -- deploy brain + agent, then run the identical spike
kubectl apply -f ../k8s-manifests/brain.yaml
kubectl apply -f ../k8s-manifests/agent.yaml
./capture.sh predictive k6
```

Each run writes into `../benchmarks/`:
- `<label>_replicas.csv` — `timestamp,replicas` timeline
- `<label>_load.json` (k6) or `<label>_load_stats.csv` (locust) — p95/p99 + error rate

Watch the difference live: `kubectl get hpa victim-app-hpa -w` — in predictive
mode `minReplicas` rises *before* the spike; in reactive mode replicas climb
only *after* CPU crosses the target.

> No numbers are committed yet — they come from running the two captures on a
> real cluster. Phase 4 (`compare.py`) overlays the two `*_replicas.csv` +
> latency results into the predictive-vs-reactive chart.
