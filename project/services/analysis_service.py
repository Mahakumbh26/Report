"""
Analysis Service - Rule-based + anomaly detection on fetched metrics
"""
from typing import Optional

# Thresholds
CPU_THRESHOLD = 80.0
MEMORY_THRESHOLD = 75.0
ERROR_RATE_THRESHOLD = 5.0
RESPONSE_TIME_SPIKE_RATIO = 1.5  # 50% increase = spike
SMA_WINDOW = 5  # Simple moving average window size


def simple_moving_average(values: list, window: int = SMA_WINDOW) -> list:
    """Calculate simple moving average over a list of values."""
    if len(values) < window:
        return values
    sma = []
    for i in range(len(values)):
        if i < window - 1:
            sma.append(values[i])
        else:
            avg = sum(values[i - window + 1:i + 1]) / window
            sma.append(avg)
    return sma


def detect_trend_spike(trend_data: list) -> Optional[float]:
    """
    Detect if the latest value is a spike compared to SMA.
    Returns spike ratio if detected, else None.
    """
    if not trend_data or len(trend_data) < SMA_WINDOW + 1:
        return None

    values = [v for _, v in trend_data]
    sma = simple_moving_average(values)

    latest = values[-1]
    baseline = sma[-2]  # SMA before latest point

    if baseline == 0:
        return None

    ratio = latest / baseline
    return ratio if ratio >= RESPONSE_TIME_SPIKE_RATIO else None


def analyze_metrics(metrics: dict) -> dict:
    """
    Run rule-based analysis on metrics.
    Returns structured issues, summary, and recommendations.
    """
    issues = []
    healthy = []

    cpu = metrics.get("cpu_usage")
    memory = metrics.get("memory_usage")
    error_rate = metrics.get("error_rate")
    response_time = metrics.get("response_time_avg")
    response_trend = metrics.get("response_time_trend", [])

    # --- CPU Analysis ---
    if cpu is not None:
        if cpu > CPU_THRESHOLD:
            issues.append({
                "metric": "CPU Usage",
                "current_value": f"{cpu:.2f}%",
                "threshold": f"{CPU_THRESHOLD}%",
                "severity": "HIGH" if cpu > 90 else "MEDIUM",
                "issue": "High CPU Utilization",
                "cause": "Excessive compute load — likely caused by unoptimized queries, background jobs, or traffic spikes.",
                "solution": "Scale horizontally, optimize heavy queries, review cron jobs, or enable auto-scaling.",
                "business_impact": "Slow response times for EMS users, potential service degradation or downtime."
            })
        else:
            healthy.append({"metric": "CPU Usage", "value": f"{cpu:.2f}%", "status": "OK"})

    # --- Memory Analysis ---
    if memory is not None:
        if memory > MEMORY_THRESHOLD:
            issues.append({
                "metric": "Memory Usage",
                "current_value": f"{memory:.2f}%",
                "threshold": f"{MEMORY_THRESHOLD}%",
                "severity": "HIGH" if memory > 90 else "MEDIUM",
                "issue": "Memory Pressure Detected",
                "cause": "High heap usage or memory leaks in application processes.",
                "solution": "Restart affected services, profile memory usage, increase RAM, or optimize data caching.",
                "business_impact": "Risk of OOM kills, application crashes, and data loss for active EMS sessions."
            })
        else:
            healthy.append({"metric": "Memory Usage", "value": f"{memory:.2f}%", "status": "OK"})

    # --- Error Rate Analysis ---
    if error_rate is not None:
        if error_rate > ERROR_RATE_THRESHOLD:
            issues.append({
                "metric": "HTTP Error Rate",
                "current_value": f"{error_rate:.2f}%",
                "threshold": f"{ERROR_RATE_THRESHOLD}%",
                "severity": "CRITICAL" if error_rate > 20 else "HIGH",
                "issue": "High HTTP Failure Rate",
                "cause": "Backend exceptions, misconfigured routes, or downstream service failures.",
                "solution": "Review application error logs, check dependent services, validate recent deployments.",
                "business_impact": "Users experiencing failed requests in EMS — impacts payroll, attendance, and HR workflows."
            })
        else:
            healthy.append({"metric": "Error Rate", "value": f"{error_rate:.2f}%", "status": "OK"})

    # --- Response Time Spike Detection (Anomaly) ---
    spike_ratio = detect_trend_spike(response_trend)
    if spike_ratio:
        issues.append({
            "metric": "Response Time",
            "current_value": f"{response_time:.3f}s" if response_time else "N/A",
            "threshold": f"{RESPONSE_TIME_SPIKE_RATIO}x SMA baseline",
            "severity": "HIGH",
            "issue": "Response Time Spike Detected",
            "cause": f"Response time increased {spike_ratio:.1f}x above moving average baseline — possible DB slowdown or resource contention.",
            "solution": "Check slow query logs, review DB connection pool, inspect recent code changes.",
            "business_impact": "EMS pages loading slowly — degraded user experience for HR and management teams."
        })
    elif response_time is not None:
        healthy.append({"metric": "Response Time (p95)", "value": f"{response_time:.3f}s", "status": "OK"})

    return {
        "total_issues": len(issues),
        "issues": issues,
        "healthy_metrics": healthy,
        "overall_status": _overall_status(issues)
    }


def _overall_status(issues: list) -> str:
    """Derive overall system status from detected issues."""
    if not issues:
        return "HEALTHY"
    severities = [i["severity"] for i in issues]
    if "CRITICAL" in severities:
        return "CRITICAL"
    if "HIGH" in severities:
        return "DEGRADED"
    return "WARNING"
