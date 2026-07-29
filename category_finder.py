"""Category & Trap Finder (Pro).

Important honesty note, stated in the UI too: we don't have live access to
Amazon's category tree (nobody outside Amazon does, reliably; it changes
without notice). This tool does two things that don't require that:

1. Applies well-documented heuristics for which category CHOICES tend to be
   traps, categories too broad to ever rank in, or a genre/age mismatch that
   gets a book placed wrong or rejected.
2. Teaches the one verification method that's always accurate because it
   checks Amazon's live site directly: searching your exact category
   breadcrumb and checking whether books in it show a bestseller-rank badge
   in the top ~20 results. No bestseller badges appearing = a dead/ghost
   category, whatever a spreadsheet claims.
"""

# A representative (not exhaustive) set of common category paths per genre,
# each flagged with a heuristic verdict and why. This mirrors the publicly
# documented BISAC subject structure KDP's own category picker uses.
CATEGORY_EXAMPLES = {
    "fiction": [
        {"path": "Fiction", "verdict": "trap", "reason": "Top-level only, far too broad. KDP won't let you stop here, but choosing the broadest available parent instead of a specific child has the same effect: you compete with millions of books for a rank that will never register."},
        {"path": "Fiction > Mystery & Detective > Women Sleuths", "verdict": "good", "reason": "Specific, genre-matched, and deep enough (3 levels) to realistically rank in."},
        {"path": "Fiction > Romance > Clean & Wholesome", "verdict": "good", "reason": "Specific sub-genre with an active, searchable readership."},
        {"path": "Fiction > Sagas", "verdict": "watch", "reason": "Exists, but thin. Verify it manually, bestseller badges are inconsistent here."},
        {"path": "Fiction > Literary", "verdict": "watch", "reason": "Valid but extremely broad within its own genre; a more specific literary sub-theme usually ranks better."},
    ],
    "nonfiction": [
        {"path": "Self-Help", "verdict": "trap", "reason": "Top-level only. Every self-help book on Amazon technically fits here, which means none of them stand out."},
        {"path": "Self-Help > Personal Growth > Success", "verdict": "good", "reason": "Specific enough to have a reachable bestseller rank."},
        {"path": "Business & Money > Small Business & Entrepreneurship", "verdict": "good", "reason": "Popular but specific, verify current competition before committing."},
        {"path": "Health, Fitness & Dieting > Diets & Weight Loss > General", "verdict": "trap", "reason": "\"General\" sub-categories are almost always a broad catch-all in disguise, avoid picking anything with \"General\" in the final segment if a more specific one exists."},
    ],
    "childrens": [
        {"path": "Children's Books", "verdict": "trap", "reason": "Top-level only, and age-group mismatches here are a common cause of KDP category rejections."},
        {"path": "Children's Books > Growing Up & Facts of Life > Friendship, Social Skills & School Life", "verdict": "good", "reason": "Specific, age-matched, and a real, searchable shelf."},
        {"path": "Children's Books > Early Learning > Counting & Numbers", "verdict": "good", "reason": "Specific and matched to a clear reader intent (parents searching for this exact thing)."},
    ],
    "romance": [
        {"path": "Romance", "verdict": "trap", "reason": "Far too broad, romance is one of the most saturated top-level categories on Amazon."},
        {"path": "Romance > Billionaires", "verdict": "good", "reason": "Specific, high-intent sub-genre with an active readership."},
        {"path": "Romance > Holidays", "verdict": "watch", "reason": "Real, but seasonal, bestseller potential swings hard with the calendar."},
    ],
}

GENRE_LABELS = {
    "fiction": "Fiction (general)",
    "nonfiction": "Non-Fiction / Self-Help",
    "childrens": "Children's Books",
    "romance": "Romance",
}

VERDICT_LABEL = {"trap": "Likely trap", "watch": "Verify before using", "good": "Good choice"}
VERDICT_SEVERITY = {"trap": "issue", "watch": "note", "good": "ok"}

# Heuristic red flags applied to any free-typed category path.
_TRAP_WORDS = ["general", "misc", "miscellaneous"]


def examples_for(genre_key: str):
    return CATEGORY_EXAMPLES.get(genre_key, [])


def evaluate_custom_path(path: str) -> dict:
    path = (path or "").strip()
    if not path:
        return {"verdict": "unknown", "reasons": ["Enter a category path to check it."]}

    segments = [s.strip() for s in path.split(">") if s.strip()]
    reasons = []
    verdict = "watch"

    if len(segments) <= 1:
        verdict = "trap"
        reasons.append("This is a top-level category only. Top-level categories are almost "
                        "always too broad to ever show a meaningful bestseller rank, look for "
                        "a specific sub-category instead.")
    elif len(segments) == 2:
        reasons.append("Two levels deep is workable but still broad. A third level "
                        "(sub-sub-category) usually ranks more reliably if one exists for your genre.")
    else:
        reasons.append(f"{len(segments)} levels deep, specific enough to realistically rank in, "
                        f"assuming it's genre-matched (verify below).")

    low = path.lower()
    if any(w in low for w in _TRAP_WORDS):
        verdict = "trap"
        reasons.insert(0, "Contains \"General\" or similar. These catch-all sub-categories are a "
                          "very common trap, they sound specific but function like the broad "
                          "parent category.")
    elif verdict == "watch" and len(segments) >= 3:
        verdict = "good"

    return {"verdict": verdict, "reasons": reasons, "segment_count": len(segments)}
