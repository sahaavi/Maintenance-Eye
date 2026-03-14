"""
Report Rendering Service
Renders inspection report data into HTML and PDF using Jinja2 + WeasyPrint.
"""

import logging
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

logger = logging.getLogger("maintenance-eye.services.report_renderer")

# Template directory
TEMPLATE_DIR = Path(__file__).parent.parent / "templates"
_jinja_env: Environment | None = None


def _get_jinja_env() -> Environment:
    """Lazy-initialize Jinja2 environment."""
    global _jinja_env
    if _jinja_env is None:
        _jinja_env = Environment(
            loader=FileSystemLoader(str(TEMPLATE_DIR)),
            autoescape=True,
        )
    return _jinja_env


def render_report_html(report_data: dict) -> str:
    """
    Render an inspection report as HTML.

    Args:
        report_data: The report dict produced by `generate_report` tool.
                     Expected keys: report_id, generated_at, asset, inspector,
                     overall_condition, findings_summary, open_work_orders,
                     next_inspection_recommendation.

    Returns:
        Rendered HTML string.
    """
    env = _get_jinja_env()
    template = env.get_template("inspection_report.html")

    asset = report_data.get("asset", {})
    asset_name = asset.get("name", asset.get("asset_id", "Unknown Asset"))

    work_orders = report_data.get("open_work_orders", [])

    html = template.render(
        report=report_data,
        asset_name=asset_name,
        work_orders=work_orders,
    )

    logger.info(f"Rendered HTML report: {report_data.get('report_id', '?')}")
    return html


def render_report_pdf(report_data: dict) -> bytes:
    """
    Render an inspection report as PDF using WeasyPrint.

    Args:
        report_data: Same as render_report_html.

    Returns:
        PDF bytes.
    """
    html_content = render_report_html(report_data)

    try:
        from weasyprint import HTML

        pdf_bytes = HTML(string=html_content).write_pdf()
        logger.info(
            f"Rendered PDF report: {report_data.get('report_id', '?')} ({len(pdf_bytes)} bytes)"
        )
        return pdf_bytes
    except ImportError:
        logger.error("WeasyPrint not installed — cannot generate PDF")
        raise RuntimeError(
            "PDF generation requires WeasyPrint. Install with: pip install weasyprint"
        )
    except Exception as e:
        logger.error(f"PDF generation failed: {e}")
        raise
