"""
Prometheus Service - Fetches metrics from Prometheus HTTP API
"""
import os
import requests
from datetime import datetime, timedelta
from typing import Optional

PROMETHEUS_URL = os.environ.get("PROMETHEUS_URL", "http://localhost:9090") + "/api/v1/query"
PROMETHEUS_RANGE_URL = os.environ.get("PROMETHEUS_URL", "http://localhost:9090") + "/api/v1/query_range"


def get_metric(query: str) -> Optional[float]:
    """Fetch a single scalar metric value from Prometheus."""
    try:
        response = requests.get(
            PROMETHEUS_URL,
            params={"query": query},
            timeout=5
        )
        response.raise_for_status()
        data = response.json()

        results = data.get("data", {}).get("result", [])
        if not results:
            return None

        # Return first result value (index 1 is the value, index 0 is timestamp)
        return float(results[0]["value"][1])

    except requests.exceptions.ConnectionError:
        raise ConnectionError("Prometheus is not reachable at " + PROMETHEUS_URL)
    except requests.exceptions.Timeout:
        raise TimeoutError("Prometheus request timed out")
    except (KeyError, IndexError, ValueError):
        return None


def get_metric_range(query: str, minutes: int = 30) -> list:
    """Fetch metric values over a time range (for trend/anomaly detection)."""
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
            timeout=5
        )
        response.raise_for_status()
        data = response.json()

        results = data.get("data", {}).get("result", [])
        if not results:
            return []

        # Return list of (timestamp, value) tuples
        return [(float(v[0]), float(v[1])) for v in results[0].get("values", [])]

    except (requests.exceptions.ConnectionError, requests.exceptions.Timeout):
        return []
    except (KeyError, IndexError, ValueError):
        return []


def fetch_all_metrics() -> dict:
    """Fetch all EMS-relevant metrics from Prometheus."""
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

    # Fetch range data for trend analysis
    metrics["cpu_trend"] = get_metric_range(queries["cpu_usage"])
    metrics["response_time_trend"] = get_metric_range(queries["response_time_avg"])

    return metrics
