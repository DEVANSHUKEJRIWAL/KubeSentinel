"""Locust version of the spike in loadtest/k6/spike.js -- same timeline so the
two tools exercise victim-app identically.

Headless run (writes percentile CSVs under benchmarks/):
  locust -f locustfile.py --headless --host http://localhost:8080 \
      --csv benchmarks/reactive_load --only-summary
Percentiles land in benchmarks/reactive_load_stats.csv (50%/95%/99% columns).
"""
from locust import HttpUser, task, constant_pacing, LoadTestShape


class VictimUser(HttpUser):
    wait_time = constant_pacing(0.5)  # ~2 req/s per user, matches k6 sleep(0.5)

    @task
    def hit(self):
        self.client.get("/")


class SpikeShape(LoadTestShape):
    # (end_second, users, spawn_rate) -- mirrors the k6 stages exactly.
    stages = [
        (30, 10, 10),   # warm-up
        (60, 80, 20),   # spike ramp
        (120, 80, 20),  # sustained peak
        (150, 0, 20),   # ramp down
    ]

    def tick(self):
        t = self.get_run_time()
        for end, users, rate in self.stages:
            if t < end:
                return (users, rate)
        return None  # past the last stage -> stop the test
