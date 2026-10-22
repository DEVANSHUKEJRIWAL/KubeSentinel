# Forecast Evaluation

> ⚠️ **SYNTHETIC input series** — these numbers measure the evaluation
> machinery, not production behaviour. Do **not** put them on a résumé.
> Re-run with `--source prometheus` on a real capture for the real number.

- Source: `benchmarks/cpu_series_sample.csv` (synthetic)
- Series length: 120 points; held-out one-step forecasts: 90
- Walk-forward initial window: 30; seasonal-naive period: 40

| Method | sMAPE (%) | MAPE (%) | RMSE |
|---|---|---|---|
| arima | 8.042 | 10.621 | 0.007487 |
| naive | 11.254 | 12.08 | 0.010768 |
| seasonal_naive | 39.614 | 27.661 | 0.043888 |

Lowest sMAPE: **arima** (8.042%).
