"""
Prometheus Service - SAFE VERSION (Railway compatible)
"""
import os
import requests
from datetime import datetime, timedelta
from typing import Optional

PROMETHEUS_BASE_URL = os.environ.get("PROMETHEUS_URL")

if PROMETHEUS_BASE_URL:
    PROMETHEUS_URL = PROMETHEUS_BASE_URL + "/api/v1/query"
    PROMETHEUS_RANGE_URL = PROMETHEUS_BASE_URL + "/api/v1/query_range"
else:
    PROMETHEUS_URL = None
    PROMETHEUS_RANGE_URL = None


def get_metric(query: str) -> Optional[float]:
    if not PROMETHEUS_URL:
        return None

    try:
        response = requests.get(
            PROMETHEUS_URL,
            params={"query": query},
            timeout=2
        )
        response.raise_for_status()
        data = response.json()

        results = data.get("data", {}).get("result", [])
        if not results:
            return None

        return float(results[0]["value"][1])

    except Exception as e:
        print("Metric error:", e)
        return None


def get_metric_range(query: str, minutes: int = 30) -> list:
    if not PROMETHEUS_RANGE_URL:
        return []

    try:
        end = datetime.utcnow()
        start = end - timedelta(minutes=minutes)

        response = requests.get(
            PROMETHEUS_RANGE_URL,
            params={
                "query": query,
                "start": start.isoformat() + "Z",
                "end": end.isoformat() + "Z",
                "step": "60s"
            },
            timeout=2
        )
        response.raise_for_status()
        data = response.json()

        results = data.get("data", {}).get("result", [])
        if not results:
            return []

        return [(float(v[0]), float(v[1])) for v in results[0].get("values", [])]

    except Exception as e:
        print("Range error:", e)
        return []


def fetch_all_metrics() -> dict:
    try:
        queries = {
            "cpu_usage": '100 - (avg(rate(node_cpu_seconds_total{mode="idle"}[5m])) * 100)',
            "memory_usage": '(1 - (node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes)) * 100',
            "http_request_rate": 'sum(rate(http_requests_total[5m]))',
            "error_rate": 'sum(rate(http_requests_total{status=~"5.."}[5m])) / sum(rate(http_requests_total[5m])) * 100',
            "response_time_avg": 'histogram_quantile(0.95, sum(rate(http_request_duration_seconds_bucket[5m])) by (le))'
        }

        metrics = {}
        for name, query in queries.items():
            metrics[name] = get_metric(query)

        metrics["cpu_trend"] = get_metric_range(queries["cpu_usage"])
        metrics["response_time_trend"] = get_metric_range(queries["response_time_avg"])

        return metrics

    except Exception as e:
        print("Fetch error:", e)
        return {}