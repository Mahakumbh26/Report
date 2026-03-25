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


def get_metric_grouped(query: str) -> dict:
    """Returns a dict mapping { 'project/instance': value }"""
    if not PROMETHEUS_URL:
        return {}

    try:
        response = requests.get(
            PROMETHEUS_URL,
            params={"query": query},
            timeout=2
        )
        response.raise_for_status()
        data = response.json()

        results = data.get("data", {}).get("result", [])
        grouped = {}
        for res in results:
            instance = res.get("metric", {}).get("project", res.get("metric", {}).get("instance", "unknown_instance"))
            try:
                grouped[instance] = float(res["value"][1])
            except (ValueError, TypeError, IndexError):
                pass
        return grouped

    except Exception as e:
        print("Metric error:", e)
        return {}


def get_metric_range_grouped(query: str, minutes: int = 30) -> dict:
    """Returns a dict mapping { 'project/instance': [(time, value), ...] }"""
    if not PROMETHEUS_RANGE_URL:
        return {}

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
        grouped = {}
        for res in results:
            instance = res.get("metric", {}).get("project", res.get("metric", {}).get("instance", "unknown_instance"))
            values = res.get("values", [])
            grouped[instance] = [(float(v[0]), float(v[1])) for v in values]
            
        return grouped

    except Exception as e:
        print("Range error:", e)
        return {}


def fetch_all_metrics() -> dict:
    """
    Fetches metrics and builds a dict formatted as:
    {
      "instance_1": {"cpu_usage": 45.0, "memory_usage": ...},
      "instance_2": {"cpu_usage": 20.0, ...}
    }
    """
    try:
        queries = {
            "cpu_usage": '100 - (avg by (instance) (rate(node_cpu_seconds_total{mode="idle"}[5m])) * 100)',
            "memory_usage": '(1 - (node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes)) * 100',
            "http_request_rate": 'sum by (instance) (rate(http_requests_total[5m]))',
            "error_rate": 'sum by (instance) (rate(http_requests_total{status=~"5.."}[5m])) / sum by (instance) (rate(http_requests_total[5m])) * 100',
            "response_time_avg": 'histogram_quantile(0.95, sum by (le, instance) (rate(http_request_duration_seconds_bucket[5m])))'
        }

        # Fetch grouped data per metric
        raw_metrics = {}
        for name, query in queries.items():
            raw_metrics[name] = get_metric_grouped(query)

        # Trends
        cpu_trend = get_metric_range_grouped(queries["cpu_usage"])
        response_time_trend = get_metric_range_grouped(queries["response_time_avg"])

        # Reorganize from {metric_name: {instance: value}} back to {instance: {metric_name: value}}
        grouped_by_instance = {}
        all_instances = set()
        
        for metric_dict in raw_metrics.values():
            all_instances.update(metric_dict.keys())
        all_instances.update(cpu_trend.keys())
        all_instances.update(response_time_trend.keys())

        # Give a fallback if prometheus returned absolutely empty data but no error
        if not all_instances:
            return {}

        for instance in all_instances:
            instance_data = {}
            for name in queries.keys():
                instance_data[name] = raw_metrics[name].get(instance)
            
            instance_data["cpu_trend"] = cpu_trend.get(instance, [])
            instance_data["response_time_trend"] = response_time_trend.get(instance, [])
            
            grouped_by_instance[instance] = instance_data

        return grouped_by_instance

    except Exception as e:
        print("Fetch error:", e)
        return {}