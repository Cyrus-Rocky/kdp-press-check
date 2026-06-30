"""Deterministic KDP paperback-interior compliance checks using PyMuPDF.

No network calls, no AI — every finding here is computed directly from
the PDF's own geometry, embedded fonts, and embedded images.

Each check returns:
  title    - short name shown as the row heading
  ok       - whether it passes
  warning_only - if True, this is a heads-up, not a blocker
  summary  - one plain-English sentence on the result
  fix      - what to actually do about it (omitted when ok and not warning_only)
  detail   - technical specifics, page-by-page, tucked behind a toggle in the UI
"""
import fitz  # PyMuPDF

import classify
import content_quality
import frontmatter
import kdp_rules as rules


def _full_text(doc) -> str:
    return "\n".join(page.get_text() for page in doc)


def _pt_to_in(pt: float) -> float:
    return pt / rules.POINTS_PER_INCH


def _page_range_label(pages: list) -> str:
    if len(pages) == 1:
        return f"page {pages[0]}"
    if len(pages) == 2:
        return f"pages {pages[0]} and {pages[1]}"
    return f"pages {pages[0]}, {pages[1]}, and {len(pages) - 2} more"


def check_content_type(doc) -> dict:
    page_count = doc.page_count
    full_text_parts = []
    mono_pages = 0
    landscape_pages = 0

    for page in doc:
        full_text_parts.append(page.get_text())
        if page.rect.width > page.rect.height:
            landscape_pages += 1
        fonts = page.get_fonts(full=True)
        if any("courier" in (f[3] or "").lower() or "mono" in (f[3] or "").lower()
               for f in fonts):
            mono_pages += 1

    full_text = "\n".join(full_text_parts)
    mono_ratio = mono_pages / page_count if page_count else 0
    landscape_ratio = landscape_pages / page_count if page_count else 0

    result = classify.classify(page_count, full_text, mono_ratio, landscape_ratio)
    ok = result["kind"] == "book"
    out = {"title": "Document Type", "ok": ok, "summary": result["summary"]}
    if result.get("fix"):
        out["fix"] = result["fix"]
    out["detail"] = (
        f"{page_count} page(s). Classified as: {result['kind']}."
    )
    return out


def check_trim_size(doc) -> dict:
    page = doc[0]
    w_in, h_in = _pt_to_in(page.rect.width), _pt_to_in(page.rect.height)
    match, dist = rules.closest_trim_size(w_in, h_in)
    ok = dist is not None and dist <= 0.1

    if ok:
        summary = f"Your pages are {w_in:.2f}\" x {h_in:.2f}\" — a standard KDP trim size."
        return {"title": "Trim Size", "ok": True, "summary": summary,
                "detail": f"Matches KDP's {match[0]}\" x {match[1]}\" trim size exactly."}

    summary = f"Your pages are {w_in:.2f}\" x {h_in:.2f}\", which isn't one of KDP's trim sizes."
    fix = (
        f"Resize every page to a standard size — the closest is {match[0]}\" x {match[1]}\". "
        f"In your word processor or design software, change the page/document size before "
        f"re-exporting the PDF, then upload it again."
    )
    return {
        "title": "Trim Size", "ok": False, "summary": summary, "fix": fix,
        "detail": f"Measured {w_in:.2f}\" x {h_in:.2f}\". Closest standard size: "
                  f"{match[0]}\" x {match[1]}\". KDP will reject non-standard trim sizes.",
    }


def check_page_size_consistency(doc) -> dict:
    sizes = {(round(p.rect.width, 1), round(p.rect.height, 1)) for p in doc}
    ok = len(sizes) == 1
    if ok:
        return {"title": "Page Size Consistency", "ok": True,
                "summary": "Every page is the same size.",
                "detail": "All pages are the same size."}
    return {
        "title": "Page Size Consistency", "ok": False,
        "summary": f"Found {len(sizes)} different page sizes — every page needs to match.",
        "fix": "Check your export settings for any page that was resized, rotated, or "
               "pasted in from a different document, and make it match the rest of the book.",
        "detail": f"Found {len(sizes)} distinct page sizes in this document.",
    }


