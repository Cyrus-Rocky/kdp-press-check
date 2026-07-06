"""Checks for manuscript formats with no fixed print page (.txt, .rtf, .odt):
document-type classification + content-quality checks only. Trim/margin/
bleed/font/image checks are skipped because these formats don't carry that
information — we say so explicitly instead of guessing.
"""
import classify
import content_quality
import formats
import frontmatter


def check_print_geometry_unavailable() -> dict:
    return {
        "title": "Print Geometry", "ok": True, "warning_only": True,
        "summary": "This file format doesn't carry page size, margins, or bleed information.",
        "fix": "We only checked writing/content issues below. For trim size, margins, "
               "and bleed, export this as a PDF (or open it in Word and save as .docx) "
               "and run that file through Press Check.",
        "detail": "Plain text, RTF, and ODT files have no fixed printed page to measure.",
    }


def run_all_checks_text_format(path: str, ext: str) -> dict:
    data = formats.extract(path, ext)
    full_text = data["full_text"]
    page_count = data["estimated_pages"]
    mono_ratio = 0.0
    landscape_ratio = 0.0

    classification = classify.classify(page_count, full_text, mono_ratio, landscape_ratio)
    ok = classification["kind"] == "book"
    doc_type_result = {"title": "Document Type", "ok": ok, "summary": classification["summary"]}
    if classification.get("fix"):
        doc_type_result["fix"] = classification["fix"]
    doc_type_result["detail"] = f"~{page_count} page(s) estimated from word count. " \
                                 f"Classified as: {classification['kind']}."

    results = [doc_type_result, check_print_geometry_unavailable()]
    results += content_quality.run(full_text, data.get("headings"))
    results.append(frontmatter.check_copyright_page(full_text))

    blocking_results = [r for r in results if not r.get("warning_only")]
    summary_ok = all(r["ok"] for r in blocking_results)
    issue_count = sum(1 for r in blocking_results if not r["ok"])
    advisory_issue_count = sum(1 for r in results if r.get("warning_only") and not r["ok"])

    return {
        "page_count": page_count,
        "page_count_is_estimate": True,
        "results": results,
        "overall_ok": summary_ok,
        "issue_count": issue_count,
        "advisory_issue_count": advisory_issue_count,
    }
