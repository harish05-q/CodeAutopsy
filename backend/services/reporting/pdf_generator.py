"""
PDF Report Generator Service.

Generates a beautiful, downloadable executive summary PDF using ReportLab.
Consumes the unified pipeline artifacts to stitch together a comprehensive report.
"""

from io import BytesIO
from typing import Any

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    PageBreak,
)

from backend.core.logger import get_logger
from backend.models.schemas import RiskFinding

logger = get_logger(__name__)


def generate_pdf_report(
    repo_name: str,
    scan_stats: dict[str, Any],
    parse_stats: dict[str, Any],
    dependency_stats: dict[str, Any],
    call_stats: dict[str, Any],
    risks: list[RiskFinding],
    llm_autopsy: dict[str, Any] | None,
) -> bytes:
    """
    Generate the CodeAutopsy PDF report.
    Returns the PDF bytes.
    """
    logger.info("generating_pdf_report", repo_name=repo_name)
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        rightMargin=72,
        leftMargin=72,
        topMargin=72,
        bottomMargin=18,
    )

    Story = []
    styles = getSampleStyleSheet()

    # Custom Styles
    title_style = styles["Title"]
    h1_style = styles["Heading1"]
    h2_style = styles["Heading2"]
    normal_style = styles["Normal"]
    code_style = ParagraphStyle(
        "CodeStyle",
        parent=styles["Normal"],
        fontName="Courier",
        fontSize=9,
        textColor=colors.darkblue,
    )

    # 1. Title Page
    Story.append(Spacer(1, 2 * inch))
    Story.append(Paragraph("CodeAutopsy Report", title_style))
    Story.append(Spacer(1, 0.5 * inch))
    Story.append(Paragraph(f"<b>Repository:</b> {repo_name}", h2_style))
    Story.append(Spacer(1, 2 * inch))
    Story.append(PageBreak())

    # 2. Executive Summary (from LLM if available)
    if llm_autopsy:
        Story.append(Paragraph("Executive Summary", h1_style))
        Story.append(Paragraph(llm_autopsy.get("executive_summary", "No summary provided."), normal_style))
        Story.append(Spacer(1, 0.2 * inch))
        
        score = llm_autopsy.get("quality_score", "N/A")
        Story.append(Paragraph(f"<b>Overall Quality Score:</b> {score}/100", normal_style))
        Story.append(Spacer(1, 0.2 * inch))

        Story.append(Paragraph("<b>Primary Architectural Pattern:</b>", normal_style))
        Story.append(Paragraph(llm_autopsy.get("architecture_pattern", "Unknown"), normal_style))
        Story.append(Spacer(1, 0.5 * inch))

    # 3. Codebase Statistics
    Story.append(Paragraph("Codebase Statistics", h1_style))
    
    stats_data = [
        ["Metric", "Value"],
        ["Total Files", str(scan_stats.get("total_files", 0))],
        ["Python Files", str(scan_stats.get("python_files", 0))],
        ["Modules Parsed", str(parse_stats.get("modules", 0))],
        ["Total Functions", str(parse_stats.get("functions", 0))],
        ["Total Classes", str(parse_stats.get("classes", 0))],
    ]
    
    stats_table = Table(stats_data, colWidths=[2.5 * inch, 1.5 * inch])
    stats_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#4f46e5")),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor("#f3f4f6")),
        ('GRID', (0, 0), (-1, -1), 1, colors.white),
    ]))
    Story.append(stats_table)
    Story.append(Spacer(1, 0.5 * inch))

    # 4. Structural Graph Analysis
    Story.append(Paragraph("Structural Graph Analysis", h1_style))
    
    graph_data = [
        ["Analysis Area", "Metric", "Value"],
        ["Dependency Graph", "Modules (Nodes)", str(dependency_stats.get("nodes", 0))],
        ["", "Dependencies (Edges)", str(dependency_stats.get("edges", 0))],
        ["", "Circular Dependencies", str(dependency_stats.get("cycles", 0))],
        ["", "Dead Code Candidates", str(dependency_stats.get("tight_coupling", 0))],
        ["Call Graph", "Functions (Nodes)", str(call_stats.get("nodes", 0))],
        ["", "Call Edges", str(call_stats.get("edges", 0))],
        ["", "Orphaned Functions", str(call_stats.get("orphans", 0))],
    ]
    
    graph_table = Table(graph_data, colWidths=[1.5 * inch, 2.5 * inch, 1 * inch])
    graph_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#059669")),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor("#f0fdf4")),
        ('GRID', (0, 0), (-1, -1), 1, colors.white),
        # Merge cells for Analysis Area column to make it look clean
        ('SPAN', (0, 1), (0, 4)),
        ('SPAN', (0, 5), (0, 7)),
        ('VALIGN', (0, 1), (0, -1), 'MIDDLE'),
    ]))
    Story.append(graph_table)
    Story.append(Spacer(1, 0.5 * inch))

    # 5. Risk Assessment
    Story.append(PageBreak())
    Story.append(Paragraph("Risk Assessment", h1_style))
    
    if not risks:
        Story.append(Paragraph("No major risks detected by the analysis pipeline.", normal_style))
    else:
        # Tally severities
        severities = {"critical": 0, "high": 0, "medium": 0, "low": 0}
        for r in risks:
            sev = r.severity.lower()
            if sev in severities:
                severities[sev] += 1
                
        tally_text = (
            f"<b>Total Risks Detected: {len(risks)}</b><br/>"
            f"Critical: {severities['critical']} | "
            f"High: {severities['high']} | "
            f"Medium: {severities['medium']} | "
            f"Low: {severities['low']}"
        )
        Story.append(Paragraph(tally_text, normal_style))
        Story.append(Spacer(1, 0.2 * inch))
        
        # Only list Top 15 risks to avoid massive PDFs
        Story.append(Paragraph("Top Risk Findings:", h2_style))
        
        severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
        sorted_risks = sorted(risks, key=lambda r: severity_order.get(r.severity, 4))
        
        for idx, r in enumerate(sorted_risks[:15]):
            Story.append(Paragraph(f"<b>{idx+1}. [{r.severity.upper()}] {r.title}</b>", normal_style))
            Story.append(Paragraph(f"<i>Category: {r.category}</i>", normal_style))
            Story.append(Paragraph(f"Location: {r.file_path}:{r.line_number or 'N/A'}", code_style))
            Story.append(Paragraph(f"{r.description}", normal_style))
            if r.suggestion:
                Story.append(Paragraph(f"<b>Suggestion:</b> {r.suggestion}", normal_style))
            Story.append(Spacer(1, 0.15 * inch))
            
        if len(risks) > 15:
            Story.append(Paragraph(f"...and {len(risks) - 15} more findings omitted for brevity.", normal_style))

    # 6. Actionable Recommendations (from LLM)
    if llm_autopsy and llm_autopsy.get("actionable_recommendations"):
        Story.append(PageBreak())
        Story.append(Paragraph("Actionable Recommendations", h1_style))
        for rec in llm_autopsy["actionable_recommendations"]:
            Story.append(Paragraph(f"• {rec}", normal_style))
            Story.append(Spacer(1, 0.1 * inch))

    doc.build(Story)
    return buffer.getvalue()
