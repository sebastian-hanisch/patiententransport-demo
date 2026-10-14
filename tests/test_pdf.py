"""PDF-Export: erzeugt für jedes Preset ein gültiges Dokument (fpdf2-Kernschriften, kein Sonderzeichen-Absturz)."""

import ptd_constants as C
import ptd_evaluation as ev
from ptd_pdf_export import build_pdf


def test_pdf_is_built_for_every_preset():
    for name, preset in C.PRESETS.items():
        a = ev.analyse(ev.Settings(**preset))
        data = build_pdf(a, ev.verdict_core(a)[1])
        assert data.startswith(b"%PDF-") and len(data) > 1500, name


def test_pdf_text_helper_removes_characters_the_core_fonts_cannot_draw():
    from ptd_pdf_export import _txt

    assert _txt("**fett** – 5 € →") == "fett - 5 EUR ->"
