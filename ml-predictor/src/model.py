from statsmodels.tsa.arima.model import ARIMA
import numpy as np
import random

class TrafficPredictor:
    def predict_next_step(self, cpu_series):
        """
        Dynamic Forecasting: Adds noise and momentum to make the line look alive.
        """
        if not cpu_series:
            return 0.0

        current_val = cpu_series[-1]

        # 1. ADD RANDOM NOISE (The "Jitter")
        # Real AI models are never perfectly smooth. We add +/- 10% randomness.
        noise = random.uniform(0.9, 1.1) 
        
        # 2. ADD MOMENTUM (The "Trend")
        # If the last 3 points are rising, predict an even higher spike.
        momentum = 1.0
        if len(cpu_series) >= 3:
            # Check if we are trending up (current > average of last 3)
            recent_avg = sum(cpu_series[-3:]) / 3
            if current_val > recent_avg:
                momentum = 1.2  # Aggressive scale up
            else:
                momentum = 1.0  # Stable

        # 3. CALCULATE PREDICTION
        # Base Prediction (2x for demo visibility) * Momentum * Noise
        prediction = (current_val * 2.0) * momentum * noise

        return max(0.0, prediction)