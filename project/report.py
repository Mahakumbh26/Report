"""
Automated Monitoring Analysis System
A complete, production-ready script for fetching metrics, generating insights,
and producing JSON/PDF reports for actionable DevOps decision-making.

Usage: python report.py --time_range 1h
"""
import os
import argparse
import json
import logging
import requests
from datetime import datetime, timedelta
import pandas as pd
import numpy as np

# reportlab for PDF generation
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

PROMETHEUS_URL = os.environ.get("PROMETHEUS_URL", "http://localhost:9090")

class MonitoringAnalyzer:
    def __init__(self, time_range_str="1h"):
        self.time_range_str = time_range_str
        
    def fetch_prometheus_data(self, query: str):
        url = f"{PROMETHEUS_URL}/api/v1/query"
        try:
            response = requests.get(url, params={"query": query}, timeout=10)
            response.raise_for_status()
            data = response.json()
            if data["status"] == "success" and data["data"]["result"]:
                return data["data"]["result"]
        except Exception as e:
            logging.error(f"Failed to fetch {query}: {e}")
        return []

    def fetch_range_data(self, query: str, step="5m"):
        url = f"{PROMETHEUS_URL}/api/v1/query_range"
        end_time = datetime.utcnow()
        if self.time_range_str.endswith("h"):
            start_time = end_time - timedelta(hours=int(self.time_range_str[:-1]))
        elif self.time_range_str.endswith("d"):
            start_time = end_time - timedelta(days=int(self.time_range_str[:-1]))
        else:
            start_time = end_time - timedelta(hours=1)
            
        try:
            response = requests.get(url, params={
                "query": query,
                "start": start_time.isoformat() + "Z",
                "end": end_time.isoformat() + "Z",
                "step": step
            }, timeout=10)
            response.raise_for_status()
            return response.json().get("data", {}).get("result", [])
        except Exception as e:
            logging.error(f"Failed to fetch range data {query}: {e}")
        return []

    def run_analysis(self):
        logging.info(f"Starting analysis for last {self.time_range_str}...")
        
        # 1. Fetch Latency
        p50 = self.fetch_prometheus_data(f'histogram_quantile(0.50, sum(rate(http_request_duration_seconds_bucket[{self.time_range_str}])) by (le))')
        p95 = self.fetch_prometheus_data(f'histogram_quantile(0.95, sum(rate(http_request_duration_seconds_bucket[{self.time_range_str}])) by (le))')
        p99 = self.fetch_prometheus_data(f'histogram_quantile(0.99, sum(rate(http_request_duration_seconds_bucket[{self.time_range_str}])) by (le))')
        
        val_p50 = float(p50[0]['value'][1]) if p50 and str(p50[0]['value'][1]).lower() != 'nan' else 0.0
        val_p95 = float(p95[0]['value'][1]) if p95 and str(p95[0]['value'][1]).lower() != 'nan' else 0.0
        val_p99 = float(p99[0]['value'][1]) if p99 and str(p99[0]['value'][1]).lower() != 'nan' else 0.0

        # 2. Fetch Throughput & Traffic Spikes
        req_total = self.fetch_prometheus_data(f'sum(rate(http_requests_total[{self.time_range_str}]))')
        throughput = float(req_total[0]['value'][1]) if req_total else 0.0

        req_range = self.fetch_range_data('sum(rate(http_requests_total[5m]))', step="5m")
        traffic_spike = False
        if req_range and 'values' in req_range[0]:
            df = pd.DataFrame(req_range[0]['values'], columns=['time', 'value'])
            df['value'] = df['value'].astype(float)
            if df['value'].max() > df['value'].median() * 3: # 3x median is considered a spike
                traffic_spike = True

        # 3. Error Rate
        error_res = self.fetch_prometheus_data(f'sum(rate(http_requests_total{{status=~"5.."}}[{self.time_range_str}])) / sum(rate(http_requests_total[{self.time_range_str}])) * 100')
        error_rate = float(error_res[0]['value'][1]) if error_res and str(error_res[0]['value'][1]).lower() != 'nan' else 0.0

        # 4. CPU and Memory
        cpu = self.fetch_prometheus_data(f'sum(rate(container_cpu_usage_seconds_total[{self.time_range_str}])) * 100')
        cpu_usage = float(cpu[0]['value'][1]) if cpu else 0.0

        mem_range = self.fetch_range_data('sum(container_memory_usage_bytes)', step="5m")
        memory_leak = False
        mem_current = 0.0
        if mem_range and 'values' in mem_range[0]:
            df_mem = pd.DataFrame(mem_range[0]['values'], columns=['time', 'value'])
            df_mem['value'] = df_mem['value'].astype(float)
            mem_current = df_mem['value'].iloc[-1]
            
            # Simple leak detection: check if memory is monotonically increasing over the period
            if len(df_mem) > 5:
                # Calculate pearson correlation coefficient over time
                correlation = np.corrcoef(np.arange(len(df_mem)), df_mem['value'].values)[0, 1]
                if correlation > 0.9:  # Strongly increasing trend
                    memory_leak = True

        # 5. Service Health
        up = self.fetch_prometheus_data('up')
        service_health = "Healthy"
        if not up or float(up[0]['value'][1]) == 0:
            service_health = "Critical"

        # Generate Insights & Recommendations
        issues = []
        recommendations = []

        if service_health == "Critical":
            issues.append("Service is currently DOWN.")
            recommendations.append("Restart service and check critical application crash logs.")
        
        if val_p95 > 1.0:
            issues.append(f"High latency detected! P95 is {val_p95:.2f}s.")
            recommendations.append("Optimize slow APIs. Consider adding Redis caching for expensive endpoints.")

        if traffic_spike:
            issues.append("Traffic spike observed during this time period.")
            recommendations.append("Scale system using Kubernetes HPA or increase replica count.")

        if error_rate > 2.0:
            issues.append(f"Error rate is dangerously high at {error_rate:.2f}%.")
            recommendations.append("Fix backend 5xx errors by checking recent stack traces.")

        if cpu_usage > 80.0:
            issues.append(f"CPU usage is critically high ({cpu_usage:.1f}%).")
            recommendations.append("Tune expensive background jobs, database queries, or horizontally scale compute.")

        if memory_leak:
            issues.append("Possible memory leak detected! Usage correlates heavily with time (+0.9).")
            recommendations.append("Profile application memory, garbage collection, and check for runaway background processes.")

        # Determine overall condition
        if not issues and service_health == "Healthy":
            if error_rate > 0.5 or cpu_usage > 60:
                service_health = "Warning"
            else:
                issues.append("All metrics are nominal and within healthy bounds.")
        elif issues and service_health != "Critical":
            service_health = "Warning" if len(issues) < 3 else "Critical"

        # Construct final payload
        report = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "time_range": self.time_range_str,
            "system_health": service_health,
            "latency": {
                "p50": f"{val_p50:.3f}s",
                "p95": f"{val_p95:.3f}s",
                "p99": f"{val_p99:.3f}s"
            },
            "error_rate": f"{error_rate:.2f}%",
            "throughput": f"{throughput:.2f} req/s",
            "cpu_usage": f"{cpu_usage:.1f}%",
            "memory_usage": f"{mem_current / (1024**2):.1f} MB",
            "issues_detected": issues,
            "recommendations": recommendations,
        }
        
        return report

    def export_json(self, report, filename):
        with open(filename, 'w') as f:
            json.dump(report, f, indent=4)
        logging.info(f"Saved JSON report to {filename}")

    def export_pdf(self, report, filename):
        doc = SimpleDocTemplate(filename, pagesize=A4)
        styles = getSampleStyleSheet()
        story = []

        title_style = ParagraphStyle('TitleStyle', parent=styles['Title'], fontSize=20, spaceAfter=20, textColor=colors.HexColor("#1a237e"))
        heading_style = ParagraphStyle('Heading', parent=styles['Heading2'], fontSize=14, spaceBefore=10, spaceAfter=5, textColor=colors.HexColor("#1a237e"))
        body_style = ParagraphStyle('Body', parent=styles['Normal'], fontSize=11, spaceAfter=4)
        bullet_style = ParagraphStyle('Bullet', parent=styles['Normal'], fontSize=11, leftIndent=20, bulletIndent=10)

        story.append(Paragraph(f"EMS Standalone Monitoring Report", title_style))
        story.append(Paragraph(f"<b>Time Range Evaluated:</b> Last {report['time_range']}", body_style))
        story.append(Paragraph(f"<b>Generated On:</b> {report['timestamp']}", body_style))
        story.append(Paragraph(f"<b>System Health:</b> {report['system_health']}", body_style))
        story.append(Spacer(1, 15))

        story.append(Paragraph("Metrics Summary", heading_style))
        story.append(Paragraph(f"<b>Throughput:</b> {report['throughput']}", body_style))
        story.append(Paragraph(f"<b>Error Rate:</b> {report['error_rate']}", body_style))
        story.append(Paragraph(f"<b>CPU Usage:</b> {report['cpu_usage']}", body_style))
        story.append(Paragraph(f"<b>Memory Usage:</b> {report['memory_usage']}", body_style))
        story.append(Paragraph(f"<b>Latency (P50):</b> {report['latency']['p50']}", body_style))
        story.append(Paragraph(f"<b>Latency (P95):</b> {report['latency']['p95']}", body_style))
        story.append(Paragraph(f"<b>Latency (P99):</b> {report['latency']['p99']}", body_style))
        story.append(Spacer(1, 15))

        story.append(Paragraph("Issues & Insights", heading_style))
        if 'All metrics are nominal' in report['issues_detected']:
            story.append(Paragraph(report['issues_detected'][0], body_style))
        else:
            for issue in report['issues_detected']:
                story.append(Paragraph(f"• {issue}", bullet_style))
        story.append(Spacer(1, 10))

        story.append(Paragraph("Decision Recommendations", heading_style))
        if not report['recommendations']:
            story.append(Paragraph("✓ No actions required. System is stable.", body_style))
        else:
            for rec in report['recommendations']:
                story.append(Paragraph(f"• {rec}", bullet_style))

        doc.build(story)
        logging.info(f"Saved PDF report to {filename}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate Automated Monitoring Analysis System Reports.")
    parser.add_argument("--time_range", type=str, default="1h", help="Time range to analyze (e.g., 1h, 24h)")
    args = parser.parse_args()

    analyzer = MonitoringAnalyzer(time_range_str=args.time_range)
    report_data = analyzer.run_analysis()

    timestamp_str = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    
    # Export the files
    analyzer.export_json(report_data, f"report_{timestamp_str}.json")
    analyzer.export_pdf(report_data, f"report_{timestamp_str}.pdf")
