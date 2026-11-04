from io import BytesIO
from xml.sax.saxutils import escape

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer


def build_summary_pdf(report, advisor_questions):
    buffer = BytesIO()
    styles = getSampleStyleSheet()
    applicable = report["applicable"]
    unresolved = report["unresolved"]

    story = [
        Paragraph("CoverWise | SBI Demo Summary", styles["Title"]),
        Paragraph(escape(report["scenario"]), styles["Normal"]),
        Spacer(1, 12),
        Paragraph(
            f"{len(applicable)} applicable restrictions and "
            f"{len(unresolved)} rules needing review.",
            styles["Normal"],
        ),
    ]

    for rule in applicable + unresolved:
        label = rule.replace("_", " ").capitalize()
        status = (
            "Needs review" if rule in unresolved
            else "Applies in this scenario"
        )
        values = report["reviewed_values"].get(rule) or {}
        pages = values.get("source_pages", [])

        story.append(Paragraph(escape(label), styles["Heading2"]))
        story.append(Paragraph(status, styles["Normal"]))

        if pages:
            page_list = ", ".join(map(str, pages))
            story.append(Paragraph(f"SBI PDF pages {page_list}", styles["Normal"]))

        question = advisor_questions.get(rule)
        if question:
            story.append(Paragraph(escape(question), styles["Normal"]))

    SimpleDocTemplate(buffer, pagesize=A4).build(story)
    return buffer.getvalue()