import os
import requests
import pandas as pd
from datetime import datetime

class PrometheusClient:
    def __init__(self, host="localhost", port=9090):
        # DETECT CLUSTER: Use internal DNS if in Kubernetes, else localhost
        if os.getenv("KUBERNETES_SERVICE_HOST"):
            self.base_url = "http://prometheus-server.default.svc.cluster.local:80"
        else:
            self.base_url = f"http://{host}:{port}"

    def get_cpu_metrics(self):
        """Gets the CURRENT CPU usage (for the Dashboard/Agent check)"""
        # Uses the wildcard query we confirmed works: pod=~"victim-app.*"
        query = 'sum(rate(container_cpu_usage_seconds_total{namespace="default", pod=~"victim-app.*"}[1m]))'
        
        try:
            response = requests.get(f"{self.base_url}/api/v1/query", params={'query': query})
            data = response.json()
            if data['status'] == 'success' and len(data['data']['result']) > 0:
                return float(data['data']['result'][0]['value'][1])
        except Exception as e:
            print(f"Error fetching current CPU: {e}")
        return 0.0

    def fetch_cpu_history(self, app_label="victim"):
        """Gets PAST CPU usage (for the AI Model to train on)"""
        # Queries the last 15 minutes of data
        query = 'sum(rate(container_cpu_usage_seconds_total{namespace="default", pod=~"victim-app.*"}[1m]))[15m:15s]'
        
        try:
            response = requests.get(f"{self.base_url}/api/v1/query", params={'query': query})
            data = response.json()
            
            if data['status'] == 'success' and len(data['data']['result']) > 0:
                # Convert Prometheus JSON response to a Pandas DataFrame
                values = data['data']['result'][0]['values']
                df = pd.DataFrame(values, columns=['timestamp', 'cpu_usage'])
                df['cpu_usage'] = df['cpu_usage'].astype(float)
                return df
        except Exception as e:
            print(f"Error fetching history: {e}")
            
        # Return empty DataFrame if something fails (prevents crash)
        return pd.DataFrame()