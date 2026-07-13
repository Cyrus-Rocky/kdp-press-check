"""Detects whether an uploaded file actually looks like a book interior,
as opposed to a screenplay/script, a near-empty document, slides, or
something else KDP's paperback interior rules were never meant to judge.

This runs first and reports honestly either way, it does not block the
rest of the checks from running, it just tells the user what it found.
"""
import re

SCREENPLAY_PATTERN = re.compile(
    r"(\bINT\.\s|\bEXT\.\s|\bINT/EXT\.\s|\bFADE IN:|\bFADE OUT|\bCUT TO:|"
    r"\(V\.O\.\)|\(O\.S\.\)|\(CONT'D\))",
    re.IGNORECASE,
)

MIN_WORDS_PER_PAGE_FOR_BOOK = 30


def classify(page_count: int, full_text: str, mono_font_page_ratio: float,
             landscape_page_ratio: float) -> dict:
    """Returns {kind, summary, fix} based on aggregate signals.

    kind is one of: "book", "screenplay", "sparse_text", "no_text", "landscape".
    """
    if page_count == 0:
        return {"kind": "no_text", "summary": "This file has no pages.",
                "fix": "Upload a manuscript PDF or Word file with at least one page."}

    words = full_text.split()
    word_count = len(words)
    words_per_page = word_count / page_count
    screenplay_hits = len(SCREENPLAY_PATTERN.findall(full_text))
    screenplay_ratio = screenplay_hits / page_count

    if screenplay_ratio >= 0.4 or (screenplay_ratio >= 0.15 and mono_font_page_ratio >= 0.5):
        detail_bits = [f"about {screenplay_ratio:.1f} screenplay markers per page "
                        f"(scene headings like INT./EXT., FADE IN/OUT, CUT TO)"]
        if mono_font_page_ratio >= 0.5:
            detail_bits.append(
                f"{mono_font_page_ratio * 100:.0f}% of pages set in a Courier-style "
                f"monospace font, which is the screenplay industry standard"
            )
        return {
            "kind": "screenplay",
            "summary": "This reads like a screenplay or script, not a book interior, "
                       + " and ".join(detail_bits) + ".",
            "fix": "Screenplays follow different formatting standards (and usually go to "
                   "different platforms, like KDP Print for a bound script, or a "
                   "screenwriting-specific service) than a novel or nonfiction interior. "
                   "The trim/margin/bleed rules below are built for book interiors, so "
                   "they may not mean much here, if you did mean to upload a book "
                   "manuscript, double-check you picked the right file.",
        }

    if word_count == 0:
        return {
            "kind": "no_text",
            "summary": "No readable text was found anywhere in this file.",
            "fix": "If this is a scanned book, it needs to be a text-based PDF, not just "
                   "page images, otherwise this just isn't a manuscript file. Double-check "
                   "you uploaded the right document.",
        }

    if words_per_page < MIN_WORDS_PER_PAGE_FOR_BOOK:
        return {
            "kind": "sparse_text",
            "summary": f"Only about {words_per_page:.0f} words per page on average, too "
                       f"little body text for a typical book interior. This might be slides, "
                       f"a cover sheet, a form, or a mostly-blank file.",
            "fix": "If this was meant to be your book's interior, make sure you uploaded the "
                   "full manuscript and not a title page, a template, or an export with "
                   "mostly empty pages.",
        }

    if landscape_page_ratio > 0.5:
        return {
            "kind": "landscape",
            "summary": f"Most pages ({landscape_page_ratio * 100:.0f}%) are landscape-oriented, "
                       f"which is unusual for a paperback book interior, those are almost "
                       f"always portrait.",
            "fix": "If this is meant to be a paperback interior, check that you exported it "
                   "in portrait orientation. Landscape can be correct for some children's "
                   "books, comics, or photo books, if that's what this is, you can ignore "
                   "this note.",
        }

    page_word = "page" if page_count == 1 else "pages"
    return {
        "kind": "book",
        "summary": f"Reads like a book interior, about {words_per_page:.0f} words per page "
                   f"across {page_count} {page_word}.",
        "fix": None,
    }
