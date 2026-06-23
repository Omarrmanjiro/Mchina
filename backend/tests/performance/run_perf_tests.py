# =============================================================================
# run_perf_tests.py  -  Mchina Redis Performance Test Suite
#
# HOW TO USE:
#   Run ONE phase at a time using the --phase flag:
#
#   python tests/performance/run_perf_tests.py --token "YOUR_JWT" --phase baseline
#   python tests/performance/run_perf_tests.py --token "YOUR_JWT" --phase cold
#   python tests/performance/run_perf_tests.py --token "YOUR_JWT" --phase warm
#   python tests/performance/run_perf_tests.py --token "YOUR_JWT" --phase stale
#   python tests/performance/run_perf_tests.py --token "YOUR_JWT" --phase stampede
#   python tests/performance/run_perf_tests.py --token "YOUR_JWT" --phase redisdown
#   python tests/performance/run_perf_tests.py --token "YOUR_JWT" --phase report
#
# Results accumulate in perf_results.json across runs. Run 'report' last to see
# the full comparison table.
# =============================================================================

import argparse
import concurrent.futures
import json
import os
import statistics
import time

import psycopg2
import redis
import requests

RESULTS_FILE = "perf_results.json"

# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def compute_percentile(latencies, p):
    if not latencies:
        return 0
    n = len(latencies)
    if n >= 100:
        return statistics.quantiles(latencies, n=100)[p - 1]
    return sorted(latencies)[int(n * p / 100)]


def fire_requests(url, headers, count, spread_seconds=0):
    latencies = []
    errors = 0
    session = requests.Session()
    def make_request():
        nonlocal errors
        start = time.time()
        try:
            resp = session.get(url, headers=headers, timeout=15)
            if resp.status_code == 200:
                latencies.append((time.time() - start) * 1000)
            else:
                errors += 1
                print(f"  [HTTP {resp.status_code}] {resp.text[:100]}")
        except Exception as exc:
            errors += 1
            print(f"  [ERR] {exc}")

    start_time = time.time()
    with concurrent.futures.ThreadPoolExecutor(max_workers=min(count, 200)) as executor:
        futures = []
        for i in range(count):
            if spread_seconds:
                time.sleep(spread_seconds / count)
            futures.append(executor.submit(make_request))
        concurrent.futures.wait(futures)

    duration = time.time() - start_time
    rps = count / duration if duration > 0 else 0
    return latencies, errors, rps, duration


def build_result(latencies, errors, rps, total):
    return {
        "Avg Latency ms": round(sum(latencies) / len(latencies), 2) if latencies else 0,
        "p50 ms":  round(compute_percentile(latencies, 50), 2),
        "p95 ms":  round(compute_percentile(latencies, 95), 2),
        "p99 ms":  round(compute_percentile(latencies, 99), 2),
        "RPS":     round(rps, 2),
        "Errors":  errors,
        "Total":   total,
        "Error Rate": f"{(errors / total) * 100:.1f}%",
    }


def load_results():
    if os.path.exists(RESULTS_FILE):
        with open(RESULTS_FILE) as f:
            return json.load(f)
    return {}


