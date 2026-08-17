"""Page break and chapter structure analysis.

Detects chapters that are too long (>10k words) without internal breaks,
and suggests where page/section breaks should be added for better readability.
"""
import re
from collections import defaultdict


def _find_chapters(full_text: str) -> list:
    """Identify chapter boundaries by looking for Heading 1 patterns.
    Returns list of (chapter_title, start_pos, end_pos, word_count)."""
    # Match common chapter patterns:
    # "Chapter 1", "CHAPTER ONE", "1.", "Part 1", "Section 1", etc.
    # Also standalone lines that look like headings (short, often all caps)
    chapter_pattern = re.compile(
        r"^(?:chapter|part|section|act|book|prologue|epilogue|interlude|outro|\d+\.?)\s*[\w\s]*$",
        re.IGNORECASE | re.MULTILINE
    )

    chapters = []
    for match in chapter_pattern.finditer(full_text):
        start = match.start()
        title = match.group(0).strip()
        # Find next chapter or end of text
        next_match = chapter_pattern.search(full_text, match.end())
        end = next_match.start() if next_match else len(full_text)

        chapter_text = full_text[start:end]
        word_count = len(chapter_text.split())
        chapters.append((title, start, end, word_count))

    return chapters


def _has_breaks_in_text(text: str) -> bool:
    """Check if text contains scene/section break markers or page breaks."""
    # Common scene break markers: ***, ---, ###, ~~~, •••, etc.
    # Also check for multiple consecutive blank lines (paragraph breaks)
    break_patterns = [
        r"^\s*(\*{2,}|-{3,}|#{2,}|~{2,}|•{2,}|§|✦)\s*$",  # line-only symbols
        r"\n\n\n+",  # 3+ consecutive newlines
    ]

    for pattern in break_patterns:
        if re.search(pattern, text, re.MULTILINE):
            return True
    return False


def check_chapter_length(full_text: str) -> dict:
    """Detect chapters >10k words without internal breaks."""
    chapters = _find_chapters(full_text)

    if not chapters:
        return {
            "title": "Chapter Structure",
            "ok": True,
            "warning_only": True,
            "summary": "No standard chapter headings detected. Skipping chapter length check.",
            "detail": "No patterns like 'Chapter 1', 'Part 1', etc. were found.",
        }

    long_chapters = []
    for title, start, end, word_count in chapters:
        if word_count > 10000:
            # Check if there are internal breaks
            chapter_text = full_text[start:end]
            has_breaks = _has_breaks_in_text(chapter_text)
            if not has_breaks:
                long_chapters.append((title, word_count))

    if not long_chapters:
        return {
            "title": "Chapter Structure",
            "ok": True,
            "warning_only": True,
            "summary": f"All {len(chapters)} chapters are well-paced. No chapters over 10,000 words without breaks.",
            "detail": "Chapters are readable length with good pacing.",
        }

    # Format the issue
    chapter_list = ", ".join(f"{title} ({wc:,} words)" for title, wc in long_chapters[:5])
    if len(long_chapters) > 5:
        chapter_list += f", and {len(long_chapters) - 5} more"

    return {
        "title": "Chapter Length",
        "ok": False,
        "warning_only": True,
        "summary": f"Found {len(long_chapters)} chapter(s) over 10,000 words without breaks: {chapter_list}.",
        "fix": "Long chapters without breaks can feel overwhelming. Consider adding a scene break "
               "(e.g., ***, ---, or ~~~) to break it into paced sections. This improves readability "
               "without changing the story.",
        "detail": f"Total chapters scanned: {len(chapters)}. Long chapters flagged: {len(long_chapters)}.",
    }


def run(full_text: str) -> list:
    """Returns page/chapter structure checks."""
    return [check_chapter_length(full_text)]
