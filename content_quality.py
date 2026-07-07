"""Writing/content quality checks that apply to any manuscript regardless of
file format — repeated words, stray formatting artifacts, mixed punctuation
styles, and possible typos. These are heuristics, not a full grammar engine:
they're tuned to flag real problems without drowning the author in false
positives from character names or stylistic choices.
"""
import re
from collections import Counter

from spellchecker import SpellChecker

_REPEATED_WORD = re.compile(r"\b(\w+)\s+\1\b", re.IGNORECASE)
_DOUBLE_SPACE = re.compile(r"[^\S\n]{2,}")
_MULTI_BLANK_LINE = re.compile(r"\n[ \t]*\n[ \t]*\n[ \t]*\n+")

_WORD_TOKEN = re.compile(r"[A-Za-z']+")

_spell = None


def _get_spell():
    global _spell
    if _spell is None:
        _spell = SpellChecker()
    return _spell


def _check_repeated_words(text: str) -> dict:
    matches = _REPEATED_WORD.findall(text)
    if not matches:
        return {"title": "Repeated Words", "ok": True,
                "summary": "No accidentally doubled words found.",
                "detail": "Scanned for patterns like \"the the\" — none found."}
    counts = Counter(w.lower() for w in matches)
    examples = ", ".join(f"\"{w} {w}\"" for w, _ in counts.most_common(5))
    return {
        "title": "Repeated Words", "ok": False, "warning_only": True,
        "summary": f"Found {len(matches)} place(s) where a word repeats back-to-back, "
                   f"like {examples}.",
        "fix": "Search your manuscript for these doubled words and remove the extra one — "
               "this usually happens from editing/pasting.",
        "detail": ", ".join(f"\"{w} {w}\" x{n}" for w, n in counts.most_common(15)),
    }


def _check_spacing(text: str) -> dict:
    double_spaces = len(_DOUBLE_SPACE.findall(text))
    multi_blank = len(_MULTI_BLANK_LINE.findall(text))
    if double_spaces == 0 and multi_blank == 0:
        return {"title": "Spacing", "ok": True,
                "summary": "No stray double spaces or oversized gaps found.",
                "detail": "Checked for repeated spaces and 3+ consecutive blank lines."}
    bits = []
    if double_spaces:
        bits.append(f"{double_spaces} place(s) with a double (or larger) space between words")
    if multi_blank:
        bits.append(f"{multi_blank} place(s) with 3+ blank lines in a row")
    return {
        "title": "Spacing", "ok": False, "warning_only": True,
        "summary": "Found " + " and ".join(bits) + ".",
        "fix": "Use Find & Replace for double spaces (search for two spaces, replace with "
               "one). Large gaps between paragraphs are often leftover from editing — check "
               "those spots render as you intend.",
        "detail": f"Double/extra spaces: {double_spaces}. Oversized paragraph gaps: {multi_blank}.",
    }


def _check_quote_consistency(text: str) -> dict:
    straight = text.count('"') + text.count("'")
    curly = sum(text.count(c) for c in ['“', '”', '‘', '’'])
    total = straight + curly
    if total < 10 or straight == 0 or curly == 0:
        return {"title": "Quote Style", "ok": True,
                "summary": "Quote marks are used consistently (all straight or all curly).",
                "detail": f"Straight quotes: {straight}. Curly/smart quotes: {curly}."}
    minority = min(straight, curly)
    return {
        "title": "Quote Style", "ok": False, "warning_only": True,
        "summary": f"This manuscript mixes straight quotes (\"like this\") and curly quotes "
                   f"(“like this”) — {minority} marks are the minority style.",
        "fix": "Pick one style and apply it throughout. Most word processors auto-convert to "
               "curly (\"smart\") quotes by default — if you see straight quotes mixed in, "
               "they were likely typed somewhere autocorrect was off, or pasted from another source.",
        "detail": f"Straight quotes: {straight}. Curly/smart quotes: {curly}.",
    }


def _classify_heading_case(heading: str) -> str:
    words = [w for w in re.split(r"\s+", heading.strip()) if w]
    if not words:
        return "empty"
    letters_only = "".join(c for c in heading if c.isalpha())
    if letters_only and letters_only.isupper():
        return "upper"
    if heading[0].isalpha() and heading[0].islower():
        return "lower-start"
    capitalized = sum(1 for w in words if w[:1].isupper())
    if capitalized >= max(1, len(words) - 1):
        return "title"
    return "sentence"


def _check_heading_consistency(headings: list) -> dict:
    if not headings or len(headings) < 2:
        return None
    styles = [s for s in (_classify_heading_case(h) for h in headings) if s != "empty"]
    if not styles:
        return None
    counts = Counter(styles)
    if len(counts) == 1:
        return {"title": "Heading Style", "ok": True,
                "summary": f"All {len(styles)} headings use the same capitalization style.",
                "detail": f"Style: {next(iter(counts))}."}
    dominant_style, dominant_count = counts.most_common(1)[0]
    return {
        "title": "Heading Style", "ok": False, "warning_only": True,
        "summary": f"Headings mix capitalization styles — most ({dominant_count} of "
                   f"{len(styles)}) use {dominant_style} case, but not all.",
        "fix": "Pick one heading style (Title Case, Sentence case, or ALL CAPS) and make "
               "every chapter/section heading match it.",
        "detail": ", ".join(f"{style}: {n}" for style, n in counts.most_common()),
    }


