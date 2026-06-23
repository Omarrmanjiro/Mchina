#!/usr/bin/env python3
"""
Live monitoring dashboard for Redis + PostgreSQL during performance tests.

Monitors the /public-searches endpoint's stale-while-revalidate caching layer:
  - Redis cache keys, hit/miss rates, lock states
  - PostgreSQL active connections and search queries
  - Cache stampede risk assessment

Usage:
    python monitor.py
    python monitor.py --interval 1
    python monitor.py --redis-url redis://localhost:6379/0 --db-url postgresql://...
"""

import argparse
import json
import os
import sys
import time

import psycopg2
import redis

# ── ANSI escape codes ────────────────────────────────────────────────────────
RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"

GREEN = "\033[32m"
YELLOW = "\033[33m"
RED = "\033[31m"
CYAN = "\033[36m"
WHITE = "\033[37m"
MAGENTA = "\033[35m"

BG_RED = "\033[41m"
BG_GREEN = "\033[42m"
BG_YELLOW = "\033[43m"

# ── Cache key definitions ────────────────────────────────────────────────────
CACHE_WINDOWS = ["1h", "6h", "1d"]
CACHE_KEY_TEMPLATE = "public_searches:{window}"
LOCK_KEY_TEMPLATE = "lock:refresh_public_searches:{window}"


def clear_screen():
    """Clear terminal screen (cross-platform)."""
    os.system("cls" if os.name == "nt" else "clear")


def colorize(text, color):
    return f"{color}{text}{RESET}"


def status_color(status_text):
    """Return colored status string."""
    upper = status_text.upper()
    if upper in ("CONNECTED", "FRESH", "ACTIVE", "LOW"):
        return colorize(status_text, GREEN + BOLD)
    if upper in ("STALE", "WARNING", "MEDIUM"):
        return colorize(status_text, YELLOW + BOLD)
    if upper in ("DOWN", "MISSING", "INACTIVE", "HIGH", "CRITICAL"):
        return colorize(status_text, RED + BOLD)
    return text


def format_bytes(num_bytes):
    """Human-readable byte size."""
    for unit in ("B", "KB", "MB", "GB"):
        if abs(num_bytes) < 1024:
            return f"{num_bytes:.1f} {unit}"
        num_bytes /= 1024
    return f"{num_bytes:.1f} TB"


def separator(title, width=72):
    """Print a section separator."""
    pad = width - len(title) - 6
    left = pad // 2
    right = pad - left
    return f"\n{BOLD}{CYAN}{'═' * left}  {title}  {'═' * right}{RESET}"


# ── Redis metrics ────────────────────────────────────────────────────────────

