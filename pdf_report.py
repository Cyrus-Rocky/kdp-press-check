"""Branded PDF report generation (Pro).

Turns a check report dict (the same structure result.html renders) into a
clean, branded PDF an author can save, print, or hand to a formatter or
cover designer as proof of what needs fixing. Built with PyMuPDF (already a
dependency for PDF rendering elsewhere in this app), no extra library needed.
"""
import io

import fitz

PAGE_W, PAGE_H = 612, 792  # US Letter, points
MARGIN = 48
CORAL = (1.0, 0x77 / 255, 0x59 / 255)
INK = (0.11, 0.11, 0.13)
MUTED = (0.42, 0.42, 0.46)
OK_GREEN = (0.05, 0.48, 0.35)
ISSUE_RED = (0.74, 0.31, 0.18)


def _new_page(doc):
    return doc.new_page(width=PAGE_W, height=PAGE_H)


def _header(page, title_text: str):
    page.draw_rect(fitz.Rect(0, 0, PAGE_W, 6), color=None, fill=CORAL)
    page.insert_text((MARGIN, 44), "KDP PRESS CHECK", fontsize=10, color=MUTED,
                      fontname="Helvetica-Bold")
    page.insert_text((MARGIN, 74), title_text, fontsize=20, color=INK,
                      fontname="Helvetica-Bold")


def _footer(page, site_url: str, page_num: int, page_count: int):
    y = PAGE_H - 34
    page.draw_line((MARGIN, y - 10), (PAGE_W - MARGIN, y - 10), color=(0.85, 0.83, 0.8), width=0.6)
    page.insert_text((MARGIN, y), site_url or "kdp press check", fontsize=8, color=MUTED)
    page.insert_text((PAGE_W - MARGIN - 60, y), f"Page {page_num} of {page_count}", fontsize=8, color=MUTED)


def build_report_pdf(report: dict, filename: str, mode_label: str, site_url: str = "") -> bytes:
    doc = fitz.open()
    page = _new_page(doc)
    _header(page, "Interior Check Report" if mode_label == "interior" else f"{mode_label.title()} Check Report")

    y = 110
    page.insert_text((MARGIN, y), f"File: {filename}", fontsize=11, color=INK)
    y += 18
    import datetime
    page.insert_text((MARGIN, y), "Generated: " + datetime.date.today().strftime("%B %d, %Y"), fontsize=10, color=MUTED)
    y += 30

    readiness = report.get("readiness_pct")
    overall_ok = report.get("overall_ok")
    stamp_text = "PASS" if overall_ok else "NEEDS FIXES"
    stamp_color = OK_GREEN if overall_ok else ISSUE_RED
    if readiness is not None:
        page.insert_text((MARGIN, y), f"{readiness}% ready to publish", fontsize=16, color=stamp_color,
                          fontname="Helvetica-Bold")
        y += 22
    page.insert_text((MARGIN, y), stamp_text, fontsize=11, color=stamp_color, fontname="Helvetica-Bold")
    y += 26

    results = report.get("results", [])
    page.insert_text((MARGIN, y), f"{len(results)} check(s) run", fontsize=10, color=MUTED)
    y += 24

    page_count_estimate = 1
    for r in results:
        if r.get("warning_only") and not r.get("ok"):
            state, label, color = "issue", "ISSUE", ISSUE_RED
        elif r.get("warning_only"):
            state, label, color = "note", "NOTE", MUTED
        elif r.get("ok"):
            state, label, color = "ok", "OK", OK_GREEN
        else:
            state, label, color = "fail", "FAIL", ISSUE_RED

        block_height = 20
        summary = r.get("summary", "")
        wrapped = _wrap(summary, 88)
        block_height += 13 * len(wrapped)

        if y + block_height > PAGE_H - 70:
            page_count_estimate += 1
            page = _new_page(doc)
            y = 60

        page.insert_text((MARGIN, y), f"[{label}]", fontsize=9, color=color, fontname="Helvetica-Bold")
        page.insert_text((MARGIN + 55, y), r.get("title", ""), fontsize=11, color=INK, fontname="Helvetica-Bold")
        y += 15
        for line in wrapped:
            page.insert_text((MARGIN + 55, y), line, fontsize=9.5, color=MUTED)
            y += 13
        y += 10

    total_pages = len(doc)
    for i, p in enumerate(doc, start=1):
        _footer(p, site_url, i, total_pages)

    buf = io.BytesIO()
    doc.save(buf)
    doc.close()
    return buf.getvalue()


def _wrap(text: str, width: int):
    words = text.split()
    lines, current = [], ""
    for w in words:
        candidate = (current + " " + w).strip()
        if len(candidate) > width:
            if current:
                lines.append(current)
            current = w
        else:
            current = candidate
    if current:
        lines.append(current)
    return lines or [""]