def _content_bbox(page):
    rect = page.rect
    blocks = page.get_text("blocks")
    images = page.get_image_info()
    boxes = [b[:4] for b in blocks if b[4].strip()] if blocks else []
    boxes += [im["bbox"] for im in images]
    if not boxes:
        return None
    x0 = min(b[0] for b in boxes)
    y0 = min(b[1] for b in boxes)
    x1 = max(b[2] for b in boxes)
    y1 = max(b[3] for b in boxes)
    return (x0, y0, x1, y1), rect


def check_margins(doc) -> dict:
    page_count = doc.page_count
    required_inside = rules.inside_margin_in(page_count)
    required_outer = rules.MIN_OUTSIDE_TOP_BOTTOM_MARGIN_IN
    tol = rules.TOLERANCE_IN

    violation_pages = []
    violation_lines = []
    checked_pages = 0
    tightest = None  # (margin_in, required_in, page_num, side)

    for i, page in enumerate(doc):
        result = _content_bbox(page)
        if result is None:
            continue
        (x0, y0, x1, y1), rect = result
        checked_pages += 1

        left_in = _pt_to_in(x0)
        right_in = _pt_to_in(rect.width - x1)
        top_in = _pt_to_in(y0)
        bottom_in = _pt_to_in(rect.height - y1)

        page_num = i + 1
        is_odd = page_num % 2 == 1
        inside_margin = left_in if is_odd else right_in
        outside_margin = right_in if is_odd else left_in

        checks = [
            (inside_margin, required_inside, "inside"),
            (outside_margin, required_outer, "outside"),
            (top_in, required_outer, "top"),
            (bottom_in, required_outer, "bottom"),
        ]
        page_failed = False
        for margin_val, required_val, side in checks:
            if margin_val < required_val - tol:
                page_failed = True
                violation_lines.append(
                    f"Page {page_num}: {side} margin {margin_val:.2f}\" "
                    f"(needs {required_val:.2f}\")"
                )
                shortfall = required_val - margin_val
                if tightest is None or shortfall > tightest[0]:
                    tightest = (shortfall, margin_val, required_val, page_num, side)
        if page_failed:
            violation_pages.append(page_num)

    ok = len(violation_pages) == 0
    if ok:
        return {
            "title": "Margins", "ok": True,
            "summary": f"All {checked_pages} pages meet KDP's minimum margins.",
            "detail": f"Inside margin minimum {required_inside:.2f}\", outside/top/bottom "
                      f"minimum {required_outer:.2f}\" — every page clears both.",
        }

    _, margin_val, required_val, page_num, side = tightest
    summary = (
        f"{len(violation_pages)} of {checked_pages} pages have text or images too close "
        f"to the edge. Tightest: page {page_num}'s {side} margin is {margin_val:.2f}\" "
        f"(needs {required_val:.2f}\")."
    )
    fix = (
        f"In your document's page setup, increase margins so the inside (binding-side) "
        f"margin is at least {required_inside:.2f}\" and the outside, top, and bottom margins "
        f"are at least {required_outer:.2f}\". Re-export the PDF and upload again. "
        f"Affects {_page_range_label(violation_pages)}."
    )
    return {
        "title": "Margins", "ok": False, "summary": summary, "fix": fix,
        "detail": "\n".join(violation_lines[:10])
                  + (f"\n…and {len(violation_lines) - 10} more." if len(violation_lines) > 10 else ""),
    }


def _pages_with_edge_touching_images(doc, tol_in=rules.EDGE_TOUCH_TOLERANCE_IN):
    tol_pt = tol_in * rules.POINTS_PER_INCH
    pages = []
    for i, page in enumerate(doc):
        rect = page.rect
        for img in page.get_image_info():
            x0, y0, x1, y1 = img["bbox"]
            touches = (
                x0 <= tol_pt or y0 <= tol_pt
                or x1 >= rect.width - tol_pt or y1 >= rect.height - tol_pt
            )
            if touches:
                pages.append(i + 1)
                break
    return pages


