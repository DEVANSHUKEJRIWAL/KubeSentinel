import http from 'k6/http';
import { check, sleep } from 'k6';

// Identical, repeatable spike profile shared by both modes (reactive vs
// predictive). Keep these stages fixed so the two runs are comparable.
export const options = {
  stages: [
    { duration: '30s', target: 10 }, // warm-up
    { duration: '30s', target: 80 }, // spike ramp
    { duration: '60s', target: 80 }, // sustained peak
    { duration: '30s', target: 0 },  // ramp down
  ],
  thresholds: {
    http_req_failed: ['rate<0.01'],                 // goal: ~zero failed requests
    http_req_duration: ['p(95)<500', 'p(99)<1000'], // ms
  },
};

const TARGET = __ENV.TARGET || 'http://localhost:8080';

export default function () {
  const res = http.get(TARGET);
  check(res, { 'status 200': (r) => r.status === 200 });
  sleep(0.5); // ~2 req/s per VU (matches the Locust pacing)
}

// Export p95/p99 + error rate to JSON so capture.sh / compare.py can read it.
export function handleSummary(data) {
  const d = data.metrics.http_req_duration.values;
  const f = data.metrics.http_req_failed.values;
  const out = {
    p95_ms: d['p(95)'],
    p99_ms: d['p(99)'],
    error_rate: f.rate,
    failed_requests: f.fails,
    total_requests: data.metrics.http_reqs.values.count,
  };
  const path = __ENV.K6_SUMMARY_OUT || 'benchmarks/k6_summary.json';
  return {
    [path]: JSON.stringify(out, null, 2),
    stdout: `\np95=${out.p95_ms?.toFixed(1)}ms p99=${out.p99_ms?.toFixed(1)}ms ` +
            `errors=${(out.error_rate * 100).toFixed(2)}% failed=${out.failed_requests}/${out.total_requests}\n`,
  };
}
