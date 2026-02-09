#!/usr/bin/env python3
"""Simple HTTP load benchmark for ADE API endpoints."""

from __future__ import annotations

import argparse
import concurrent.futures
import math
import sys
import time
import urllib.error
import urllib.request
from collections import Counter


def _percentile(values: list[float], percentile: float) -> float:
    if not values:
        return 0.0
    sorted_values = sorted(values)
    rank = math.ceil((percentile / 100.0) * len(sorted_values)) - 1
    index = max(0, min(rank, len(sorted_values) - 1))
    return sorted_values[index]


def _request_once(url: str, timeout: float) -> tuple[bool, int | None, float]:
    started = time.perf_counter()
    status_code: int | None = None
    ok = False

    try:
        request = urllib.request.Request(url=url, method="GET")
        with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310
            status_code = int(response.status)
            response.read(1)
            ok = 200 <= status_code < 400
    except urllib.error.HTTPError as exc:
        status_code = int(exc.code)
    except urllib.error.URLError:
        status_code = None

    elapsed = time.perf_counter() - started
    return ok, status_code, elapsed


def main() -> int:
    parser = argparse.ArgumentParser(description="Benchmark an ADE API HTTP endpoint.")
    parser.add_argument(
        "--url",
        default="http://localhost:8000/api/v1/health",
        help="Endpoint URL to benchmark (default: %(default)s)",
    )
    parser.add_argument(
        "--requests",
        type=int,
        default=2000,
        help="Total number of requests to execute (default: %(default)s)",
    )
    parser.add_argument(
        "--concurrency",
        type=int,
        default=50,
        help="Concurrent request workers (default: %(default)s)",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=5.0,
        help="Per-request timeout in seconds (default: %(default)s)",
    )
    args = parser.parse_args()

    if args.requests < 1:
        print("error: --requests must be >= 1", file=sys.stderr)
        return 2
    if args.concurrency < 1:
        print("error: --concurrency must be >= 1", file=sys.stderr)
        return 2
    if args.timeout <= 0:
        print("error: --timeout must be > 0", file=sys.stderr)
        return 2

    successes = 0
    failures = 0
    latencies: list[float] = []
    status_codes: Counter[str] = Counter()

    wall_started = time.perf_counter()

    with concurrent.futures.ThreadPoolExecutor(max_workers=args.concurrency) as executor:
        futures = [
            executor.submit(_request_once, args.url, args.timeout)
            for _ in range(args.requests)
        ]
        for future in concurrent.futures.as_completed(futures):
            ok, status_code, elapsed = future.result()
            latencies.append(elapsed)
            if status_code is None:
                status_codes["error"] += 1
            else:
                status_codes[str(status_code)] += 1
            if ok:
                successes += 1
            else:
                failures += 1

    duration = max(time.perf_counter() - wall_started, 1e-9)
    throughput = args.requests / duration

    p50_ms = _percentile(latencies, 50) * 1000.0
    p95_ms = _percentile(latencies, 95) * 1000.0
    p99_ms = _percentile(latencies, 99) * 1000.0

    print("ADE API benchmark result")
    print(f"url: {args.url}")
    print(f"requests: {args.requests}")
    print(f"concurrency: {args.concurrency}")
    print(f"duration_seconds: {duration:.3f}")
    print(f"throughput_rps: {throughput:.2f}")
    print(f"successes: {successes}")
    print(f"failures: {failures}")
    print(f"latency_p50_ms: {p50_ms:.2f}")
    print(f"latency_p95_ms: {p95_ms:.2f}")
    print(f"latency_p99_ms: {p99_ms:.2f}")
    status_summary = ", ".join(f"{code}={count}" for code, count in sorted(status_codes.items()))
    print(f"status_codes: {status_summary}")

    return 0 if failures == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