def collect_redis_metrics(redis_url):
    """Connect to Redis and collect all relevant metrics."""
    metrics = {
        "status": "DOWN",
        "hits": 0,
        "misses": 0,
        "hit_rate": 0.0,
        "connected_clients": 0,
        "used_memory": 0,
        "cache_keys": [],
        "lock_keys": [],
        "error": None,
    }

    try:
        r = redis.from_url(redis_url, socket_connect_timeout=3, decode_responses=True)
        r.ping()
        metrics["status"] = "CONNECTED"

        # Server info
        info = r.info()
        metrics["hits"] = info.get("keyspace_hits", 0)
        metrics["misses"] = info.get("keyspace_misses", 0)
        total = metrics["hits"] + metrics["misses"]
        metrics["hit_rate"] = (metrics["hits"] / total * 100) if total > 0 else 0.0
        metrics["connected_clients"] = info.get("connected_clients", 0)
        metrics["used_memory"] = info.get("used_memory", 0)

        # Cache keys
        now = time.time()
        for window in CACHE_WINDOWS:
            key = CACHE_KEY_TEMPLATE.format(window=window)
            entry = {"key": key, "ttl": None, "data_age": None, "status": "MISSING"}

            raw = r.get(key)
            if raw is not None:
                ttl = r.ttl(key)  # -1 = no expiry, -2 = key gone
                entry["ttl"] = ttl if ttl >= 0 else None

                # Try to parse timestamp from cached JSON
                try:
                    data = json.loads(raw)
                    cached_at = data.get("cached_at") or data.get("timestamp")
                    if cached_at is not None:
                        entry["data_age"] = int(now - float(cached_at))
                except (json.JSONDecodeError, TypeError, ValueError):
                    pass

                # Determine freshness: if data_age is available, use thresholds;
                # otherwise fall back to TTL ratio heuristic.
                if entry["data_age"] is not None:
                    # Consider data stale if older than 60 seconds
                    entry["status"] = "FRESH" if entry["data_age"] < 60 else "STALE"
                else:
                    entry["status"] = "FRESH" if (ttl and ttl > 0) else "STALE"

            metrics["cache_keys"].append(entry)

        # Lock keys
        for window in CACHE_WINDOWS:
            key = LOCK_KEY_TEMPLATE.format(window=window)
            entry = {"key": key, "ttl": None, "status": "INACTIVE"}

            ttl = r.ttl(key)
            if ttl >= 0:
                entry["ttl"] = ttl
                entry["status"] = "ACTIVE"
            elif ttl == -1:
                # Key exists but has no expiry
                entry["ttl"] = -1
                entry["status"] = "ACTIVE"

            metrics["lock_keys"].append(entry)

        r.close()

    except redis.ConnectionError as exc:
        metrics["error"] = str(exc)
    except redis.RedisError as exc:
        metrics["error"] = str(exc)
    except Exception as exc:  # noqa: BLE001
        metrics["error"] = str(exc)

    return metrics


def render_redis(metrics):
    """Render the Redis section of the dashboard."""
    print(separator("REDIS METRICS"))
    print()

    # Status line
    status = status_color(metrics["status"])
    print(f"  Status:             {status}")

    if metrics["status"] == "DOWN":
        err = metrics.get("error", "unknown")
        print(f"  Error:              {colorize(err, RED)}")
        print()
        return

    print(f"  Keyspace Hits:      {colorize(str(metrics['hits']), GREEN)}")
    print(f"  Keyspace Misses:    {colorize(str(metrics['misses']), YELLOW)}")

    rate = metrics["hit_rate"]
    rate_color = GREEN if rate >= 95 else (YELLOW if rate >= 80 else RED)
    print(f"  Hit Rate:           {colorize(f'{rate:.2f}%', rate_color)}")

    print(f"  Connected Clients:  {metrics['connected_clients']}")
    print(f"  Used Memory:        {format_bytes(metrics['used_memory'])}")

    # Cache keys table
    print()
    print(f"  {BOLD}Cache Keys:{RESET}")
    header = f"  {'Key':<35} {'TTL (s)':<12} {'Data Age (s)':<16} {'Status':<10}"
    print(f"  {DIM}{header.strip()}{RESET}")
    print(f"  {DIM}{'─' * 68}{RESET}")

    for entry in metrics["cache_keys"]:
        ttl_str = str(entry["ttl"]) if entry["ttl"] is not None else "-"
        age_str = str(entry["data_age"]) if entry["data_age"] is not None else "-"
        st = status_color(entry["status"])
        print(f"  {entry['key']:<35} {ttl_str:<12} {age_str:<16} {st}")

    # Lock keys table
    print()
    print(f"  {BOLD}Lock Keys:{RESET}")
    header = f"  {'Key':<45} {'TTL':<12} {'Status':<10}"
    print(f"  {DIM}{header.strip()}{RESET}")
    print(f"  {DIM}{'─' * 68}{RESET}")

    for entry in metrics["lock_keys"]:
        if entry["ttl"] is not None and entry["ttl"] >= 0:
            ttl_str = f"TTL: {entry['ttl']}s"
        elif entry["ttl"] == -1:
            ttl_str = "no expiry"
        else:
            ttl_str = "-"
        st = status_color(entry["status"])
        print(f"  {entry['key']:<45} {ttl_str:<12} {st}")


