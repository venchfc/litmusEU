from fpdf import FPDF


def render_results_pdf(event, competition, results):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", style="B", size=14)
    pdf.cell(0, 10, "LITMUS Event Results", ln=True)

    pdf.set_font("Helvetica", size=11)
    pdf.cell(0, 8, f"Event: {event.name}", ln=True)
    pdf.cell(0, 8, f"Competition: {competition.name}", ln=True)
    pdf.ln(4)

    pdf.set_font("Helvetica", style="B", size=11)
    pdf.cell(100, 8, "Contestant")
    pdf.cell(40, 8, "Total", ln=True)

    pdf.set_font("Helvetica", size=11)
    for row in results:
        pdf.cell(100, 8, row["contestant"])
        pdf.cell(40, 8, f"{row['total']:.2f}", ln=True)

    return pdf.output(dest="S").encode("latin-1")