_SCENE_BREAK_REPEAT_SYMBOLS = set("*#~•§×◆✦∞○")


def _check_scene_break_consistency(text: str) -> dict:
    """Scene breaks (a blank line with a symbol marking a jump in time/POV)
    should use one marker throughout — mixing *** in one place and # in
    another reads as an accident, not a stylistic choice."""
    candidates = []
    for line in text.split("\n"):
        compact = re.sub(r"\s+", "", line.strip())
        if not compact or len(set(compact)) != 1:
            continue
        ch = compact[0]
        if ch in _SCENE_BREAK_REPEAT_SYMBOLS or (ch == "-" and len(compact) >= 3):
            candidates.append(ch)

    if not candidates:
        return {"title": "Scene Break Style", "ok": True,
                "summary": "No scene-break markers (like *** or #) found to check.",
                "detail": "Scanned for standalone lines made only of repeated symbols "
                          "(*, #, ~, -, etc)."}

    sig_counts = Counter(candidates)
    if len(sig_counts) == 1:
        ch, n = next(iter(sig_counts.items()))
        return {"title": "Scene Break Style", "ok": True,
                "summary": f"All {n} scene break(s) use the same marker (\"{ch}\").",
                "detail": f"Marker character: \"{ch}\"."}

    examples = ", ".join(f"\"{ch}\" x{n}" for ch, n in sig_counts.most_common())
    return {
        "title": "Scene Break Style", "ok": False, "warning_only": True,
        "summary": f"Scene breaks use {len(sig_counts)} different markers: {examples}.",
        "fix": "Pick one scene-break symbol (commonly *** or a centered #) and use Find & "
               "Replace to make every scene break in the manuscript match it.",
        "detail": examples,
    }


_TYPO_REPEAT_THRESHOLD = 3  # a word appearing this many+ times reads as a name/invented term, not a typo


def _check_spelling(text: str) -> dict:
    words = [w for w in _WORD_TOKEN.findall(text) if len(w) >= 3]
    if not words:
        return {"title": "Possible Typos", "ok": True,
                "summary": "No body text to spell-check.",
                "detail": "No words found."}
    spell = _get_spell()
    lower_words = [w.lower() for w in words if not w.isupper()]
    sample = lower_words[:20000]  # cap for very long manuscripts
    unknown = spell.unknown(sample)
    if not unknown:
        return {"title": "Possible Typos", "ok": True,
                "summary": "No words flagged against our dictionary.",
                "detail": f"Checked {len(sample)} word(s)."}

    counts = Counter(w for w in sample if w in unknown)
    # A word that recurs is almost certainly a character name or invented term an author
    # typed on purpose; a word seen once or twice is much more likely to be an actual typo.
    repeated = {w: n for w, n in counts.items() if n >= _TYPO_REPEAT_THRESHOLD}
    one_offs = {w: n for w, n in counts.items() if n < _TYPO_REPEAT_THRESHOLD}

    if not one_offs:
        return {
            "title": "Possible Typos", "ok": True, "warning_only": True,
            "summary": f"{len(counts)} word(s) aren't in our dictionary, but each appears "
                       f"{_TYPO_REPEAT_THRESHOLD}+ times — almost certainly character names or "
                       f"invented terms rather than typos.",
            "detail": ", ".join(f"\"{w}\" x{n}" for w, n in Counter(repeated).most_common(15)),
        }

    top_one_offs = Counter(one_offs).most_common(15)
    examples = ", ".join(f"\"{w}\"" for w, _ in top_one_offs[:6])
    summary = (f"{len(one_offs)} word(s) that appear only once or twice aren't in our "
               f"dictionary, e.g. {examples} — these are more likely to be real typos than "
               f"recurring names.")
    if repeated:
        summary += (f" ({len(repeated)} other word(s) recur {_TYPO_REPEAT_THRESHOLD}+ times and "
                     f"are left out of this list as likely names/invented terms.)")
    return {
        "title": "Possible Typos", "ok": False, "warning_only": True,
        "summary": summary,
        "fix": "These are still guesses, not confirmed errors — but words appearing only once "
               "or twice are worth a look first, since recurring character names and invented "
               "words have already been filtered out of this list.",
        "detail": ", ".join(f"\"{w}\" x{n}" for w, n in top_one_offs),
    }


def run(full_text: str, headings: list = None) -> list:
    """Returns a list of check-result dicts in the same shape as the print checks."""
    results = [
        _check_repeated_words(full_text),
        _check_spacing(full_text),
        _check_quote_consistency(full_text),
        _check_scene_break_consistency(full_text),
        _check_spelling(full_text),
    ]
    heading_result = _check_heading_consistency(headings or [])
    if heading_result:
        results.append(heading_result)
    return results
