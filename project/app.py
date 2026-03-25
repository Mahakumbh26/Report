"""
EMS Monitoring Report System - Flask Application
"""
import io
import os
from datetime import datetime
from flask import Flask, jsonify, Response, send_file

# 🔥 SAFE IMPORTS (IMPORTANT)
try:
    from services.prometheus_service import fetch_all_metrics
except Exception as e:
    print("Prometheus import error:", e)
    fetch_all_metrics = None

try:
    from services.analysis_service import analyze_metrics
except Exception as e:
    print("Analysis import error:", e)
    analyze_metrics = None

try:
    from services.report_service import render_html_report, generate_pdf_report
except Exception as e:
    print("Report import error:", e)
    render_html_report = None
    generate_pdf_report = None

app = Flask(__name__)


def _get_metrics_and_analysis():
    if not fetch_all_metrics or not analyze_metrics:
        return {}, []

    try:
        metrics = fetch_all_metrics()
        analysis = analyze_metrics(metrics)
        return metrics, analysis
    except Exception as e:
        print("Metrics/Analysis error:", e)
        return {}, []


# 🔥 HEALTHCHECK (VERY IMPORTANT)
@app.route("/health", methods=["GET"])
def health():
    return "OK", 200


@app.route("/metrics", methods=["GET"])
def get_metrics():
    if not fetch_all_metrics:
        return jsonify({"error": "Prometheus not available"}), 500

    try:
        metrics = fetch_all_metrics()
        return jsonify({"status": "ok", "metrics": metrics})
    except Exception as e:
        return jsonify({"error": str(e)}), 503


@app.route("/analysis", methods=["GET"])
def get_analysis():
    try:
        metrics, analysis = _get_metrics_and_analysis()
        return jsonify({"status": "ok", "analysis": analysis})
    except Exception as e:
        return jsonify({"error": str(e)}), 503


@app.route("/report/html", methods=["GET"])
def get_html_report():
    if not render_html_report:
        return jsonify({"error": "Report service unavailable"}), 500

    try:
        metrics, analysis = _get_metrics_and_analysis()
        html = render_html_report(metrics, analysis)
        return Response(html, mimetype="text/html")
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/report/pdf", methods=["GET"])
def get_pdf_report():
    if not generate_pdf_report:
        return jsonify({"error": "PDF service unavailable"}), 500

    try:
        metrics, analysis = _get_metrics_and_analysis()
        pdf_bytes = generate_pdf_report(metrics, analysis)

        return send_file(
            io.BytesIO(pdf_bytes),
            mimetype="application/pdf",
            as_attachment=True,
            download_name="ems_report.pdf"
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/send-report", methods=["POST"])
def send_report():
    return get_pdf_report()


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print("Running on PORT:", port)
    app.run(host="0.0.0.0", port=port)