/**
 * k6 Performance Test Suite
 * ─────────────────────────
 * Endpoint:  GET /public-searches?window={1h|6h|1d}
 * Auth:      Bearer JWT
 * Caching:   Stale-while-revalidate via Redis
 *              • Physical TTL : 24 hours
 *              • Logical TTL  : 1 minute
 *              • Redis lock (SETNX) prevents duplicate background refreshes
 *
 * Environment variables:
 *   TOKEN    – JWT bearer token (required)
 *   BASE_URL – API base URL (default: http://localhost:8000)
 *
 * Usage:
 *   k6 run -e TOKEN=<jwt> k6_test.js                        # run ALL scenarios
 *   k6 run -e TOKEN=<jwt> --scenario baseline k6_test.js    # run a single scenario
 */

import http from "k6/http";
import { check, sleep } from "k6";
import { Trend, Rate, Counter } from "k6/metrics";

// ──────────────────────────────────────────────
//  Custom metrics — one set per scenario
// ──────────────────────────────────────────────
const baselineDuration       = new Trend("baseline_duration", true);
const coldCacheDuration      = new Trend("cold_cache_duration", true);
const warmCacheDuration      = new Trend("warm_cache_duration", true);
const stampedeDuration       = new Trend("stampede_duration", true);
const redisFailureDuration   = new Trend("redis_failure_duration", true);

const baselineErrors         = new Rate("baseline_errors");
const coldCacheErrors        = new Rate("cold_cache_errors");
const warmCacheErrors        = new Rate("warm_cache_errors");
const stampedeErrors         = new Rate("stampede_errors");
const redisFailureErrors     = new Rate("redis_failure_errors");

const baselineRequests       = new Counter("baseline_requests");
const coldCacheRequests      = new Counter("cold_cache_requests");
const warmCacheRequests      = new Counter("warm_cache_requests");
const stampedeRequests       = new Counter("stampede_requests");
const redisFailureRequests   = new Counter("redis_failure_requests");

// ──────────────────────────────────────────────
//  Configuration
// ──────────────────────────────────────────────
const BASE_URL = __ENV.BASE_URL || "http://localhost:8000";
const TOKEN    = __ENV.TOKEN;
const WINDOWS  = ["1h", "6h", "1d"];

const HEADERS = {
  headers: {
    Authorization: `Bearer ${TOKEN}`,
    Accept: "application/json",
  },
  tags: {}, // overridden per-scenario
};

// ──────────────────────────────────────────────
//  k6 options — scenarios & thresholds
// ──────────────────────────────────────────────
export const options = {
  // Scenarios run independently (set startTime offsets so they don't overlap
  // if you run ALL at once — adjust as needed).
  scenarios: {
    // 1. Baseline — no Redis
    baseline: {
      executor: "ramping-vus",
      startVUs: 0,
      stages: [
        { duration: "30s",  target: 50 },   // ramp up
        { duration: "2m",   target: 50 },   // hold
        { duration: "30s",  target: 0 },    // ramp down
      ],
      exec: "scenarioBaseline",
      tags: { scenario_name: "baseline" },
      startTime: "0s",
    },

    // 2. Cold cache — Redis on, cache empty
    cold_cache: {
      executor: "constant-vus",
      vus: 100,
      duration: "30s",
      exec: "scenarioColdCache",
      tags: { scenario_name: "cold_cache" },
      startTime: "3m30s", // starts after baseline finishes
    },

    // 3. Warm cache — populated cache, includes spike
    warm_cache: {
      executor: "ramping-vus",
      startVUs: 0,
      stages: [
        { duration: "30s",  target: 50 },   // ramp up
        { duration: "2m",   target: 50 },   // hold steady
        { duration: "30s",  target: 200 },  // spike
        { duration: "2m",   target: 200 },  // hold spike
        { duration: "30s",  target: 0 },    // ramp down
      ],
      exec: "scenarioWarmCache",
      tags: { scenario_name: "warm_cache" },
      startTime: "4m30s",
    },

    // 4. Stale-cache stampede
    //    Run AFTER the logical TTL (1 min) has elapsed so data is stale.
    //    All 100 VUs hit simultaneously for 10 s.
    stale_cache_stampede: {
      executor: "constant-vus",
      vus: 100,
      duration: "10s",
      exec: "scenarioStampede",
      tags: { scenario_name: "stale_cache_stampede" },
      startTime: "10m30s",
    },

    // 5. Redis failure — Redis is down, fallback to DB
    redis_failure: {
      executor: "constant-vus",
      vus: 50,
      duration: "1m",
      exec: "scenarioRedisFailure",
      tags: { scenario_name: "redis_failure" },
      startTime: "11m",
    },
  },

  thresholds: {
    // ── Baseline (no Redis) ──
    "baseline_duration":     [
      { threshold: "p(95)<500",  abortOnFail: false },
      { threshold: "p(99)<1000", abortOnFail: false },
    ],
    "baseline_errors":       ["rate<0.01"],

    // ── Cold cache ──
    "cold_cache_duration":   [
      { threshold: "p(95)<500",  abortOnFail: false },
    ],
    "cold_cache_errors":     ["rate<0.01"],

    // ── Warm cache ──
    "warm_cache_duration":   [
      { threshold: "p(95)<50",   abortOnFail: false },
      { threshold: "p(99)<100",  abortOnFail: false },
    ],
    "warm_cache_errors":     ["rate<0.01"],

    // ── Stale-cache stampede ──
    "stampede_duration":     [
      { threshold: "p(95)<50",   abortOnFail: false },
    ],
    "stampede_errors":       ["rate<0.01"],

    // ── Redis failure ──
    "redis_failure_duration": [
      { threshold: "p(95)<1000", abortOnFail: false },
    ],
    "redis_failure_errors":  ["rate<0.05"], // allow slightly higher error rate
  },
};

