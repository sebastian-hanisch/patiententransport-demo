"""PDF-Export des aktuellen Tages (fpdf2). Nur Kernschriften: kein Gedankenstrich, kein Euro-Zeichen, Umlaute sind erlaubt."""

from fpdf import FPDF

import ptd_constants as C


def _txt(s: str) -> str:
    """Kernschriften kennen kein Unicode-Sonderzeichen außerhalb von Latin-1; Markdown-Sterne entfernen."""
    return s.replace("**", "").replace("–", "-").replace("—", "-").replace("€", "EUR").replace("→", "->")


def _para(pdf, height, text):
    """Absatz über die volle Breite; der Cursor geht danach an den linken Rand (fpdf2 lässt ihn sonst rechts stehen)."""
    pdf.multi_cell(0, height, text, new_x="LMARGIN", new_y="NEXT")


def build_pdf(analysis, verdict_text: str) -> bytes:
    s = analysis.settings
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 15)
    _para(pdf, 8, _txt("Patiententransport: Zuweisungsregeln im Vergleich"))
    pdf.set_font("Helvetica", "", 10)
    pdf.ln(2)
    _para(pdf, 5, _txt(
        f"Szenario: {s.rate} neue Aufträge je Stunde im Mittel, {s.porters} Träger, {s.qual} % mit Bett-Qualifikation, "
        f"{s.breaks}, Sammelfenster {s.batch} min, Seed {s.seed}. {analysis.n_orders} Hinfahrten im Meldefenster 06:00 bis 18:00."))
    pdf.ln(3)
    pdf.set_font("Helvetica", "B", 10)
    _para(pdf, 5, "Kernfrage")
    pdf.set_font("Helvetica", "", 10)
    _para(pdf, 5, _txt(verdict_text))
    pdf.ln(3)
    widths = [38, 22, 30, 30, 30, 22]
    heads = ["Regel", "Ausl. %", "Notfall min (verf. %)", "dringend min (verf. %)", "Routine min (verf. %)", "Leerf. %"]
    pdf.set_font("Helvetica", "B", 8)
    for w, text in zip(widths, heads):
        pdf.cell(w, 6, text, border=1)
    pdf.ln()
    pdf.set_font("Helvetica", "", 8)
    for r in C.RULES:
        st = analysis.stats[r]
        cells = [C.RULE_NAME[r], f"{100 * st.utilization:.0f}"]
        for c in range(3):
            cells.append(f"{st.classes[c].mean:.1f} ({100 * st.classes[c].miss:.0f})")
        cells.append(f"{100 * st.empty_share:.0f}")
        for w, text in zip(widths, cells):
            pdf.cell(w, 6, _txt(text), border=1)
        pdf.ln()
    pdf.ln(3)
    pdf.set_font("Helvetica", "I", 8)
    _para(pdf, 4, _txt(
        "Soll bis zur Ankunft am Abholort: Notfall 10, dringend 20, Routine 40 min. Synthetisches Haus; alle Eingangszahlen sind "
        "Annahmen, keine Messung aus einem echten Betrieb. Quelle: sebastianhanisch.net"))
    return bytes(pdf.output())
