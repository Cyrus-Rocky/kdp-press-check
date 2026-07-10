"""KDP paperback cover compliance checks using PyMuPDF.

Unlike the interior checker, a cover file can't tell us its own page count or
paper stock — those come from the interior file and the author's printing
choice, so the cover-check form collects trim size, page count, and paper
type up front and we calculate the expected cover geometry from KDP's
published spine-width formula.

Font embedding, image resolution, and metadata checks are identical to the
interior checks, so they're reused directly from checker.py rather than
duplicated here.
"""
import fitz  # PyMuPDF

import kdp_rules as rules
from checker import check_fonts, check_image_resolution, check_metadata, _pt_to_in


def check_cover_dimensions(doc, trim_w_in, trim_h_in, page_count, paper_type) -> dict:
    page = doc[0]
    w_in, h_in = _pt_to_in(page.rect.width), _pt_to_in(page.rect.height)
    exp_w, exp_h, spine_w = rules.cover_dimensions_in(
        trim_w_in, trim_h_in, page_count, paper_type
    )
    tol = rules.TOLERANCE_IN
    ok = abs(w_in - exp_w) <= tol and abs(h_in - exp_h) <= tol

    paper_label = rules.PAPER_TYPE_LABELS[paper_type]
    if ok:
        return {
            "title": "Cover Dimensions", "ok": True,
            "summary": f"Cover is {w_in:.2f}\" x {h_in:.2f}\" — correct for a "
                       f"{trim_w_in}\" x {trim_h_in}\" book, {page_count} pages on "
                       f"{paper_label} (spine {spine_w:.3f}\").",
            "detail": f"Measured {w_in:.2f}\" x {h_in:.2f}\". Expected {exp_w:.2f}\" x "
                      f"{exp_h:.2f}\" (spine width {spine_w:.3f}\", bleed "
                      f"{rules.COVER_BLEED_IN}\" on all sides).",
        }
    return {
        "title": "Cover Dimensions", "ok": False,
        "summary": f"Cover is {w_in:.2f}\" x {h_in:.2f}\", but needs to be "
                   f"{exp_w:.2f}\" x {exp_h:.2f}\" for these book specs.",
        "fix": f"Resize the full wraparound cover (back cover + spine + front cover, "
               f"with {rules.COVER_BLEED_IN}\" bleed on all four outer edges) to exactly "
               f"{exp_w:.2f}\" x {exp_h:.2f}\". For a {trim_w_in}\" x {trim_h_in}\" book "
               f"at {page_count} pages on {paper_label}, the calculated spine width is "
               f"{spine_w:.3f}\". Use KDP's own cover calculator to double-check this "
               f"number before your final export.",
        "detail": f"Measured {w_in:.2f}\" x {h_in:.2f}\". Expected {exp_w:.2f}\" x {exp_h:.2f}\".",
    }


def _panel_bounds_pt(trim_w_in, trim_h_in, page_count, paper_type):
    """Returns x-coordinates (in points) of the back/spine/front panel edges,
    assuming the standard KDP layout: back cover, spine, front cover, left to right."""
    bleed = rules.COVER_BLEED_IN
    spine_w = rules.cover_spine_width_in(page_count, paper_type)
    back_x0 = 0.0
    back_x1 = bleed + trim_w_in
    spine_x0 = back_x1
    spine_x1 = spine_x0 + spine_w
    front_x1 = spine_x1 + trim_w_in + bleed
    to_pt = rules.POINTS_PER_INCH
    return {
        "spine_w_in": spine_w,
        "back": (back_x0 * to_pt, back_x1 * to_pt),
        "spine": (spine_x0 * to_pt, spine_x1 * to_pt),
        "front": (spine_x1 * to_pt, front_x1 * to_pt),
    }


def check_spine_text_safety(doc, trim_w_in, trim_h_in, page_count, paper_type) -> dict:
    bounds = _panel_bounds_pt(trim_w_in, trim_h_in, page_count, paper_type)
    spine_w_in = bounds["spine_w_in"]
    sx0, sx1 = bounds["spine"]

    if spine_w_in >= rules.MIN_SPINE_WIDTH_FOR_TEXT_IN:
        return {
            "title": "Spine Text", "ok": True,
            "summary": f"Spine is {spine_w_in:.3f}\" wide — wide enough for readable "
                       f"title/author text.",
            "detail": f"Spine width {spine_w_in:.3f}\" >= the "
                      f"{rules.MIN_SPINE_WIDTH_FOR_TEXT_IN}\" usually needed for legible text.",
        }

    text_on_spine = False
    for page in doc:
        for block in page.get_text("blocks"):
            x0, y0, x1, y1, text = block[0], block[1], block[2], block[3], block[4]
            if text.strip() and not (x1 <= sx0 or x0 >= sx1):
                text_on_spine = True
                break
        if text_on_spine:
            break

    if text_on_spine:
        return {
            "title": "Spine Text", "ok": False, "warning_only": True,
            "summary": f"The spine is only {spine_w_in:.3f}\" wide — too narrow for text "
                       f"to print legibly — but text was found positioned there.",
            "fix": f"Books need roughly {rules.MIN_PAGES_FOR_SPINE_TEXT}+ pages before the "
                   f"spine is wide enough for readable text. At {page_count} pages, remove "
                   f"any title or author text from the spine area, or it likely won't be "
                   f"legible on the printed book.",
            "detail": f"Spine width {spine_w_in:.3f}\". Text detected overlapping the "
                      f"spine x-range.",
        }
    return {
        "title": "Spine Text", "ok": True,
        "summary": f"Spine is {spine_w_in:.3f}\" wide (too narrow for legible text), and "
                   f"none was placed there — fine.",
        "detail": f"Spine width {spine_w_in:.3f}\". No text found in the spine x-range.",
    }


