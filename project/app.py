"""
EMS Monitoring Report System - Flask Application
Prometheus → Analysis → HTML/PDF Reports → EMS Integration
"""
import io
import os
from datetime import datetime

from flask import Flask, jsonify, Response, send_file

from services.prometheus_service import fetch_all_metrics
from services.analysis_service import analyze_metrics
from services.report_service import render_html_report, generate_pdf_report

app = Flask(__name__)


def _get_metrics_and_analysis():
    """Fetch metrics from Prometheus and run analysis. Returns (metrics, analysis)."""
    metrics = fetch_all_metrics()
    analysis = analyze_metrics(metrics)
    return metrics, analysis


# ── GET /health ──────────────────────────────
# Railway healthcheck hits this — must always return 200
@app.route("/health", methods=["GET"])
def health():
    return jsonify({
        "status": "ok",
        "service": "EMS Monitoring API",
        "timestamp": datetime.utcnow().isoformat(),
        "prometheus_url": os.environ.get("PROMETHEUS_URL", "http://localhost:9090")
    }), 200


# ── GET /metrics ─────────────────────────────
@app.route("/metrics", methods=["GET"])
def get_metrics():
    try:
        metrics = fetch_all_metrics()
        serializable = {k: v for k, v in metrics.items() if not isinstance(v, list)}
        serializable["cpu_trend_points"] = len(metrics.get("cpu_trend", []))
        serializable["response_time_trend_points"] = len(metrics.get("response_time_trend", []))
        return jsonify({
            "status": "ok",
            "timestamp": datetime.utcnow().isoformat(),
            "metrics": serializable
        })
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 503


# ── GET /analysis ────────────────────────────
@app.route("/analysis", methods=["GET"])
def get_analysis():
    try:
        metrics, analysis = _get_metrics_and_analysis()
        return jsonify({
            "status": "ok",
            "timestamp": datetime.utcnow().isoformat(),
            "analysis": analysis
        })
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 503


# ── GET /report/html ─────────────────────────
@app.route("/report/html", methods=["GET"])
def get_html_report():
    try:
        metrics, analysis = _get_metrics_and_analysis()
        html = render_html_report(metrics, analysis)
        return Response(html, mimetype="text/html")
    except Exception as e:
        return jsonify({"status": "error", "message": f"Report generation failed: {str(e)}"}), 500


# ── GET /report/pdf ──────────────────────────
@app.route("/report/pdf", methods=["GET"])
def get_pdf_report():
    try:
        metrics, analysis = _get_metrics_and_analysis()
        pdf_bytes = generate_pdf_report(metrics, analysis)
        filename = f"ems_report_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.pdf"
        return send_file(
            io.BytesIO(pdf_bytes),
            mimetype="application/pdf",
            as_attachment=True,
            download_name=filename
        )
    except Exception as e:
        return jsonify({"status": "error", "message": f"PDF generation failed: {str(e)}"}), 500


# ── POST /send-report ────────────────────────
@app.route("/send-report", methods=["POST"])
def send_report():
    try:
        metrics, analysis = _get_metrics_and_analysis()
        pdf_bytes = generate_pdf_report(metrics, analysis)
        filename = f"ems_report_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.pdf"
        return send_file(
            io.BytesIO(pdf_bytes),
            mimetype="application/pdf",
            as_attachment=True,
            download_name=filename
        )
    except Exception as e:
        return jsonify({"status": "error", "message": f"Failed to generate report: {str(e)}"}), 500


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