def save_results(results):
    with open(RESULTS_FILE, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\n  Results saved to {RESULTS_FILE}")


def get_redis_stats(redis_url):
    try:
        r = redis.Redis.from_url(redis_url, decode_responses=True)
        info = r.info("stats")
        return info.get("keyspace_hits", 0), info.get("keyspace_misses", 0)
    except Exception:
        return 0, 0


def get_pg_active_queries(db_url):
    try:
        conn = psycopg2.connect(db_url, connect_timeout=5)
        cur = conn.cursor()
        cur.execute(
            "SELECT count(*) FROM pg_stat_activity "
            "WHERE state = 'active' AND query ILIKE '%searches%' AND pid <> pg_backend_pid();"
        )
        count = cur.fetchone()[0]
        cur.close()
        conn.close()
        return count
    except Exception:
        return -1


def print_separator(title):
    print("\n" + "=" * 65)
    print(f"  {title}")
    print("=" * 65)


def print_report(results):
    print("\n" + "=" * 90)
    print(f"  FINAL COMPARISON TABLE")
    print("=" * 90)
    phases  = ["Baseline", "Cold Cache", "Warm Cache", "Stale Cache", "Stampede", "Redis Down"]
    metrics = ["Avg Latency ms", "p50 ms", "p95 ms", "p99 ms", "RPS", "Error Rate"]
    header  = f"{'Metric':<18}"
    for p in phases:
        header += f" | {p:<12}"
    print(header)
    print("-" * 90)
    for metric in metrics:
        row = f"{metric:<18}"
        for phase in phases:
            val = results.get(phase, {}).get(metric, "N/A")
            if isinstance(val, float):
                val = f"{val:.1f}"
            row += f" | {str(val):<12}"
        print(row)
    print("=" * 90 + "\n")


# ─────────────────────────────────────────────────────────────────────────────
# Phase Runners
# ─────────────────────────────────────────────────────────────────────────────

def phase_baseline(args):
    """
    PHASE 1 - BASELINE
    Redis is BYPASSED in main.py. This measures raw DB performance.
    Run AFTER adding the bypass line to main.py (see manual guide).
    """
    print_separator("PHASE 1 - BASELINE (Raw DB, no Redis)")
    print("  Sending requests. This WILL be slow and may have timeouts.")
    print(f"  Firing {args.concurrent} requests...\n")

    latencies, errors, rps, duration = fire_requests(
        f"{args.base_url}/public-searches?window=1h",
        {"Authorization": f"Bearer {args.token}"},
        args.concurrent,
        spread_seconds=0,
    )
    result = build_result(latencies, errors, rps, args.concurrent)
    print(f"\n  Done. Avg: {result['Avg Latency ms']} ms | RPS: {result['RPS']} | Errors: {result['Error Rate']}")

    results = load_results()
    results["Baseline"] = result
    save_results(results)


def phase_cold(args):
    """
    PHASE 2 - COLD CACHE
    Redis is enabled but empty. Measures the first-hit cache miss penalty.
    """
    print_separator("PHASE 2 - COLD CACHE (Redis empty)")

    r = redis.Redis.from_url(args.redis_url)
    r.flushall()
    print("  Redis flushed - cache is now empty.")

    url     = f"{args.base_url}/public-searches?window=1h"
    headers = {"Authorization": f"Bearer {args.token}"}

    hits_before, misses_before = get_redis_stats(args.redis_url)
    latencies, errors, rps, _ = fire_requests(url, headers, args.concurrent, spread_seconds=0)
    hits_after, misses_after   = get_redis_stats(args.redis_url)

    result = build_result(latencies, errors, rps, args.concurrent)
    result["Cache Hits"]   = hits_after   - hits_before
    result["Cache Misses"] = misses_after - misses_before
    print(f"\n  Cache hits: {result['Cache Hits']}  |  misses: {result['Cache Misses']}")
    print(f"  Avg: {result['Avg Latency ms']} ms | RPS: {result['RPS']} | Errors: {result['Error Rate']}")

    results = load_results()
    results["Cold Cache"] = result
    save_results(results)


def phase_warm(args):
    """
    PHASE 3 - WARM CACHE
    Redis is populated. This should show the best latency and highest RPS.
    """
    print_separator("PHASE 3 - WARM CACHE (Redis populated)")

    url     = f"{args.base_url}/public-searches?window=1h"
    headers = {"Authorization": f"Bearer {args.token}"}
    total   = args.concurrent * args.duration

    print("  Priming cache with a single request first...")
    try:
        requests.get(url, headers=headers, timeout=20)
        print("  Cache primed! Waiting 2s for it to settle...")
        time.sleep(2)
    except Exception as e:
        print(f"  [!] Priming failed: {e}. Waiting 5s and continuing anyway...")
        time.sleep(5)

    print(f"\n  Firing {total} requests spread over {args.duration}s...\n")
    latencies, errors, rps, _ = fire_requests(url, headers, total, spread_seconds=args.duration)

    result = build_result(latencies, errors, rps, total)
    print(f"\n  Avg: {result['Avg Latency ms']} ms | RPS: {result['RPS']} | Errors: {result['Error Rate']}")

    results = load_results()
    results["Warm Cache"] = result
    save_results(results)


def phase_stale(args):
    """
    PHASE 4 - STALE CACHE (SWR Validation)
    Waits for the 60s logical TTL to expire, then blasts the endpoint.
    All users should get a fast response (stale data), while exactly 1
    background DB refresh fires.
    """
    print_separator("PHASE 4 - STALE CACHE / SWR Validation")
    print("  Waiting 65 seconds for the logical TTL to expire...")

    for i in range(65, 0, -5):
        print(f"  {i}s remaining...", end="\r")
        time.sleep(5)
    print("  TTL expired! Blasting 50 concurrent requests now...     ")

    url     = f"{args.base_url}/public-searches?window=1h"
    headers = {"Authorization": f"Bearer {args.token}"}

    latencies, errors, rps, _ = fire_requests(url, headers, args.concurrent, spread_seconds=0)
    db_queries = get_pg_active_queries(args.db_url)

    result = build_result(latencies, errors, rps, args.concurrent)
    print(f"\n  Avg: {result['Avg Latency ms']} ms | RPS: {result['RPS']} | Errors: {result['Error Rate']}")
    print(f"  Active DB queries at peak: {db_queries} (expected <= 1)")
    result["Active DB Queries"] = db_queries

    results = load_results()
    results["Stale Cache"] = result
    save_results(results)


def phase_stampede(args):
    """
    PHASE 5 - STAMPEDE PREVENTION
    Flushes Redis then fires 100 concurrent requests at once.
    The Redis lock should ensure only 1 DB query fires.
    """
    print_separator("PHASE 5 - STAMPEDE PREVENTION")

    r = redis.Redis.from_url(args.redis_url)
    r.flushall()
    print("  Redis flushed. Firing 100 concurrent requests instantly...")
    time.sleep(1)

    url     = f"{args.base_url}/public-searches?window=1h"
    headers = {"Authorization": f"Bearer {args.token}"}

    latencies, errors, rps, _ = fire_requests(url, headers, 100, spread_seconds=0)
    db_queries = get_pg_active_queries(args.db_url)

    print(f"\n  Active DB queries during stampede: {db_queries} (expected <= 1)")
    result = build_result(latencies, errors, rps, 100)
    result["Active DB Queries"] = db_queries
    result["Expected"] = "<= 1"
    result["Passed"] = db_queries <= 1

    results = load_results()
    results["Stampede"] = result
    save_results(results)


def phase_redisdown(args):
    """
    PHASE 6 - REDIS DOWN (Graceful Fallback)
    Redis must be STOPPED before running this phase.
    The endpoint should fall back to DB queries and return 0% errors.
    """
    print_separator("PHASE 6 - REDIS DOWN (Graceful Fallback)")
    print("  NOTE: This phase expects Redis to be ALREADY stopped.")
    print("  Sending requests to verify graceful DB fallback...\n")

    url     = f"{args.base_url}/public-searches?window=1h"
    headers = {"Authorization": f"Bearer {args.token}"}
    total   = args.concurrent

    latencies, errors, rps, _ = fire_requests(url, headers, total, spread_seconds=0)
    result = build_result(latencies, errors, rps, total)

    print(f"\n  Avg: {result['Avg Latency ms']} ms | RPS: {result['RPS']} | Errors: {result['Error Rate']}")
    if errors == 0:
        print("  PASS - Graceful fallback working! 0 errors with Redis down.")
    else:
        print("  FAIL - Errors detected. Check server logs for details.")

    results = load_results()
    results["Redis Down"] = result
    save_results(results)


def phase_report(args):
    """Print the full comparison table from saved results."""
    print_separator("RESULTS REPORT")
    results = load_results()
    if not results:
        print("  No results found. Run some phases first!")
        return
    print_report(results)


# ─────────────────────────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────────────────────────

PHASES = {
    "baseline":  phase_baseline,
    "cold":      phase_cold,
    "warm":      phase_warm,
    "stale":     phase_stale,
    "stampede":  phase_stampede,
    "redisdown": phase_redisdown,
    "report":    phase_report,
}

def main():
    parser = argparse.ArgumentParser(
        description="Mchina Redis Performance Test Suite - Run one phase at a time",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
PHASES:
  baseline   Phase 1 - Measure raw DB performance (requires Redis bypassed in main.py)
  cold       Phase 2 - Cold cache (Redis empty)
  warm       Phase 3 - Warm cache (Redis populated, best latency expected)
  stale      Phase 4 - Stale cache / SWR validation (waits 65s for TTL to expire)
  stampede   Phase 5 - Stampede prevention (flush + 100 concurrent requests)
  redisdown  Phase 6 - Graceful fallback when Redis is down (stop Redis first!)
  report     Print the full comparison table from accumulated results

EXAMPLE:
  python tests/performance/run_perf_tests.py --token "YOUR_JWT" --phase warm
        """
    )
    parser.add_argument("--token",       required=True,  help="JWT Bearer token (Pro user)")
    parser.add_argument("--phase",       required=True,  choices=PHASES.keys(),
                        help="Which phase to run")
    parser.add_argument("--base-url",    default="http://127.0.0.1:8000")
    parser.add_argument("--redis-url",   default="redis://127.0.0.1:6379/0")
    parser.add_argument("--db-url",      default="postgresql://postgres:Omarr.2002@127.0.0.1:5432/mchina_db")
    parser.add_argument("--concurrent",  type=int, default=50,  help="Concurrent workers (default: 50)")
    parser.add_argument("--duration",    type=int, default=10,  help="Spread duration in seconds (default: 10)")
    args = parser.parse_args()

    PHASES[args.phase](args)


if __name__ == "__main__":
    main()
