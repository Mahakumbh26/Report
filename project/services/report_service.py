"""
Report Service - Generates HTML and PDF reports using Jinja2 + ReportLab
"""
import io
from datetime import datetime
from jinja2 import Environment, FileSystemLoader, select_autoescape
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable, PageBreak
)
from reportlab.lib.enums import TA_CENTER, TA_LEFT

import os

TEMPLATES_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "templates")


def _calc_global_status(grouped_analysis: dict) -> str:
    severities = []
    for ana in grouped_analysis.values():
        val = ana.get("overall_status", "HEALTHY")
        severities.append(val)
        
    if "CRITICAL" in severities: return "CRITICAL"
    if "DEGRADED" in severities: return "DEGRADED"
    if "WARNING" in severities: return "WARNING"
    return "HEALTHY"


def render_html_report(metrics: dict, analysis: dict) -> str:
    """Render the HTML report using Jinja2 template grouped by instance/project."""
    env = Environment(
        loader=FileSystemLoader(TEMPLATES_DIR),
        autoescape=select_autoescape(["html"])
    )
    template = env.get_template("report.html")
    
    projects = {}
    for instance, met in metrics.items():
        ana = analysis.get(instance, {})
        met_ctx = dict(met)
        met_ctx["cpu_trend_points"] = len(met.get("cpu_trend", []))
        met_ctx["response_time_trend_points"] = len(met.get("response_time_trend", []))
        projects[instance] = {
            "metrics": met_ctx,
            "analysis": ana
        }

    global_status = _calc_global_status(analysis) if len(analysis) > 0 else "UNKNOWN"

    return template.render(
        projects=projects,
        global_status=global_status,
        timestamp=datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
    )


