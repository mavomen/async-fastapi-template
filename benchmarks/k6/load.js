// k6 load test — ramp 10→50 VUs over 5 minutes
// Run: docker run --rm -i grafana/k6 run - < benchmarks/k6/load.js
// Or:  k6 run benchmarks/k6/load.js

import http from "k6/http";
import { check, sleep } from "k6";

const BASE_URL = __ENV.BASE_URL || "http://localhost:8000";

export const options = {
  stages: [
    { duration: "30s", target: 10 },   // ramp up
    { duration: "2m", target: 30 },    // steady state
    { duration: "30s", target: 50 },   // peak
    { duration: "1m", target: 50 },    // sustain peak
    { duration: "30s", target: 0 },    // ramp down
  ],
  thresholds: {
    http_req_duration: ["p(95)<500"],
    http_req_failed: ["rate<0.01"],
  },
};

export default function () {
  // Health check
  let res = http.get(`${BASE_URL}/health`);
  check(res, {
    "health status 200": (r) => r.status === 200,
  });

  // Register a user
  const uid = Date.now().toString(36) + Math.random().toString(36).slice(2, 8);
  res = http.post(
    `${BASE_URL}/api/v1/auth/register`,
    JSON.stringify({
      email: `load-${uid}@test.example.com`,
      username: `load-${uid}`,
      password: "LoadTest1!",
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

  sleep(0.5);
}