# ── PostgreSQL metrics ───────────────────────────────────────────────────────

def collect_pg_metrics(db_url):
    """Connect to PostgreSQL and collect connection/query metrics."""
    metrics = {
        "status": "DOWN",
        "active_connections": 0,
        "active_search_queries": 0,
        "active_queries": [],
        "error": None,
    }

    try:
        conn = psycopg2.connect(db_url, connect_timeout=3)
        conn.autocommit = True
        cur = conn.cursor()
        metrics["status"] = "CONNECTED"

        # Total active connections
        cur.execute(
            "SELECT count(*) FROM pg_stat_activity WHERE state = 'active';"
        )
        metrics["active_connections"] = cur.fetchone()[0]

        # Active queries that look like search queries
        cur.execute("""
            SELECT pid,
                   EXTRACT(EPOCH FROM (now() - query_start))::numeric(10,2) AS duration,
                   LEFT(query, 120) AS query_text
            FROM pg_stat_activity
            WHERE state = 'active'
              AND pid != pg_backend_pid()
            ORDER BY query_start;
        """)
        rows = cur.fetchall()
        for pid, duration, query_text in rows:
            is_search = any(
                kw in (query_text or "").lower()
                for kw in ("search", "public_search", "listing")
            )
            metrics["active_queries"].append({
                "pid": pid,
                "duration": float(duration) if duration else 0,
                "query": query_text or "",
                "is_search": is_search,
            })

        metrics["active_search_queries"] = sum(
            1 for q in metrics["active_queries"] if q["is_search"]
        )

        cur.close()
        conn.close()

    except psycopg2.OperationalError as exc:
        metrics["error"] = str(exc).strip().split("\n")[0]
    except Exception as exc:  # noqa: BLE001
        metrics["error"] = str(exc).strip().split("\n")[0]

    return metrics


def render_pg(metrics):
    """Render the PostgreSQL section of the dashboard."""
    print(separator("POSTGRESQL METRICS"))
    print()

    status = status_color(metrics["status"])
    print(f"  Status:               {status}")

    if metrics["status"] == "DOWN":
        err = metrics.get("error", "unknown")
        print(f"  Error:                {colorize(err, RED)}")
        print()
        return

    print(f"  Active Connections:   {metrics['active_connections']}")

    sq = metrics["active_search_queries"]
    sq_color = GREEN if sq <= 1 else (YELLOW if sq <= 3 else RED)
    print(f"  Active Search Queries: {colorize(str(sq), sq_color)}")

    if metrics["active_queries"]:
        print()
        print(f"  {BOLD}Active Queries:{RESET}")
        header = f"  {'PID':<10} {'Duration':<14} {'Query'}"
        print(f"  {DIM}{header.strip()}{RESET}")
        print(f"  {DIM}{'─' * 68}{RESET}")

        for q in metrics["active_queries"]:
            dur = f"{q['duration']:.1f}s"
            dur_color = GREEN if q["duration"] < 1 else (YELLOW if q["duration"] < 5 else RED)
            query_display = q["query"][:80]
            pid_str = str(q["pid"])
            print(f"  {pid_str:<10} {colorize(dur, dur_color):<23} {DIM}{query_display}{RESET}")
    else:
        print(f"\n  {DIM}No active queries.{RESET}")


# ── System summary ───────────────────────────────────────────────────────────