def check_bleed(doc) -> dict:
    page = doc[0]
    w_in, h_in = _pt_to_in(page.rect.width), _pt_to_in(page.rect.height)

    plain_match, plain_dist = rules.closest_trim_size(w_in, h_in)
    unbled_match, unbled_dist = rules.closest_trim_size(
        w_in - rules.BLEED_WIDTH_ADD_IN, h_in - rules.BLEED_HEIGHT_ADD_IN
    )
    sized_for_bleed = unbled_dist <= rules.TOLERANCE_IN and unbled_dist < plain_dist

    bleed_pages = _pages_with_edge_touching_images(doc)
    has_bleed_content = len(bleed_pages) > 0

    if has_bleed_content and not sized_for_bleed:
        target_w = plain_match[0] + rules.BLEED_WIDTH_ADD_IN
        target_h = plain_match[1] + rules.BLEED_HEIGHT_ADD_IN
        return {
            "title": "Bleed", "ok": False, "warning_only": False,
            "summary": f"Images on {_page_range_label(bleed_pages)} run to the page edge, "
                       f"but the page wasn't enlarged for bleed.",
            "fix": f"Either pull those images back so they stay inside the margins, or "
                   f"resize every page to {target_w:.2f}\" x {target_h:.2f}\" "
                   f"({rules.BLEED_WIDTH_ADD_IN}\" extra on the outer edge, "
                   f"{rules.BLEED_HEIGHT_ADD_IN}\" extra split between top and bottom) "
                   f"and re-position the bleeding images to fill the new page size.",
            "detail": f"Page size is {w_in:.2f}\" x {h_in:.2f}\" (plain trim). "
                      f"{len(bleed_pages)} page(s) have an image touching the page edge.",
        }
    if has_bleed_content and sized_for_bleed:
        return {
            "title": "Bleed", "ok": True, "warning_only": False,
            "summary": f"Page size is correctly enlarged for the full-bleed images on "
                       f"{_page_range_label(bleed_pages)}.",
            "detail": f"Page size {w_in:.2f}\" x {h_in:.2f}\" matches trim + bleed.",
        }
    if sized_for_bleed and not has_bleed_content:
        return {
            "title": "Bleed", "ok": True, "warning_only": True,
            "summary": "Page size is set up for bleed, but no image actually reaches the edge.",
            "fix": f"If nothing in your book is meant to bleed off the page, you can switch "
                   f"back to the plain trim size ({plain_match[0]}\" x {plain_match[1]}\") — "
                   f"not required, just simpler.",
            "detail": f"Page size {w_in:.2f}\" x {h_in:.2f}\" matches a bleed size, "
                      f"but no images touch the page edge.",
        }
    return {
        "title": "Bleed", "ok": True, "warning_only": False,
        "summary": "No bleed in use — page size and image placement are consistent with that.",
        "detail": "No images extend to the page edge, and the page matches the plain trim size.",
    }


def check_fonts(doc) -> dict:
    not_embedded = set()
    for page in doc:
        for font in page.get_fonts(full=True):
            basefont = font[3]
            ext = font[1]
            is_embedded = ext != "n/a"
            if not is_embedded:
                not_embedded.add(basefont)

    if not not_embedded:
        return {"title": "Font Embedding", "ok": True,
                "summary": "Every font used in the document is embedded.",
                "detail": "All fonts used in the document are embedded."}

    names = ", ".join(sorted(not_embedded))
    return {
        "title": "Font Embedding", "ok": False,
        "summary": f"{len(not_embedded)} font(s) aren't embedded: {names}.",
        "fix": "When exporting your PDF, turn on font embedding (in Word: File > Save As > "
               "More options > Tools > Save Options > check \"Embed fonts in the file\"; in "
               "InDesign or similar: enable subset/embed fonts on export). Without this, KDP's "
               "printer may substitute a different font and your layout will shift.",
        "detail": "Fonts not embedded: " + names,
    }