// ──────────────────────────────────────────────
//  setup() — print operator instructions
// ──────────────────────────────────────────────
export function setup() {
  if (!TOKEN) {
    console.error("ERROR: TOKEN environment variable is required. Pass -e TOKEN=<jwt>");
    throw new Error("Missing TOKEN");
  }

  console.log("╔══════════════════════════════════════════════════════════════╗");
  console.log("║          k6 Performance Test Suite — Instructions           ║");
  console.log("╠══════════════════════════════════════════════════════════════╣");
  console.log("║                                                            ║");
  console.log("║  SCENARIO 1 — baseline                                     ║");
  console.log("║    • Disable Redis before this scenario starts.            ║");
  console.log("║    • Measures raw DB-backed latency.                       ║");
  console.log("║    • Ramp: 0→50 VUs (30s), hold 2m, ramp down 30s.        ║");
  console.log("║                                                            ║");
  console.log("║  SCENARIO 2 — cold_cache                                   ║");
  console.log("║    • Enable Redis, flush all keys (FLUSHALL).              ║");
  console.log("║    • 100 VUs burst for 30s — first-request penalty.        ║");
  console.log("║                                                            ║");
  console.log("║  SCENARIO 3 — warm_cache                                   ║");
  console.log("║    • Pre-populate cache (hit the endpoint once first).     ║");
  console.log("║    • Ramp 0→50 (30s), hold 2m, spike to 200 (30s),        ║");
  console.log("║      hold 2m, ramp down 30s.                              ║");
  console.log("║                                                            ║");
  console.log("║  SCENARIO 4 — stale_cache_stampede                         ║");
  console.log("║    • Wait ≥61s after the last cache write so data is       ║");
  console.log("║      logically stale but physically present.               ║");
  console.log("║    • 100 VUs for 10s — stale data must be returned fast.   ║");
  console.log("║    • Only ONE background refresh should occur (SETNX).     ║");
  console.log("║                                                            ║");
  console.log("║  SCENARIO 5 — redis_failure                                ║");
  console.log("║    • Stop Redis entirely before this scenario.             ║");
  console.log("║    • 50 VUs for 1m — expect higher latency (DB fallback). ║");
  console.log("║                                                            ║");
  console.log("╠══════════════════════════════════════════════════════════════╣");
  console.log("║  TIP: Run a single scenario with --scenario <name>         ║");
  console.log("║       e.g.  k6 run --scenario warm_cache -e TOKEN=... ...  ║");
  console.log("╚══════════════════════════════════════════════════════════════╝");

  // Smoke-check: verify the endpoint is reachable
  const smokeRes = http.get(`${BASE_URL}/public-searches?window=1h`, {
    headers: { Authorization: `Bearer ${TOKEN}`, Accept: "application/json" },
    tags: { scenario_name: "setup_smoke" },
  });

  const smokeOk = check(smokeRes, {
    "setup: endpoint reachable (status 200)": (r) => r.status === 200,
  });

  if (!smokeOk) {
    console.warn(`⚠  Smoke check failed — status ${smokeRes.status}. Some scenarios may fail.`);
  } else {
    console.log(`✓  Smoke check passed (${smokeRes.timings.duration.toFixed(1)} ms)`);
  }

  return { baseUrl: BASE_URL };
}

