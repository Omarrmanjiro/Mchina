"""
Locust Performance Test Suite for GET /public-searches
=======================================================

Tests a FastAPI endpoint that uses stale-while-revalidate Redis caching.

Prerequisites:
    pip install locust

Environment:
    export TOKEN="your-jwt-token-here"          # Linux/macOS
    $env:TOKEN = "your-jwt-token-here"          # PowerShell

Usage:
    # Baseline – no Redis running, measure raw endpoint latency
    locust -f locustfile.py --tags baseline --host=http://localhost:8000

    # Cold cache – Redis running but empty, measure first-fill behaviour
    locust -f locustfile.py --tags cold_cache --host=http://localhost:8000

    # Warm cache – Redis pre-populated, measure cache-hit latency
    locust -f locustfile.py --tags warm_cache --host=http://localhost:8000

    # Stampede – 100 concurrent users after cache expires
    locust -f locustfile.py --tags stampede --host=http://localhost:8000 -u 100 -r 100

    # Resilience – Redis is intentionally stopped, endpoint should degrade gracefully
    locust -f locustfile.py --tags resilience --host=http://localhost:8000

    # Headless quick-run example (30s, 20 users, spawn 5/s)
    locust -f locustfile.py --tags warm_cache --host=http://localhost:8000 \
        --headless -u 20 -r 5 -t 30s
"""

from __future__ import annotations

import logging
import os
import random
import time
from typing import ClassVar

from locust import HttpUser, between, constant, events, tag, task
from locust.runners import MasterRunner, WorkerRunner

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

WINDOWS: list[str] = ["1h", "6h", "1d"]
TOKEN: str = os.environ.get("TOKEN", "")

if not TOKEN:
    logging.warning(
        "TOKEN environment variable is not set. "
        "All requests will be sent without Authorization and will likely 401."
    )

# Shared request counters (updated via the request event hook).
_stats: dict[str, float | int] = {
    "total_requests": 0,
    "total_failures": 0,
    "total_response_time_ms": 0.0,
    "cache_hits": 0,
    "cache_misses": 0,
    "cache_stale": 0,
    "cache_unknown": 0,
}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

logger = logging.getLogger("perf")


def _auth_headers() -> dict[str, str]:
    """Return the Authorization header dict."""
    if TOKEN:
        return {"Authorization": f"Bearer {TOKEN}"}
    return {}


def _random_window() -> str:
    return random.choice(WINDOWS)


def _classify_cache_state(response) -> str:
    """Infer cache state from response headers or timing.

    The endpoint is expected to set one of:
        X-Cache: HIT | MISS | STALE | BYPASS

    If the header is absent we fall back to a latency heuristic:
        < 15 ms  → probable HIT
        ≥ 15 ms  → probable MISS
    """
    cache_header = (response.headers.get("X-Cache") or "").upper().strip()
    if cache_header in {"HIT", "MISS", "STALE", "BYPASS"}:
        return cache_header

    # Fallback: use response time (locust stores it in ms on the meta).
    elapsed_ms = response.elapsed.total_seconds() * 1000
    if elapsed_ms < 15:
        return "HIT"
    return "MISS"


# ---------------------------------------------------------------------------
# Event hooks – collect per-request telemetry
# ---------------------------------------------------------------------------

@events.request.add_listener
def _on_request(request_type, name, response_time, response_length, exception, **kwargs):
    """Accumulate lightweight counters for the final summary."""
    _stats["total_requests"] += 1
    if exception is not None:
        _stats["total_failures"] += 1
    _stats["total_response_time_ms"] += response_time or 0.0


@events.test_stop.add_listener
def _on_test_stop(environment, **kwargs):
    """Print a human-readable summary when the test ends."""
    total = int(_stats["total_requests"])
    failures = int(_stats["total_failures"])
    total_time = _stats["total_response_time_ms"]
    avg_ms = total_time / total if total else 0.0
    failure_pct = (failures / total * 100) if total else 0.0

    hits = int(_stats["cache_hits"])
    misses = int(_stats["cache_misses"])
    stale = int(_stats["cache_stale"])
    unknown = int(_stats["cache_unknown"])

    border = "=" * 62
    print(f"\n{border}")
    print("  PERFORMANCE TEST SUMMARY")
    print(border)
    print(f"  Total requests ........... {total:>10,}")
    print(f"  Failures ................. {failures:>10,}")
    print(f"  Failure rate ............. {failure_pct:>9.2f}%")
    print(f"  Avg response time ........ {avg_ms:>9.2f} ms")
    print(f"  Total response time ...... {total_time:>9.0f} ms")
    print(border)
    print("  Cache Classification (from headers / heuristic)")
    print(f"    HIT .................... {hits:>10,}")
    print(f"    MISS ................... {misses:>10,}")
    print(f"    STALE .................. {stale:>10,}")
    print(f"    UNKNOWN ................ {unknown:>10,}")
    print(f"{border}\n")