def render_summary(redis_metrics, pg_metrics):
    """Render the system summary with stampede risk assessment."""
    print(separator("SYSTEM SUMMARY"))
    print()

    # Cache stampede risk
    search_queries = pg_metrics.get("active_search_queries", 0)
    active_locks = sum(
        1 for lk in redis_metrics.get("lock_keys", []) if lk["status"] == "ACTIVE"
    )
    missing_keys = sum(
        1 for ck in redis_metrics.get("cache_keys", []) if ck["status"] == "MISSING"
    )

    if redis_metrics["status"] == "DOWN":
        risk = "CRITICAL"
        reason = "Redis is down — all requests hit the database"
    elif search_queries > 5 and missing_keys > 0:
        risk = "HIGH"
        reason = f"{search_queries} active search queries, {missing_keys} cache keys missing"
    elif search_queries > 3:
        risk = "MEDIUM"
        reason = f"{search_queries} active search queries"
    elif search_queries > 1 and active_locks == 0:
        risk = "WARNING"
        reason = f"{search_queries} concurrent queries, no refresh locks held"
    else:
        risk = "LOW"
        reason = f"only {search_queries} active search quer{'y' if search_queries == 1 else 'ies'}"

    print(f"  Cache Stampede Risk:  {status_color(risk)}  {DIM}({reason}){RESET}")

    # Background refresh status
    if active_locks > 0:
        active_windows = [
            lk["key"].split(":")[-1]
            for lk in redis_metrics.get("lock_keys", [])
            if lk["status"] == "ACTIVE"
        ]
        windows_str = ", ".join(active_windows)
        print(
            f"  Background Refresh:   {status_color('ACTIVE')}  "
            f"{DIM}(lock held for {windows_str} window{'s' if len(active_windows) > 1 else ''}){RESET}"
        )
    else:
        print(f"  Background Refresh:   {status_color('INACTIVE')}  {DIM}(no refresh locks held){RESET}")

    # Overall health
    stale_count = sum(
        1 for ck in redis_metrics.get("cache_keys", []) if ck["status"] == "STALE"
    )
    if stale_count > 0:
        print(
            f"  Stale Entries:        {colorize(str(stale_count), YELLOW)}  "
            f"{DIM}(background revalidation expected){RESET}"
        )

    print()


# ── Dashboard header ─────────────────────────────────────────────────────────

def render_header(interval):
    """Print the dashboard title bar."""
    now = time.strftime("%Y-%m-%d %H:%M:%S")
    title = " PERFORMANCE MONITOR — /public-searches "
    width = 72
    pad = width - len(title)
    left = pad // 2
    right = pad - left

    print(f"{BOLD}{BG_GREEN}{' ' * left}{title}{' ' * right}{RESET}")
    print(f"  {DIM}Refresh: every {interval}s | {now} | Ctrl+C to quit{RESET}")


# ── Main loop ────────────────────────────────────────────────────────────────

def run_dashboard(redis_url, db_url, interval):
    """Main dashboard loop."""
    print(f"{BOLD}Starting monitor...{RESET}")
    print(f"  Redis:      {redis_url}")
    print(f"  PostgreSQL: {db_url}")
    print(f"  Interval:   {interval}s")
    print()
    time.sleep(1)

    try:
        while True:
            clear_screen()

            render_header(interval)

            # Collect metrics
            redis_metrics = collect_redis_metrics(redis_url)
            pg_metrics = collect_pg_metrics(db_url)

            # Render sections
            render_redis(redis_metrics)
            render_pg(pg_metrics)
            render_summary(redis_metrics, pg_metrics)

            # Footer
            print(f"  {DIM}Press Ctrl+C to stop monitoring.{RESET}")

            time.sleep(interval)

    except KeyboardInterrupt:
        print(f"\n{BOLD}{YELLOW}Monitor stopped.{RESET}")
        sys.exit(0)


def parse_args():
    parser = argparse.ArgumentParser(
        description="Live monitoring dashboard for Redis + PostgreSQL performance tests."
    )
    parser.add_argument(
        "--redis-url",
        default="redis://localhost:6379/0",
        help="Redis connection URL (default: redis://localhost:6379/0)",
    )
    parser.add_argument(
        "--db-url",
        default="postgresql://postgres:Omarr.2002@localhost:5432/mchina_db",
        help="PostgreSQL connection URL",
    )
    parser.add_argument(
        "--interval",
        type=float,
        default=2,
        help="Dashboard refresh interval in seconds (default: 2)",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    run_dashboard(args.redis_url, args.db_url, args.interval)
