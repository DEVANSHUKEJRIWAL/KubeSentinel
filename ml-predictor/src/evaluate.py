"""Walk-forward evaluation of the ARIMA forecaster vs naive baselines.

Produces benchmarks/forecast_eval.{json,md} with sMAPE / MAPE / RMSE for
one-step-ahead forecasts on held-out data, comparing:
  - ARIMA         (model.TrafficPredictor)
  - naive         (last observed value)
  - seasonal-naive(value from one season ago)

The ARIMA sMAPE in the report is the résumé number -- but ONLY when the input
series is a real CPU capture. On the committed synthetic sample it measures the
machinery, not production behaviour; the report marks which source was used.

Run on real data:   python evaluate.py --source prometheus
Run on the sample:  python evaluate.py --source benchmarks/cpu_series_sample.csv
Regenerate sample:  python evaluate.py --gen benchmarks/cpu_series_sample.csv
Self-check:         python evaluate.py --selfcheck
"""
import argparse
import json
import math
import os
import sys

# Allow "python src/evaluate.py" and "python evaluate.py" (src on path) alike.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from model import TrafficPredictor


# ---------- metrics ----------

def smape(actual, pred):
    """Symmetric MAPE (%). 0 = perfect. Skips points where both are 0."""
    num = den = n = 0.0
    for a, f in zip(actual, pred):
        d = abs(a) + abs(f)
        if d == 0:
            continue
        num += 2 * abs(f - a)
        den += d
        n += 1
    return 100.0 * num / den if den else 0.0


def mape(actual, pred):
    """MAPE (%). Skips points where actual is 0 (undefined there)."""
    vals = [abs((a - f) / a) for a, f in zip(actual, pred) if a != 0]
    return 100.0 * sum(vals) / len(vals) if vals else 0.0


def rmse(actual, pred):
    sq = [(a - f) ** 2 for a, f in zip(actual, pred)]
    return math.sqrt(sum(sq) / len(sq)) if sq else 0.0


# ---------- walk-forward ----------

def walk_forward(series, season, initial):
    """One-step-ahead forecasts from `initial` to end, refitting each step.

    Returns (actuals, {method: predictions}). ARIMA refits on the growing
    history at every step -- honest held-out evaluation, no peeking ahead.
    """
    predictor = TrafficPredictor()
    actuals, arima, naive, snaive = [], [], [], []
    for t in range(initial, len(series)):
        history = series[:t]
        actuals.append(series[t])
        arima.append(predictor.predict_next_step(history))
        naive.append(history[-1])
        snaive.append(history[-season] if t >= season else history[-1])
    return actuals, {"arima": arima, "naive": naive, "seasonal_naive": snaive}


def evaluate(series, season, initial):
    actuals, preds = walk_forward(series, season, initial)
    return {
        method: {
            "sMAPE": round(smape(actuals, p), 3),
            "MAPE": round(mape(actuals, p), 3),
            "RMSE": round(rmse(actuals, p), 6),
        }
        for method, p in preds.items()
    }, len(actuals)


# ---------- data sources ----------

def load_csv(path):
    import pandas as pd
    df = pd.read_csv(path)
    return df["cpu_usage"].astype(float).tolist()


def load_prometheus():
    from prometheus import PrometheusClient
    df = PrometheusClient().fetch_cpu_history()
    if df.empty:
        raise SystemExit("Prometheus returned no data -- is the port-forward up and victim-app scraped?")
    return df["cpu_usage"].astype(float).tolist()


def generate_synthetic(n=120, seed=42):
    """Seeded, reproducible SYNTHETIC CPU series: baseline + daily-ish wave +
    two traffic spikes + noise. Clearly not real workload data."""
    import numpy as np
    rng = np.random.default_rng(seed)
    t = np.arange(n)
    base = 0.05 + 0.02 * np.sin(2 * np.pi * t / 40)          # slow oscillation
    spikes = np.zeros(n)
    for start in (45, 90):                                    # two load spikes
        spikes += 0.12 * np.exp(-((t - start) ** 2) / (2 * 4 ** 2))
    noise = rng.normal(0, 0.004, n)
    return np.clip(base + spikes + noise, 0, None).round(6).tolist()


# ---------- report ----------