// ──────────────────────────────────────────────
//  Helpers
// ──────────────────────────────────────────────
function randomWindow() {
  return WINDOWS[Math.floor(Math.random() * WINDOWS.length)];
}

function makeRequest(scenarioTag) {
  const window = randomWindow();
  const url = `${BASE_URL}/public-searches?window=${window}`;
  const res = http.get(url, {
    headers: {
      Authorization: `Bearer ${TOKEN}`,
      Accept: "application/json",
    },
    tags: { scenario_name: scenarioTag, window: window },
  });
  return res;
}

function parseBody(res) {
  try {
    return JSON.parse(res.body);
  } catch (_) {
    return null;
  }
}

// ──────────────────────────────────────────────
//  Scenario executors
// ──────────────────────────────────────────────

// 1. Baseline — no Redis
export function scenarioBaseline() {
  const res = makeRequest("baseline");
  const body = parseBody(res);

  baselineDuration.add(res.timings.duration);
  baselineRequests.add(1);

  const passed = check(res, {
    "baseline: status is 200":          (r) => r.status === 200,
    "baseline: response is array":      () => Array.isArray(body),
    "baseline: duration < 500ms (p95)": (r) => r.timings.duration < 500,
  });

  baselineErrors.add(!passed);
  sleep(Math.random() * 0.5 + 0.25); // 250–750 ms think-time
}

// 2. Cold cache — first-request penalty
export function scenarioColdCache() {
  const res = makeRequest("cold_cache");
  const body = parseBody(res);

  coldCacheDuration.add(res.timings.duration);
  coldCacheRequests.add(1);

  const passed = check(res, {
    "cold_cache: status is 200":          (r) => r.status === 200,
    "cold_cache: response is array":      () => Array.isArray(body),
    "cold_cache: duration < 500ms (p95)": (r) => r.timings.duration < 500,
  });

  coldCacheErrors.add(!passed);
  // No sleep — burst test
}

// 3. Warm cache — expect sub-50ms for most requests
export function scenarioWarmCache() {
  const res = makeRequest("warm_cache");
  const body = parseBody(res);

  warmCacheDuration.add(res.timings.duration);
  warmCacheRequests.add(1);

  const passed = check(res, {
    "warm_cache: status is 200":         (r) => r.status === 200,
    "warm_cache: response is array":     () => Array.isArray(body),
    "warm_cache: duration < 50ms (p95)": (r) => r.timings.duration < 50,
  });

  warmCacheErrors.add(!passed);
  sleep(Math.random() * 0.3 + 0.1); // 100–400 ms think-time
}

// 4. Stale-cache stampede — stale data returned instantly
export function scenarioStampede() {
  const res = makeRequest("stale_cache_stampede");
  const body = parseBody(res);

  stampedeDuration.add(res.timings.duration);
  stampedeRequests.add(1);

  const passed = check(res, {
    "stampede: status is 200":         (r) => r.status === 200,
    "stampede: response is array":     () => Array.isArray(body),
    "stampede: duration < 50ms (p95)": (r) => r.timings.duration < 50,
  });

  stampedeErrors.add(!passed);
  // No sleep — all VUs fire as fast as possible to simulate stampede
}

// 5. Redis failure — DB fallback
export function scenarioRedisFailure() {
  const res = makeRequest("redis_failure");
  const body = parseBody(res);

  redisFailureDuration.add(res.timings.duration);
  redisFailureRequests.add(1);

  const passed = check(res, {
    "redis_failure: status is 200":           (r) => r.status === 200,
    "redis_failure: response is array":       () => Array.isArray(body),
    "redis_failure: duration < 1000ms (p95)": (r) => r.timings.duration < 1000,
  });

  redisFailureErrors.add(!passed);
  sleep(Math.random() * 0.5 + 0.25);
}

// ──────────────────────────────────────────────
//  teardown() — summary
// ──────────────────────────────────────────────
export function teardown(data) {
  console.log("────────────────────────────────────────");
  console.log("  Test suite complete.");
  console.log("  Review the threshold results above.");
  console.log("  Key metrics to examine:");
  console.log("    • baseline_duration       – raw DB latency");
  console.log("    • cold_cache_duration     – first-request penalty");
  console.log("    • warm_cache_duration     – cached response speed");
  console.log("    • stampede_duration       – stale-serve stampede protection");
  console.log("    • redis_failure_duration  – fallback resilience");
  console.log("────────────────────────────────────────");
}
