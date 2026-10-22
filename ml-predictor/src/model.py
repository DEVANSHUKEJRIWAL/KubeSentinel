from statsmodels.tsa.arima.model import ARIMA
import warnings


class TrafficPredictor:
    """One-step (or h-step) CPU forecaster backed by a real ARIMA model.

    Fits ARIMA on the recent CPU history each call (series is short: ~60 points
    from a 15m:15s Prometheus window, so a per-call fit is cheap). Exposes the
    forecast mean and a prediction interval so callers can scale on the upper
    bound rather than the point estimate.
    """

    # ponytail: fixed order, not auto-selected. A short high-frequency CPU
    # series does not justify pulling in pmdarima/auto_arima. If forecast
    # quality on real data is poor, make `order` configurable or add seasonal
    # terms here.
    def __init__(self, order=(2, 1, 1)):
        self.order = order

    def forecast(self, cpu_series, h=1, alpha=0.1):
        """Return (mean, lower, upper) for the h-step-ahead forecast.

        `alpha=0.1` gives a 90% prediction interval. Falls back to last-value
        (naive) if there is too little data or ARIMA fails to fit — the caller
        always gets a usable number.
        """
        series = [float(x) for x in cpu_series]
        if len(series) < 4:
            last = series[-1] if series else 0.0
            return last, last, last

        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")  # convergence / freq warnings on short series
                fit = ARIMA(series, order=self.order).fit()
                fc = fit.get_forecast(steps=h)
                mean = float(fc.predicted_mean[-1])
                ci = fc.conf_int(alpha=alpha)
                lower = float(ci[-1][0])
                upper = float(ci[-1][1])
        except Exception:
            # ponytail: naive fallback keeps the control plane alive when ARIMA
            # can't fit (flat/degenerate window). Upgrade path: log the failure
            # and export it as a metric so flapping to naive is visible.
            last = series[-1]
            return last, last, last

        # CPU usage can't be negative.
        mean = max(0.0, mean)
        return mean, max(0.0, lower), max(0.0, upper)

    def predict_next_step(self, cpu_series):
        """Backward-compatible one-step point forecast (mean only)."""
        mean, _, _ = self.forecast(cpu_series, h=1)
        return mean
