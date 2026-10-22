import math
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, PlainTextResponse
from prometheus_client import Gauge, generate_latest, CONTENT_TYPE_LATEST

from prometheus import PrometheusClient
from model import TrafficPredictor

# Scaling knobs (env-overridable so the same image works across clusters).
CPU_PER_REPLICA = float(os.getenv("SENTINEL_CPU_PER_REPLICA", "0.05"))  # cores one pod absorbs
SCALE_THRESHOLD = float(os.getenv("SENTINEL_SCALE_THRESHOLD", "0.05"))  # upper-bound cores that trips scale-up
MIN_REPLICAS = int(os.getenv("SENTINEL_MIN_REPLICAS", "1"))
MAX_REPLICAS = int(os.getenv("SENTINEL_MAX_REPLICAS", "10"))

app = FastAPI(title="Sentinel Brain")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["GET"], allow_headers=["*"])

prom_client = PrometheusClient()
predictor = TrafficPredictor()

PREDICTED_CPU = Gauge("sentinel_predicted_cpu", "Forecast upper-bound CPU (cores) for next step")
FORECAST_ERROR = Gauge("sentinel_forecast_error", "Abs % error of the previous one-step forecast vs observed")

# Live one-step forecast error: remember last prediction, score it when the
# next observation lands. ponytail: single-step tracker, not a rolling window.
_last_predicted = {"mean": None}


@app.get("/healthz")
def healthz():
    return {"status": "ok"}


@app.get("/metrics")
def metrics():
    return PlainTextResponse(generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.get("/predict")
def predict():
    df = prom_client.fetch_cpu_history()
    if df.empty:
        return JSONResponse({
            "status": "warning",
            "message": "No data found. victim-app is up but Prometheus hasn't scraped it yet. Wait ~2 minutes.",
        })

    cpu = df["cpu_usage"].astype(float).tolist()
    current = cpu[-1]

    # Score the previous forecast against what we now observe.
    if _last_predicted["mean"] is not None and (abs(current) + abs(_last_predicted["mean"])) > 0:
        FORECAST_ERROR.set(100.0 * 2 * abs(_last_predicted["mean"] - current)
                           / (abs(_last_predicted["mean"]) + abs(current)))

    mean, lower, upper = predictor.forecast(cpu, h=1, alpha=0.1)
    _last_predicted["mean"] = mean
    PREDICTED_CPU.set(upper)

    # Decide on the predicted UPPER bound, not current CPU -> scale before the peak.
    recommended = max(MIN_REPLICAS, min(MAX_REPLICAS, math.ceil(upper / CPU_PER_REPLICA)))
    action = "scale_up" if upper > SCALE_THRESHOLD else "maintain"

    return {
        "current_cpu": current,
        "predicted_cpu": mean,
        "interval": {"lower": lower, "upper": upper},
        "recommended_replicas": recommended,
        "action": action,
    }
