"""Phase 4: overlay the reactive vs predictive experiment.

Reads the capture files written by loadtest/capture.sh for two runs (labels
'reactive' and 'predictive') and produces, in this benchmarks/ dir:
  - compare.png : replica-count timeline for both modes (the money shot)
  - compare.md  : summary table (p95/p99 latency, error rate, failed requests)

Usage (after both captures):  python compare.py
Self-check on dummy data:     python compare.py --selfcheck
"""
import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))


def load_replicas(path):
    import pandas as pd
    df = pd.read_csv(path)
    df["t"] = df["timestamp"] - df["timestamp"].iloc[0]  # elapsed seconds
    return df


def load_load(label, benchdir):
    """Load aggregate latency/error stats: k6 JSON preferred, else locust CSV."""
    j = os.path.join(benchdir, f"{label}_load.json")
    if os.path.exists(j):
        with open(j) as f:
            d = json.load(f)
        return {"p95_ms": d.get("p95_ms"), "p99_ms": d.get("p99_ms"),
                "error_rate": d.get("error_rate"), "failed": d.get("failed_requests"),
                "total": d.get("total_requests")}
    c = os.path.join(benchdir, f"{label}_load_stats.csv")
    if os.path.exists(c):
        import pandas as pd
        row = pd.read_csv(c)
        agg = row[row["Name"] == "Aggregated"].iloc[0]
        total = float(agg["Request Count"])
        return {"p95_ms": float(agg["95%"]), "p99_ms": float(agg["99%"]),
                "error_rate": float(agg["Failure Count"]) / total if total else 0.0,
                "failed": int(agg["Failure Count"]), "total": int(total)}
    return None


def make_chart(reactive_df, predictive_df, out_png):
    import matplotlib
    matplotlib.use("Agg")  # headless
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(9, 4))
    ax.plot(reactive_df["t"], reactive_df["replicas"], label="reactive HPA",
            color="#d1495b", drawstyle="steps-post", linewidth=2)
    ax.plot(predictive_df["t"], predictive_df["replicas"], label="predictive (Sentinel)",
            color="#30638e", drawstyle="steps-post", linewidth=2)
    ax.set_xlabel("seconds since start")
    ax.set_ylabel("victim-app replicas")
    ax.set_title("Replica count during an identical spike: predictive vs reactive")
    ax.legend()
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(out_png, dpi=120)
    plt.close(fig)


def summary_md(loads):
    lines = ["| metric | reactive | predictive |", "|---|---|---|"]

    def row(name, key, fmt):
        def cell(d):
            return fmt(d[key]) if d and d.get(key) is not None else "—"
        lines.append(f"| {name} | {cell(loads['reactive'])} | {cell(loads['predictive'])} |")

    row("p95 latency (ms)", "p95_ms", lambda v: f"{v:.1f}")
    row("p99 latency (ms)", "p99_ms", lambda v: f"{v:.1f}")
    row("error rate", "error_rate", lambda v: f"{v * 100:.2f}%")
    row("failed requests", "failed", lambda v: f"{int(v)}")
    row("total requests", "total", lambda v: f"{int(v)}")
    return "\n".join(lines)


def run(benchdir, reactive="reactive", predictive="predictive", out=None):
    out = out or benchdir
    rdf = load_replicas(os.path.join(benchdir, f"{reactive}_replicas.csv"))
    pdf = load_replicas(os.path.join(benchdir, f"{predictive}_replicas.csv"))
    png = os.path.join(out, "compare.png")
    make_chart(rdf, pdf, png)

    loads = {"reactive": load_load(reactive, benchdir),
             "predictive": load_load(predictive, benchdir)}
    md = ["# Predictive vs Reactive", "",
          f"![replica timeline](compare.png)", "",
          summary_md(loads), "",
          "Reactive scales *after* CPU crosses the target; predictive raises "
          "minReplicas *before* the spike (see the earlier step in the chart)."]
    with open(os.path.join(out, "compare.md"), "w") as f:
        f.write("\n".join(md) + "\n")
    return png, loads


def selfcheck():
    """Prove the pipeline runs end-to-end on DUMMY data in a temp dir."""
    import tempfile
    import pandas as pd
    with tempfile.TemporaryDirectory() as d:
        base = 1_000_000
        # reactive: replicas climb late (reacting); predictive: climb early.
        pd.DataFrame({"timestamp": [base + 2 * i for i in range(20)],
                      "replicas": [1] * 10 + [1, 2, 3, 4, 5, 5, 5, 5, 4, 3]}
                     ).to_csv(os.path.join(d, "reactive_replicas.csv"), index=False)
        pd.DataFrame({"timestamp": [base + 2 * i for i in range(20)],
                      "replicas": [1, 2, 4, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 4, 3, 2, 1, 1, 1, 1]}
                     ).to_csv(os.path.join(d, "predictive_replicas.csv"), index=False)
        with open(os.path.join(d, "reactive_load.json"), "w") as f:
            json.dump({"p95_ms": 420.0, "p99_ms": 980.0, "error_rate": 0.031,
                       "failed_requests": 57, "total_requests": 1840}, f)
        with open(os.path.join(d, "predictive_load.json"), "w") as f:
            json.dump({"p95_ms": 180.0, "p99_ms": 240.0, "error_rate": 0.0,
                       "failed_requests": 0, "total_requests": 1860}, f)
        png, loads = run(d)
        assert os.path.getsize(png) > 0, "chart not written"
        md = open(os.path.join(d, "compare.md")).read()
        assert "predictive" in md and "p99 latency" in md, md
        assert loads["predictive"]["failed"] == 0
    print("selfcheck OK (dummy data; real chart needs cluster captures)")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--benchdir", default=HERE)
    ap.add_argument("--reactive", default="reactive")
    ap.add_argument("--predictive", default="predictive")
    ap.add_argument("--selfcheck", action="store_true")
    args = ap.parse_args()
    if args.selfcheck:
        return selfcheck()
    for label in (args.reactive, args.predictive):
        if not os.path.exists(os.path.join(args.benchdir, f"{label}_replicas.csv")):
            sys.exit(f"missing {label}_replicas.csv in {args.benchdir} — run loadtest/capture.sh first")
    png, _ = run(args.benchdir, args.reactive, args.predictive)
    print(f"wrote {png} and compare.md")


if __name__ == "__main__":
    main()
