"""Front-matter checks: does the manuscript have a copyright page and a
title page? Missing front matter doesn't get a book rejected by KDP, but
it's the kind of thing an author misses on every read-through because
their eye is on the story, not the boilerplate, exactly the blind-spot
class of problem this tool exists to catch.

These are heuristics, not hard rules, so every result here is phrased as
an observation and is always non-blocking (warning_only).
"""
import re

_COPYRIGHT_PATTERN = re.compile(
    r"(copyright|©|all rights reserved|isbn|library of congress|"
    r"first edition|printed in the)",
    re.IGNORECASE,
)


def _first_n_words(text: str, n: int) -> str:
    return " ".join(text.split()[:n])


def check_copyright_page(full_text: str, scan_words: int = 1500) -> dict:
    early_text = _first_n_words(full_text, scan_words)
    found = bool(_COPYRIGHT_PATTERN.search(early_text))
    if found:
        return {
            "title": "Copyright Page", "ok": True, "warning_only": True,
            "summary": "Found copyright/rights language near the front of the manuscript.",
            "detail": "Matched a copyright marker (e.g. \"Copyright\", \"©\", \"All rights "
                      "reserved\", \"ISBN\") within the first part of the document.",
        }
    return {
        "title": "Copyright Page", "ok": False, "warning_only": True,
        "summary": "No copyright page was detected near the front of the manuscript.",
        "fix": "This is easy to forget since it's boilerplate, not story, add a copyright "
               "page near the front with at minimum \"Copyright © [year] [your name]. All "
               "rights reserved.\" KDP doesn't require it, but readers and reviewers expect "
               "it, and it's your basic proof of authorship.",
        "detail": "No copyright/rights language found in the scanned portion of the document. "
                  "This is a heuristic, unusual copyright wording could be missed.",
    }


def check_title_page(first_page_text: str, doc_title: str = None) -> dict:
    words = first_page_text.split()
    word_count = len(words)
    sparse = 0 < word_count <= 50

    if sparse:
        title_match = bool(doc_title) and doc_title.strip().lower() in first_page_text.lower()
        if title_match:
            return {
                "title": "Title Page", "ok": True, "warning_only": True,
                "summary": f"The first page is short and includes the book's title, looks "
                           f"like a title page.",
                "detail": f"First page word count: {word_count}. Matches document title "
                          f"\"{doc_title}\".",
            }
        return {
            "title": "Title Page", "ok": True, "warning_only": True,
            "summary": "The first page is short, consistent with a title page, but we "
                       "couldn't confirm it matches your book's title.",
            "detail": f"First page word count: {word_count}. "
                      + (f"Document title metadata: \"{doc_title}\"." if doc_title
                         else "No document title metadata was set to compare against."),
        }

    return {
        "title": "Title Page", "ok": False, "warning_only": True,
        "summary": "The first page has a lot of text on it, it may go straight into the "
                   "story without a dedicated title page.",
        "fix": "This is a guess, not a certainty, skip it if your book intentionally opens "
               "this way (some do). Otherwise, add a simple page at the front with just the "
               "title and your name before the story starts.",
        "detail": f"First page word count: {word_count} (a typical title page has well under "
                  f"50 words).",
    }


def run(full_text: str, first_page_text: str = None, doc_title: str = None) -> list:
    results = [check_copyright_page(full_text)]
    if first_page_text is not None:
        results.append(check_title_page(first_page_text, doc_title))
    return results
