import os

from fpdf import FPDF


def _format_score(value):
    return f"{value:.4f}"


def render_results_pdf(event, competition, results, criteria_items):
    criteria_count = max(len(criteria_items), 1)
    orientation = "P"
    if criteria_count > 4 or len(results) > 15:
        orientation = "L"

    pdf = FPDF(orientation=orientation)
    pdf.set_auto_page_break(auto=True, margin=12)
    pdf.add_page()

    logo_path = os.path.join(
        os.path.dirname(__file__),
        "..",
        "static",
        "img",
        "MseufCatLogo.png",
    )
    logo_path = os.path.abspath(logo_path)
    if os.path.exists(logo_path):
        pdf.image(logo_path, x=12, y=10, w=20)

    pdf.set_text_color(128, 0, 32)
    pdf.set_font("Helvetica", style="B", size=11)
    pdf.cell(0, 6, "Manuel S. Enverga University Foundation - Catanauan Inc", ln=True, align="C")
    pdf.set_text_color(0, 0, 0)
    pdf.ln(2)

    pdf.set_font("Helvetica", style="B", size=14)
    pdf.cell(0, 10, "LITMUS", ln=True, align="C")
    pdf.set_font("Helvetica", style="B", size=12)
    pdf.cell(
        0,
        8,
        f"{competition.name} Competition Results",
        ln=True,
        align="C",
    )
    pdf.ln(6)

    page_width = pdf.w - pdf.l_margin - pdf.r_margin
    rank_width = 10
    contestant_width = 40
    total_width = 22
    remaining_width = page_width - rank_width - contestant_width - total_width
    criteria_width = max(18, remaining_width / criteria_count)

    body_font = 8
    if criteria_count > 6:
        body_font = 7
    if criteria_count > 8:
        body_font = 6
    if len(results) > 20:
        body_font = max(5, body_font - 1)
    header_font = min(10, body_font + 1)
    row_height = 6 if body_font <= 6 else 7

    pdf.set_font("Helvetica", style="B", size=header_font)
    pdf.cell(rank_width, row_height + 1, "Rank", border=1, align="C")
    pdf.cell(contestant_width, row_height + 1, "Contestant", border=1, align="C")
    for item in criteria_items:
        pdf.cell(
            criteria_width,
            row_height + 1,
            f"{item.name} ({item.weight:.0f}%)",
            border=1,
            align="C",
        )
    pdf.cell(total_width, row_height + 1, "Total", border=1, align="C")
    pdf.ln()

    pdf.set_font("Helvetica", size=body_font)
    for index, row in enumerate(results, start=1):
        pdf.cell(rank_width, row_height, str(index), border=1, align="C")
        pdf.cell(contestant_width, row_height, row["contestant"], border=1)
        for item in criteria_items:
            weighted = row["criteria_totals"].get(item.id, 0)
            raw = row["criteria_raw_totals"].get(item.id, 0)
            pdf.cell(
                criteria_width,
                row_height,
                f"{_format_score(weighted)}({_format_score(raw)})",
                border=1,
                align="C",
            )
        pdf.cell(total_width, row_height, _format_score(row["total"]), border=1, align="C")
        pdf.ln()

    pdf_bytes = pdf.output(dest="S")
    if isinstance(pdf_bytes, str):
        return pdf_bytes.encode("latin-1")
    return bytes(pdf_bytes)
