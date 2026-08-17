"""Front-matter and back-matter completeness checklist.

Missing front/back matter doesn't get a book rejected by KDP, but it's
the kind of thing an author misses on every read-through because their
eye is on the story, not the boilerplate. This returns a checklist so
users can see at a glance what they have and what's intentionally missing.
"""
import re

_COPYRIGHT_PATTERN = re.compile(
    r"(copyright|©|all rights reserved|isbn|library of congress|"
    r"first edition|printed in the)",
    re.IGNORECASE,
)

_AUTHOR_BIO_PATTERN = re.compile(
    r"(about the author|author bio|biography|about\s+\w+)",
    re.IGNORECASE,
)

_TOC_PATTERN = re.compile(
    r"(table of contents|contents|toc|chapter \d+)",
    re.IGNORECASE,
)

_DEDICATION_PATTERN = re.compile(
    r"(dedication|dedicated to)",
    re.IGNORECASE,
)


def _first_n_words(text: str, n: int) -> str:
    return " ".join(text.split()[:n])


def _check_item(full_text: str, pattern: re.Pattern, scan_words: int = 2000) -> bool:
    """Check if a pattern exists in the early part of the text."""
    early_text = _first_n_words(full_text, scan_words)
    return bool(pattern.search(early_text))


def check_frontmatter_checklist(full_text: str, first_page_text: str = None, doc_title: str = None) -> dict:
    """Return a checklist of common front-matter items with presence status."""
    scan_words = 3000

    # Check each item
    has_title_page = False
    if first_page_text:
        words = first_page_text.split()
        word_count = len(words)
        has_title_page = 0 < word_count <= 50

    has_copyright = _check_item(full_text, _COPYRIGHT_PATTERN, scan_words)
    has_dedication = _check_item(full_text, _DEDICATION_PATTERN, scan_words)
    has_toc = _check_item(full_text, _TOC_PATTERN, scan_words)
    has_author_bio = _check_item(full_text, _AUTHOR_BIO_PATTERN, scan_words)

    # Build checklist
    checklist = [
        {"item": "Title Page", "present": has_title_page, "description": "Book title and author name"},
        {"item": "Copyright Page", "present": has_copyright, "description": "Copyright notice and ISBN (if applicable)"},
        {"item": "Dedication", "present": has_dedication, "description": "Optional dedication page"},
        {"item": "Table of Contents", "present": has_toc, "description": "Chapter list with page numbers"},
        {"item": "Author Bio", "present": has_author_bio, "description": "About the author section"},
    ]

    missing_count = sum(1 for item in checklist if not item["present"])
    present_count = sum(1 for item in checklist if item["present"])

    if missing_count == 0:
        summary = f"Front-matter complete. All {present_count} key items detected."
        return {
            "title": "Front-Matter Checklist",
            "ok": True,
            "warning_only": True,
            "summary": summary,
            "checklist": checklist,
            "detail": "All common front-matter items are present.",
        }

    missing_items = [item["item"] for item in checklist if not item["present"]]
    summary = f"Missing {missing_count} front-matter item(s): {', '.join(missing_items[:3])}"
    if missing_count > 3:
        summary += f" and {missing_count - 3} more."

    return {
        "title": "Front-Matter Checklist",
        "ok": False,
        "warning_only": True,
        "summary": summary,
        "checklist": checklist,
        "fix": "Review the missing items above. KDP doesn't require these, but professional "
               "books typically include them. Click 'Are these intentional?' below to confirm, "
               "or add them if you'd like your book to look polished.",
        "detail": f"Front-matter items present: {present_count}/5. Missing: {missing_count}/5.",
    }


def check_backmatter_checklist(full_text: str) -> dict:
    """Check for common back-matter items (appendix, author bio, etc.)."""
    scan_words = 3000
    late_text = " ".join(full_text.split()[-scan_words:])

    has_author_bio = bool(_AUTHOR_BIO_PATTERN.search(late_text))
    has_appendix = bool(re.search(r"(appendix|appendices)", late_text, re.IGNORECASE))
    has_acknowledgments = bool(re.search(r"(acknowledgments|thanks|acknowledgements)", late_text, re.IGNORECASE))

    checklist = [
        {"item": "Author Bio", "present": has_author_bio, "description": "Information about the author"},
        {"item": "Acknowledgments", "present": has_acknowledgments, "description": "Thank you section"},
        {"item": "Appendix", "present": has_appendix, "description": "Extra materials or references"},
    ]

    present_count = sum(1 for item in checklist if item["present"])

    if present_count > 0:
        return {
            "title": "Back-Matter Checklist",
            "ok": True,
            "warning_only": True,
            "summary": f"Found {present_count} back-matter item(s).",
            "checklist": checklist,
            "detail": "Back-matter items detected at the end of the manuscript.",
        }

    return {
        "title": "Back-Matter Checklist",
        "ok": False,
        "warning_only": True,
        "summary": "No back-matter items detected (all optional).",
        "checklist": checklist,
        "fix": "Back-matter is optional, but adding an author bio helps readers connect with you. "
               "Consider adding at minimum a short bio (100-150 words) about yourself.",
        "detail": "No author bio, acknowledgments, or appendix were found.",
    }


def run(full_text: str, first_page_text: str = None, doc_title: str = None) -> list:
    """Returns front-matter and back-matter checklist checks."""
    results = [
        check_frontmatter_checklist(full_text, first_page_text, doc_title),
        check_backmatter_checklist(full_text),
    ]
    return results