def check_image_resolution(doc) -> dict:
    low_res_pages = []
    low_res_lines = []
    checked = 0
    worst = None  # (dpi, page_num)

    for i, page in enumerate(doc):
        for img in page.get_image_info(xrefs=True):
            xref = img.get("xref")
            if not xref:
                continue
            bbox = img["bbox"]
            disp_w_in = _pt_to_in(bbox[2] - bbox[0])
            disp_h_in = _pt_to_in(bbox[3] - bbox[1])
            if disp_w_in <= 0 or disp_h_in <= 0:
                continue
            try:
                pix_w, pix_h = img["width"], img["height"]
            except KeyError:
                continue
            checked += 1
            effective_dpi = min(pix_w / disp_w_in, pix_h / disp_h_in)
            if effective_dpi < rules.MIN_IMAGE_DPI:
                page_num = i + 1
                if page_num not in low_res_pages:
                    low_res_pages.append(page_num)
                low_res_lines.append(
                    f"Page {page_num}: {effective_dpi:.0f} DPI "
                    f"(needs {rules.MIN_IMAGE_DPI}+)"
                )
                if worst is None or effective_dpi < worst[0]:
                    worst = (effective_dpi, page_num)

    if checked == 0:
        return {"title": "Image Resolution", "ok": True,
                "summary": "No images in this document to check.",
                "detail": "No raster images found in the document."}
    if not low_res_lines:
        return {
            "title": "Image Resolution", "ok": True,
            "summary": f"All {checked} image(s) are sharp enough to print ({rules.MIN_IMAGE_DPI}+ DPI).",
            "detail": f"All {checked} image placement(s) meet the {rules.MIN_IMAGE_DPI} DPI minimum.",
        }

    worst_dpi, worst_page = worst
    summary = (
        f"{len(low_res_lines)} image(s) across {_page_range_label(low_res_pages)} will print "
        f"blurry — the lowest is {worst_dpi:.0f} DPI on page {worst_page} (needs "
        f"{rules.MIN_IMAGE_DPI}+)."
    )
    fix = (
        f"These images are stretched larger than their source file supports. Replace each "
        f"one with its original high-resolution file (or re-export/re-scan it at "
        f"{rules.MIN_IMAGE_DPI} DPI or higher at the size you're displaying it), then "
        f"re-insert it at the same size on the page."
    )
    return {
        "title": "Image Resolution", "ok": False, "summary": summary, "fix": fix,
        "detail": "\n".join(low_res_lines[:10])
                  + (f"\n…and {len(low_res_lines) - 10} more." if len(low_res_lines) > 10 else ""),
    }


def check_metadata(doc) -> dict:
    meta = doc.metadata or {}
    title = (meta.get("title") or "").strip()
    if title:
        return {"title": "Metadata", "ok": True, "warning_only": True,
                "summary": f"Document title is set to \"{title}\".",
                "detail": f"Document title metadata is set: \"{title}\"."}
    return {
        "title": "Metadata", "ok": False, "warning_only": True,
        "summary": "The PDF's title field is empty.",
        "fix": "Not required by KDP, but worth doing: set the document title in your "
               "export settings (or File > Properties) to match your book's title.",
        "detail": "Document title metadata is empty.",
    }


def run_all_checks(pdf_path: str) -> dict:
    doc = fitz.open(pdf_path)
    try:
        results = [
            check_content_type(doc),
            check_trim_size(doc),
            check_page_size_consistency(doc),
            check_margins(doc),
            check_bleed(doc),
            check_fonts(doc),
            check_image_resolution(doc),
            check_metadata(doc),
        ]
        full_text = _full_text(doc)
        results += content_quality.run(full_text)
        doc_title = (doc.metadata or {}).get("title") or None
        first_page_text = doc[0].get_text() if doc.page_count > 0 else ""
        results += frontmatter.run(full_text, first_page_text, doc_title)
        blocking_results = [r for r in results if not r.get("warning_only")]
        summary_ok = all(r["ok"] for r in blocking_results)
        issue_count = sum(1 for r in blocking_results if not r["ok"])
        return {
            "page_count": doc.page_count,
            "results": results,
            "overall_ok": summary_ok,
            "issue_count": issue_count,
        }
    finally:
        doc.close()