def check_barcode_zone(doc, trim_w_in, trim_h_in, page_count, paper_type) -> dict:
    bleed = rules.COVER_BLEED_IN
    page = doc[0]
    page_h_in = _pt_to_in(page.rect.height)

    back_x1_in = bleed + trim_w_in
    barcode_x1_in = back_x1_in - rules.BARCODE_MARGIN_IN
    barcode_x0_in = barcode_x1_in - rules.BARCODE_WIDTH_IN
    barcode_y1_in = page_h_in - bleed - rules.BARCODE_MARGIN_IN
    barcode_y0_in = barcode_y1_in - rules.BARCODE_HEIGHT_IN

    to_pt = rules.POINTS_PER_INCH
    bx0, by0, bx1, by1 = (barcode_x0_in * to_pt, barcode_y0_in * to_pt,
                          barcode_x1_in * to_pt, barcode_y1_in * to_pt)

    overlapping_pages = []
    for i, p in enumerate(doc):
        for block in p.get_text("blocks"):
            x0, y0, x1, y1, text = block[0], block[1], block[2], block[3], block[4]
            if text.strip() and not (x1 <= bx0 or x0 >= bx1 or y1 <= by0 or y0 >= by1):
                overlapping_pages.append(i + 1)
                break

    if overlapping_pages:
        return {
            "title": "Barcode Area", "ok": False,
            "summary": "Text was found in the bottom-right area of the back cover where "
                       "KDP places the barcode — it will be covered up.",
            "fix": f"Move any text out of the bottom-right "
                   f"{rules.BARCODE_WIDTH_IN}\" x {rules.BARCODE_HEIGHT_IN}\" corner of "
                   f"the back cover (inset {rules.BARCODE_MARGIN_IN}\" from the trim edges). "
                   f"Background art can run underneath the barcode safely — only text or "
                   f"essential graphics there are a problem.",
            "detail": f"Barcode zone approx {rules.BARCODE_WIDTH_IN}\" x "
                      f"{rules.BARCODE_HEIGHT_IN}\", inset {rules.BARCODE_MARGIN_IN}\" "
                      f"from the back cover's trim edges. Text overlap detected.",
        }
    return {
        "title": "Barcode Area", "ok": True,
        "summary": "Nothing essential sits in KDP's barcode placement zone on the back cover.",
        "detail": f"No text found overlapping the approximate "
                  f"{rules.BARCODE_WIDTH_IN}\" x {rules.BARCODE_HEIGHT_IN}\" barcode zone.",
    }


def run_all_cover_checks(pdf_path: str, trim_w_in: float, trim_h_in: float,
                          page_count: int, paper_type: str) -> dict:
    doc = fitz.open(pdf_path)
    try:
        results = [
            check_cover_dimensions(doc, trim_w_in, trim_h_in, page_count, paper_type),
            check_spine_text_safety(doc, trim_w_in, trim_h_in, page_count, paper_type),
            check_barcode_zone(doc, trim_w_in, trim_h_in, page_count, paper_type),
            check_fonts(doc),
            check_image_resolution(doc),
            check_metadata(doc),
        ]
        blocking_results = [r for r in results if not r.get("warning_only")]
        summary_ok = all(r["ok"] for r in blocking_results)
        issue_count = sum(1 for r in blocking_results if not r["ok"])
        advisory_issue_count = sum(1 for r in results if r.get("warning_only") and not r["ok"])
        note_count = sum(1 for r in results if r.get("warning_only") and r["ok"])
        ok_count = sum(1 for r in results if not r.get("warning_only") and r["ok"])
        return {
            "subtitle": f"{trim_w_in}\" x {trim_h_in}\" cover · {page_count} pages · "
                        f"{rules.PAPER_TYPE_LABELS[paper_type]}",
            "results": results,
            "overall_ok": summary_ok,
            "issue_count": issue_count,
            "advisory_issue_count": advisory_issue_count,
            "note_count": note_count,
            "ok_count": ok_count,
        }
    finally:
        doc.close()
