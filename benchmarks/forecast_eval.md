# Forecast Evaluation

- Source: `prometheus` (prometheus)
- Series length: 58 points; held-out one-step forecasts: 28
- Walk-forward initial window: 30; seasonal-naive period: 40

| Method | sMAPE (%) | MAPE (%) | RMSE |
|---|---|---|---|
| arima | 20.719 | 38.398 | 0.004306 |
| naive | 26.099 | 54.296 | 0.00525 |
| seasonal_naive | 75.398 | 67.722 | 0.013291 |

Lowest sMAPE: **arima** (20.719%).