def write_reports(results, meta, outdir):
    os.makedirs(outdir, exist_ok=True)
    payload = {"meta": meta, "results": results}
    with open(os.path.join(outdir, "forecast_eval.json"), "w") as f:
        json.dump(payload, f, indent=2)

    synthetic = meta["source_kind"] == "synthetic"
    lines = ["# Forecast Evaluation", ""]
    if synthetic:
        lines += [
            "> ⚠️ **SYNTHETIC input series** — these numbers measure the evaluation",
            "> machinery, not production behaviour. Do **not** put them on a résumé.",
            "> Re-run with `--source prometheus` on a real capture for the real number.",
            "",
        ]
    lines += [
        f"- Source: `{meta['source']}` ({meta['source_kind']})",
        f"- Series length: {meta['series_len']} points; held-out one-step forecasts: {meta['n_forecasts']}",
        f"- Walk-forward initial window: {meta['initial']}; seasonal-naive period: {meta['season']}",
        "",
        "| Method | sMAPE (%) | MAPE (%) | RMSE |",
        "|---|---|---|---|",
    ]
    for method in ("arima", "naive", "seasonal_naive"):
        r = results[method]
        lines.append(f"| {method} | {r['sMAPE']} | {r['MAPE']} | {r['RMSE']} |")
    best = min(results, key=lambda m: results[m]["sMAPE"])
    lines += ["", f"Lowest sMAPE: **{best}** ({results[best]['sMAPE']}%)."]
    with open(os.path.join(outdir, "forecast_eval.md"), "w") as f:
        f.write("\n".join(lines) + "\n")


def selfcheck():
    # Perfect predictor -> ~0 error; naive on a rising ramp -> positive error.
    ramp = [float(i) for i in range(1, 21)]
    assert smape(ramp, ramp) == 0.0
    assert rmse(ramp, ramp) == 0.0
    naive_pred = ramp[:-1]  # predicting next = current, on a +1 ramp
    assert smape(ramp[1:], naive_pred) > 0
    assert rmse(ramp[1:], naive_pred) == 1.0  # always off by exactly 1
    # ARIMA should beat naive on the synthetic series (it has structure).
    series = generate_synthetic()
    results, _ = evaluate(series, season=40, initial=30)
    assert results["arima"]["sMAPE"] <= results["naive"]["sMAPE"], results
    print("selfcheck OK")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", default="benchmarks/cpu_series_sample.csv",
                    help="CSV path, or 'prometheus', or 'synthetic'")
    ap.add_argument("--season", type=int, default=40, help="seasonal-naive period (steps)")
    ap.add_argument("--initial", type=int, default=30, help="walk-forward initial window")
    ap.add_argument("--out", default="benchmarks", help="output dir")
    ap.add_argument("--gen", metavar="PATH", help="write a synthetic sample CSV here and exit")
    ap.add_argument("--selfcheck", action="store_true")
    args = ap.parse_args()

    if args.selfcheck:
        return selfcheck()

    if args.gen:
        import pandas as pd
        series = generate_synthetic()
        os.makedirs(os.path.dirname(args.gen) or ".", exist_ok=True)
        pd.DataFrame({"timestamp": range(len(series)), "cpu_usage": series}).to_csv(args.gen, index=False)
        print(f"wrote {len(series)}-point SYNTHETIC series to {args.gen}")
        return

    if args.source == "prometheus":
        series, kind = load_prometheus(), "prometheus"
    elif args.source == "synthetic":
        series, kind = generate_synthetic(), "synthetic"
    else:
        series = load_csv(args.source)
        # A CSV generated by --gen is synthetic; a real capture is not. We can't
        # tell from the numbers, so flag the shipped sample by its known name.
        kind = "synthetic" if os.path.basename(args.source) == "cpu_series_sample.csv" else "prometheus"

    results, n = evaluate(series, args.season, args.initial)
    meta = {
        "source": args.source, "source_kind": kind,
        "series_len": len(series), "n_forecasts": n,
        "initial": args.initial, "season": args.season,
    }
    write_reports(results, meta, args.out)
    print(json.dumps(results, indent=2))
    print(f"\nwrote {args.out}/forecast_eval.json and .md (source: {kind})")


if __name__ == "__main__":
    main()
