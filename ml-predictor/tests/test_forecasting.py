"""Unit tests for the forecasting layer (model.py + evaluate.py metrics).

Self-running: `python ml-predictor/tests/test_forecasting.py` (also works under
pytest). No framework or fixtures required -- plain asserts.
"""
import math
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
from model import TrafficPredictor
import evaluate as ev


# ---------- metrics ----------

def test_smape_perfect_is_zero():
    assert ev.smape([1, 2, 3], [1, 2, 3]) == 0.0


def test_smape_known_value():
    # one point, forecast 3 vs actual 1 -> 2*|3-1|/(3+1) = 1.0 -> 100%
    assert math.isclose(ev.smape([1.0], [3.0]), 100.0)


def test_smape_symmetric():
    # swapping actual/pred must give the same sMAPE (that's the point of it)
    a, b = [1.0, 2.0, 4.0], [2.0, 2.0, 3.0]
    assert math.isclose(ev.smape(a, b), ev.smape(b, a))


def test_mape_skips_zero_actual():
    # the only non-zero actual (4, predicted 2) -> 50%; the 0 actual is skipped
    assert math.isclose(ev.mape([0.0, 4.0], [1.0, 2.0]), 50.0)


def test_rmse_constant_offset():
    assert ev.rmse([1, 2, 3], [2, 3, 4]) == 1.0


# ---------- TrafficPredictor ----------

def test_forecast_short_series_falls_back_to_naive():
    mean, lo, hi = TrafficPredictor().forecast([0.3, 0.4])  # <4 points
    assert mean == lo == hi == 0.4


def test_forecast_empty_series():
    assert TrafficPredictor().forecast([]) == (0.0, 0.0, 0.0)


def test_forecast_non_negative_and_ordered_interval():
    series = [0.02, 0.03, 0.05, 0.04, 0.06, 0.08, 0.07, 0.09, 0.1, 0.12]
    mean, lo, hi = TrafficPredictor().forecast(series, h=1, alpha=0.1)
    assert mean >= 0.0 and lo >= 0.0            # CPU can't be negative
    assert hi >= lo                             # interval is ordered
    assert math.isfinite(mean) and math.isfinite(hi)


def test_predict_next_step_matches_forecast_mean():
    series = [0.02, 0.03, 0.05, 0.04, 0.06, 0.08, 0.07, 0.09]
    p = TrafficPredictor()
    assert p.predict_next_step(series) == p.forecast(series)[0]


# ---------- end-to-end walk-forward ----------

def test_walk_forward_lengths():
    series = list(range(50))
    actuals, preds = ev.walk_forward([float(x) for x in series], season=10, initial=20)
    assert len(actuals) == 30
    assert all(len(p) == 30 for p in preds.values())


def test_arima_beats_naive_on_structured_series():
    series = ev.generate_synthetic()
    results, n = ev.evaluate(series, season=40, initial=30)
    assert n > 0
    assert results["arima"]["sMAPE"] <= results["naive"]["sMAPE"]


def _run():
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    for fn in fns:
        fn()
        print(f"ok   {fn.__name__}")
    print(f"\n{len(fns)} passed")


if __name__ == "__main__":
    _run()
