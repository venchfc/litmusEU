import os

from fpdf import FPDF


def _format_score(value):
    return f"{value:.4f}"


def _ellipsize_to_width(pdf, text, max_width):
    if pdf.get_string_width(text) <= max_width:
        return text

    ellipsis = "..."
    if pdf.get_string_width(ellipsis) >= max_width:
        return ellipsis

    trimmed = text
    while trimmed and pdf.get_string_width(trimmed + ellipsis) > max_width:
        trimmed = trimmed[:-1]
    return trimmed + ellipsis


def _split_header_label(pdf, text, max_width):
    if pdf.get_string_width(text) <= max_width:
        return text, ""

    words = text.split()
    if len(words) <= 1:
        return _ellipsize_to_width(pdf, text, max_width), ""

    best_split = None
    best_width = None
    for index in range(1, len(words)):
        left = " ".join(words[:index])
        right = " ".join(words[index:])
        max_line = max(
            pdf.get_string_width(left),
            pdf.get_string_width(right),
        )
        if best_width is None or max_line < best_width:
            best_split = (left, right)
            best_width = max_line

    line_one, line_two = best_split
    line_one = _ellipsize_to_width(pdf, line_one, max_width)
    line_two = _ellipsize_to_width(pdf, line_two, max_width)
    return line_one, line_two


def _fit_header_font_size(pdf, labels, max_size, min_size):
    for size in range(max_size, min_size - 1, -1):
        pdf.set_font("Helvetica", style="B", size=size)
        fits = True
        for text, width in labels:
            line_one, line_two = _split_header_label(pdf, text, width)
            if pdf.get_string_width(line_one) > width:
                fits = False
                break
            if line_two and pdf.get_string_width(line_two) > width:
                fits = False
                break
        if fits:
            return size
    return min_size


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

    header_labels = [("Rank", rank_width), ("Contestant", contestant_width)]
    header_labels += [
        (f"{item.name} ({item.weight:.0f}%)", criteria_width)
        for item in criteria_items
    ]
    header_labels.append(("Total", total_width))
    header_font = _fit_header_font_size(
        pdf,
        header_labels,
        max_size=header_font,
        min_size=6,
    )

    pdf.set_font("Helvetica", style="B", size=header_font)
    header_row_height = row_height + 1

    pdf.cell(rank_width, header_row_height, "Rank", border="LTR", align="C")
    contestant_line_one, contestant_line_two = _split_header_label(
        pdf,
        "Contestant",
        contestant_width,
    )
    pdf.cell(
        contestant_width,
        header_row_height,
        contestant_line_one,
        border="LTR",
        align="C",
    )
    criteria_lines = []
    for item in criteria_items:
        label = f"{item.name} ({item.weight:.0f}%)"
        line_one, line_two = _split_header_label(pdf, label, criteria_width)
        criteria_lines.append((line_one, line_two))
        pdf.cell(
            criteria_width,
            header_row_height,
            line_one,
            border="LTR",
            align="C",
        )
    pdf.cell(total_width, header_row_height, "Total", border="LTR", align="C")
    pdf.ln()

    pdf.cell(rank_width, header_row_height, "", border="LRB", align="C")
    pdf.cell(
        contestant_width,
        header_row_height,
        contestant_line_two,
        border="LRB",
        align="C",
    )
    for line_one, line_two in criteria_lines:
        pdf.cell(
            criteria_width,
            header_row_height,
            line_two,
            border="LRB",
            align="C",
        )
    pdf.cell(total_width, header_row_height, "", border="LRB", align="C")
    pdf.ln()

    pdf.set_font("Helvetica", size=body_font)
    for index, row in enumerate(results, start=1):
        pdf.cell(rank_width, row_height, str(index), border=1, align="C")
        contestant_text = _ellipsize_to_width(
            pdf,
            row["contestant"],
            contestant_width,
        )
        pdf.cell(contestant_width, row_height, contestant_text, border=1)
        for item in criteria_items:
            weighted = row["criteria_totals"].get(item.id, 0)
            raw = row["criteria_raw_totals"].get(item.id, 0)
            score_text = f"{_format_score(weighted)}({_format_score(raw)})"
            pdf.cell(
                criteria_width,
                row_height,
                _ellipsize_to_width(pdf, score_text, criteria_width),
                border=1,
                align="C",
            )
        total_text = _ellipsize_to_width(
            pdf,
            _format_score(row["total"]),
            total_width,
        )
        pdf.cell(total_width, row_height, total_text, border=1, align="C")
        pdf.ln()

    pdf_bytes = pdf.output(dest="S")
    if isinstance(pdf_bytes, str):
        return pdf_bytes.encode("latin-1")
    return bytes(pdf_bytes)
