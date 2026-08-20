// k6 smoke test — single VU, 30 seconds
// Run: docker run --rm -i grafana/k6 run - < benchmarks/k6/smoke.js
// Or:  k6 run benchmarks/k6/smoke.js

import http from "k6/http";
import { check, sleep } from "k6";

const BASE_URL = __ENV.BASE_URL || "http://localhost:8000";

export const options = {
  vus: 1,
  duration: "30s",
  thresholds: {
    http_req_duration: ["p(95)<500"],
    http_req_failed: ["rate<0.01"],
  },
};

export default function () {
  // Health check (read-only, no auth)
  let res = http.get(`${BASE_URL}/health`);
  check(res, {
    "health status 200": (r) => r.status === 200,
    "health response time < 200ms": (r) => r.timings.duration < 200,
  });

  // Liveness
  res = http.get(`${BASE_URL}/health/live`);
  check(res, {
    "liveness status 200": (r) => r.status === 200,
  });

  // Readiness
  res = http.get(`${BASE_URL}/health/ready`);
  check(res, {
    "readiness status 200": (r) => r.status === 200,
  });

  // Register a user
  const uid = Date.now().toString(36) + Math.random().toString(36).slice(2, 8);
  res = http.post(
    `${BASE_URL}/api/v1/auth/register`,
    JSON.stringify({
      email: `smoke-${uid}@test.example.com`,
      username: `smoke-${uid}`,
      password: "SmokeTest1!",
    }),
    { headers: { "Content-Type": "application/json" } }
  );
  check(res, {
    "register status 201 or 409": (r) => r.status === 201 || r.status === 409,
  });

  // List users (unauthenticated — expects 401)
  res = http.get(`${BASE_URL}/api/v1/users/`);
  check(res, {
    "users list returns 401": (r) => r.status === 401,
  });

  sleep(1);
}