def generate_pdf_report(metrics: dict, analysis: dict) -> bytes:
    """Generate a PDF report iterating over projects and return as bytes."""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=20 * mm,
        leftMargin=20 * mm,
        topMargin=20 * mm,
        bottomMargin=20 * mm
    )

    styles = getSampleStyleSheet()
    story = []

    # --- Custom Styles ---
    title_style = ParagraphStyle(
        "Title", parent=styles["Title"],
        fontSize=22, textColor=colors.HexColor("#1a237e"),
        spaceAfter=4
    )
    subtitle_style = ParagraphStyle(
        "Subtitle", parent=styles["Normal"],
        fontSize=10, textColor=colors.grey, spaceAfter=16
    )
    section_style = ParagraphStyle(
        "Section", parent=styles["Heading2"],
        fontSize=13, textColor=colors.HexColor("#1a237e"),
        spaceBefore=16, spaceAfter=8,
        borderPad=4
    )
    project_title_style = ParagraphStyle(
        "ProjectTitle", parent=styles["Heading1"],
        fontSize=16, textColor=colors.HexColor("#1a237e"),
        spaceBefore=16, spaceAfter=12,
        alignment=TA_LEFT
    )
    body_style = ParagraphStyle(
        "Body", parent=styles["Normal"],
        fontSize=10, leading=14, spaceAfter=6
    )

    timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
    global_status = _calc_global_status(analysis) if len(analysis) > 0 else "UNKNOWN"

    status_colors = {
        "HEALTHY": colors.HexColor("#2e7d32"),
        "WARNING": colors.HexColor("#f57f17"),
        "DEGRADED": colors.HexColor("#e65100"),
        "CRITICAL": colors.HexColor("#b71c1c"),
    }
    status_color = status_colors.get(global_status, colors.grey)

    # --- Cover Page ---
    story.append(Spacer(1, 40*mm))
    story.append(Paragraph("EMS Monitoring Report", title_style))
    story.append(Paragraph("Production Infrastructure Health & Performance Analysis", subtitle_style))
    story.append(Paragraph(f"Generated: {timestamp}", subtitle_style))
    story.append(Paragraph(
        f'Global System Status: <font color="{status_color.hexval() if hasattr(status_color, "hexval") else "#333333"}"><b>{global_status}</b></font>',
        body_style
    ))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#1a237e"), spaceAfter=12))
    story.append(PageBreak())

    # --- Project Loop ---
    if not metrics:
        story.append(Paragraph("No metrics data found for any projects.", body_style))
    
    for project_name, met in metrics.items():
        ana = analysis.get(project_name, {})
        overall_status = ana.get("overall_status", "UNKNOWN")
        proj_status_color = status_colors.get(overall_status, colors.grey)

        # Project Header
        story.append(Paragraph(f"Project / Instance: {project_name}", project_title_style))
        story.append(Paragraph(
            f'Status: <font color="{proj_status_color.hexval() if hasattr(proj_status_color, "hexval") else "#333333"}"><b>{overall_status}</b></font>',
            body_style
        ))
        story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#dddddd"), spaceAfter=12))

        # Metrics Summary Table
        story.append(Paragraph("Metrics Summary", section_style))

        metric_rows = [["Metric", "Value", "Status"]]
        metric_map = {
            "cpu_usage": ("CPU Usage", "%"),
            "memory_usage": ("Memory Usage", "%"),
            "error_rate": ("Error Rate", "%"),
            "http_request_rate": ("HTTP Request Rate", "/s"),
            "response_time_avg": ("Response Time (p95)", "s"),
        }
        thresholds = {"cpu_usage": 80, "memory_usage": 75, "error_rate": 5}

        for key, (label, unit) in metric_map.items():
            val = met.get(key)
            if val is None:
                continue
            threshold = thresholds.get(key)
            if threshold:
                status = "⚠ High" if val > threshold else "✓ OK"
            else:
                status = "✓ Tracked"
            metric_rows.append([label, f"{val:.2f}{unit}", status])

        if len(metric_rows) > 1:
            t = Table(metric_rows, colWidths=[80 * mm, 50 * mm, 40 * mm])
            t.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1a237e")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 10),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.HexColor("#f8f9ff"), colors.white]),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cccccc")),
                ("PADDING", (0, 0), (-1, -1), 6),
            ]))
            story.append(t)

        story.append(Spacer(1, 12))

        # Issues Detected
        story.append(Paragraph(f"Issues Detected ({ana.get('total_issues', 0)})", section_style))

        issues = ana.get("issues", [])
        if not issues:
            story.append(Paragraph("✓ No issues detected — all metrics within normal thresholds.", body_style))
        else:
            severity_bg = {
                "CRITICAL": colors.HexColor("#ffebee"),
                "HIGH": colors.HexColor("#fff3e0"),
                "MEDIUM": colors.HexColor("#fffde7"),
            }
            for issue in issues:
                sev = issue.get("severity", "MEDIUM")
                bg = severity_bg.get(sev, colors.HexColor("#f9f9f9"))

                issue_data = [
                    ["Issue", issue.get("issue", "")],
                    ["Severity", sev],
                    ["Metric", issue.get("metric", "")],
                    ["Current Value", issue.get("current_value", "")],
                    ["Threshold", issue.get("threshold", "")],
                    ["Root Cause", issue.get("cause", "")],
                    ["Solution", issue.get("solution", "")],
                    ["Business Impact", issue.get("business_impact", "")],
                ]

                it = Table(issue_data, colWidths=[45 * mm, 125 * mm])
                it.setStyle(TableStyle([
                    ("BACKGROUND", (0, 0), (-1, -1), bg),
                    ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, -1), 9),
                    ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#dddddd")),
                    ("PADDING", (0, 0), (-1, -1), 6),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ]))
                story.append(it)
                story.append(Spacer(1, 8))
        
        story.append(PageBreak())

    # --- Footer ---
    story.append(Spacer(1, 16))
    story.append(HRFlowable(width="100%", thickness=0.5, color=colors.grey))
    story.append(Paragraph(
        f"EMS Monitoring System — Auto-generated report — {timestamp}",
        ParagraphStyle("Footer", parent=styles["Normal"], fontSize=8,
                       textColor=colors.grey, alignment=TA_CENTER, spaceBefore=8)
    ))

    doc.build(story)
    return buffer.getvalue()
