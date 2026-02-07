from flask import Flask, jsonify
from flask_cors import CORS
from prometheus import PrometheusClient
from model import TrafficPredictor
import traceback

app = Flask(__name__)
CORS(app)

# Ensure this port matches your tunnel (9090 or 9091)
prom_client = PrometheusClient()
predictor = TrafficPredictor()

@app.route('/predict', methods=['GET'])
def predict():
    try:
        # 1. Fetch Data
        print("Fetching data from Prometheus...")
        df = prom_client.fetch_cpu_history(app_label="victim")

        # 2. Handle Empty Data (The "New App" Scenario)
        if df.empty:
            print("Warning: Prometheus returned no data.")
            return jsonify({
                "status": "warning",
                "message": "No data found. The victim app is running, but Prometheus hasn't scraped it yet. Wait 2 minutes."
            }), 200

        # 3. Predict
        cpu_values = df['cpu_usage'].tolist()
        print(f"Analyzing {len(cpu_values)} data points...")

        forecast_value = predictor.predict_next_step(cpu_values)
        current_value = cpu_values[-1]

        # 4. Action Logic
        action = "maintain"
        if current_value > 0.05:
            action = "scale_up"

        return jsonify({
            "current_cpu": current_value,
            "predicted_cpu": forecast_value,
            "action": action
        })

    except Exception as e:
        print("CRITICAL ERROR Occurred:")
        traceback.print_exc() # Prints to Terminal
        return jsonify({
            "error": "Server Error",
            "details": str(e),
            "hint": "Check if your kubectl port-forward tunnel is running!"
        }), 500

if __name__ == '__main__':
    print("Starting ML Predictor on port 8081...")
    app.run(host='0.0.0.0', port=8081)