# ---------------------------------------------------------------------------
# Base mixin – shared request logic
# ---------------------------------------------------------------------------

class _PublicSearchMixin:
    """Reusable request logic shared by every user class."""

    # Subclasses can override to tolerate higher failure rates.
    _failure_tolerance: ClassVar[float] = 0.0  # 0 = any non-2xx is a failure

    def _fetch_public_searches(self, label: str | None = None) -> None:
        window = _random_window()
        url = f"/public-searches?window={window}"
        request_name = label or f"/public-searches?window={window}"

        with self.client.get(
            url,
            headers=_auth_headers(),
            name=request_name,
            catch_response=True,
        ) as response:
            # ---------- classify cache state ----------
            cache_state = "UNKNOWN"
            if response.status_code and 200 <= response.status_code < 300:
                cache_state = _classify_cache_state(response)

            state_key = {
                "HIT": "cache_hits",
                "MISS": "cache_misses",
                "STALE": "cache_stale",
            }.get(cache_state, "cache_unknown")
            _stats[state_key] += 1

            # ---------- log ----------
            elapsed = response.elapsed.total_seconds() * 1000 if response.elapsed else 0
            logger.debug(
                "window=%s  status=%s  time=%.1fms  cache=%s",
                window,
                response.status_code,
                elapsed,
                cache_state,
            )

            # ---------- pass / fail ----------
            if response.status_code is None:
                response.failure("No response received")
            elif response.status_code == 401:
                response.failure("401 Unauthorized – check TOKEN env var")
            elif response.status_code == 503:
                # Resilience scenario: service may intentionally return 503
                if self._failure_tolerance > 0:
                    response.success()
                else:
                    response.failure(f"503 Service Unavailable")
            elif response.status_code >= 400:
                response.failure(f"HTTP {response.status_code}")
            else:
                response.success()


# ---------------------------------------------------------------------------
# 1. BaselineUser – no Redis, raw endpoint performance
# ---------------------------------------------------------------------------

class BaselineUser(_PublicSearchMixin, HttpUser):
    """Measure raw endpoint latency without any Redis layer.

    Run with Redis stopped so every request hits the database directly.
    """

    wait_time = between(0.5, 1.5)
    weight = 1

    @tag("baseline")
    @task
    def get_public_searches(self) -> None:
        self._fetch_public_searches(label="/public-searches [baseline]")


# ---------------------------------------------------------------------------
# 2. ColdCacheUser – Redis running but empty
# ---------------------------------------------------------------------------

class ColdCacheUser(_PublicSearchMixin, HttpUser):
    """Simulate a burst of traffic against an empty cache.

    Aggressive wait_time to expose thundering-herd on first fill.
    """

    wait_time = between(0.05, 0.1)
    weight = 1

    @tag("cold_cache")
    @task
    def get_public_searches(self) -> None:
        self._fetch_public_searches(label="/public-searches [cold_cache]")


# ---------------------------------------------------------------------------
# 3. WarmCacheUser – Redis pre-populated
# ---------------------------------------------------------------------------

class WarmCacheUser(_PublicSearchMixin, HttpUser):
    """Steady-state traffic against a fully populated cache.

    Expect near-instant responses served from Redis.
    """

    wait_time = between(0.1, 0.5)
    weight = 1

    @tag("warm_cache")
    @task
    def get_public_searches(self) -> None:
        self._fetch_public_searches(label="/public-searches [warm_cache]")


# ---------------------------------------------------------------------------
# 4. StampedeUser – cache just expired, 100 users at once
# ---------------------------------------------------------------------------

class StampedeUser(_PublicSearchMixin, HttpUser):
    """Thundering-herd / stampede test.

    Launch with  -u 100 -r 100  so all 100 users fire simultaneously
    right after the cache TTL expires.
    """

    wait_time = between(0, 0.05)
    weight = 1

    @tag("stampede")
    @task
    def get_public_searches(self) -> None:
        self._fetch_public_searches(label="/public-searches [stampede]")


# ---------------------------------------------------------------------------
# 5. ResilienceUser – Redis is down
# ---------------------------------------------------------------------------

class ResilienceUser(_PublicSearchMixin, HttpUser):
    """Verify the endpoint degrades gracefully when Redis is unavailable.

    503 responses are tolerated and counted as successes so we can
    measure whether the endpoint falls back or errors out.
    """

    wait_time = between(0.5, 1.0)
    weight = 1
    _failure_tolerance: ClassVar[float] = 1.0  # tolerate 503s

    @tag("resilience")
    @task
    def get_public_searches(self) -> None:
        self._fetch_public_searches(label="/public-searches [resilience]")
