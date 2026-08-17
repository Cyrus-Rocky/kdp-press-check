"""Writing/content quality checks that apply to any manuscript regardless of
file format, repeated words, stray formatting artifacts, mixed punctuation
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
                "detail": "Scanned for patterns like \"the the\", none found."}
    counts = Counter(w.lower() for w in matches)
    # Only flag if a word is doubled 2+ times (likely an accident, not stylistic emphasis)
    frequent_repeats = {w: n for w, n in counts.items() if n >= 2}
    if not frequent_repeats:
        return {"title": "Repeated Words", "ok": True,
                "summary": "Doubled words found, but only once each (likely intentional emphasis).",
                "detail": f"Scanned {len(matches)} doubled-word instance(s), none repeated."}
    examples = ", ".join(f"\"{w} {w}\"" for w, _ in sorted(frequent_repeats.items(),
                                                            key=lambda x: x[1], reverse=True)[:5])
    return {
        "title": "Repeated Words", "ok": False, "warning_only": True,
        "summary": f"Found {len(frequent_repeats)} doubled-word pattern(s) that repeat multiple times, "
                   f"like {examples}.",
        "fix": "Search your manuscript for these doubled words and remove the extra one, "
               "this usually happens from editing/pasting.",
        "detail": ", ".join(f"\"{w} {w}\" x{n}" for w, n in sorted(frequent_repeats.items(),
                                                                     key=lambda x: x[1], reverse=True)[:15]),
    }


def _check_spacing(text: str) -> dict:
    double_spaces = len(_DOUBLE_SPACE.findall(text))
    multi_blank = len(_MULTI_BLANK_LINE.findall(text))
    if double_spaces == 0 and multi_blank == 0:
        return {"title": "Spacing", "ok": True,
                "summary": "No stray double spaces or oversized gaps found.",
                "detail": "Checked for repeated spaces and 3+ consecutive blank lines."}
    # Only flag excessive spacing (25+ instances suggests a real problem)
    bits = []
    flagged = False
    if double_spaces >= 25:
        bits.append(f"{double_spaces} place(s) with a double (or larger) space between words")
        flagged = True
    elif double_spaces > 0:
        bits.append(f"{double_spaces} double space(s) (minor)")
    if multi_blank >= 10:
        bits.append(f"{multi_blank} place(s) with 3+ blank lines in a row")
        flagged = True
    elif multi_blank > 0:
        bits.append(f"{multi_blank} oversized gap(s) (usually intentional)")
    if not flagged:
        return {
            "title": "Spacing", "ok": True, "warning_only": True,
            "summary": "Minor spacing issues found, but not excessive. Likely intentional formatting.",
            "detail": f"Double/extra spaces: {double_spaces}. Oversized paragraph gaps: {multi_blank}.",
        }
    return {
        "title": "Spacing", "ok": False, "warning_only": True,
        "summary": "Found " + " and ".join(bits) + ".",
        "fix": "Use Find & Replace for double spaces (search for two spaces, replace with "
               "one). Large gaps between paragraphs are often leftover from editing, check "
               "those spots render as you intend.",
        "detail": f"Double/extra spaces: {double_spaces}. Oversized paragraph gaps: {multi_blank}.",
    }


def _check_quote_consistency(text: str) -> dict:
    straight = text.count('"') + text.count("'")
    curly = 0
    for quote_char in ['“', '”', '‘', '’']:
        curly += text.count(quote_char)
    total = straight + curly
    if total < 20:
        return {"title": "Quote Style", "ok": True,
                "summary": "Too few quotes to reliably check consistency.",
                "detail": f"Straight quotes: {straight}. Curly/smart quotes: {curly}."}
    minority_pct = min(straight, curly) / total if total > 0 else 0
    if minority_pct < 0.2:
        return {"title": "Quote Style", "ok": True,
                "summary": "Quote marks are mostly consistent. Rare exceptions are normal.",
                "detail": f"Straight quotes: {straight} ({straight/total*100:.0f}%). Curly/smart quotes: {curly} ({curly/total*100:.0f}%)."}
    return {
        "title": "Quote Style", "ok": False, "warning_only": True,
        "summary": f"This manuscript mixes straight quotes and curly quotes, with {int(minority_pct*100)}% being the minority style.",
        "fix": "This is usually from PDFs combining text from multiple sources or scanned content. If it bothers you, use Find & Replace to standardize, but KDP accepts mixed quotes.",
        "detail": f"Straight quotes: {straight} ({straight/total*100:.0f}%). Curly/smart quotes: {curly} ({curly/total*100:.0f}%).",
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
        "summary": f"Headings mix capitalization styles, most ({dominant_count} of "
                   f"{len(styles)}) use {dominant_style} case, but not all.",
        "fix": "Pick one heading style (Title Case, Sentence case, or ALL CAPS) and make "
               "every chapter/section heading match it.",
        "detail": ", ".join(f"{style}: {n}" for style, n in counts.most_common()),
    }


_SCENE_BREAK_REPEAT_SYMBOLS = set("*#~•§×◆✦∞○")


def _check_scene_break_consistency(text: str) -> dict:
    """Scene breaks (a blank line with a symbol marking a jump in time/POV)
    should use one marker throughout, mixing *** in one place and # in
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
                "detail": "Scanned for standalone lines made only of repeated symbols (*, #, ~, -, etc)."}

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


_TYPO_REPEAT_THRESHOLD = 3


def _check_spelling(text: str) -> dict:
    """Check for ACTUAL spelling errors with correction suggestions.

    Very conservative: only flags words that recur 2+ times AND have close matches.
    Ignores single-occurrence words (likely names or domain terms).
    Shows actual corrections, not just "this word might be wrong".
    """
    words = [w for w in _WORD_TOKEN.findall(text) if len(w) >= 4]  # 4+ chars only
    if not words:
        return {"title": "Spelling & Typos", "ok": True,
                "summary": "No text found to spell-check.",
                "detail": "Manuscript needs body text."}
    spell = _get_spell()
    lower_words = [w.lower() for w in words if not w.isupper()]
    sample = lower_words[:20000]
    unknown = spell.unknown(sample)
    if not unknown:
        return {"title": "Spelling & Typos", "ok": True,
                "summary": "No spelling issues detected.",
                "detail": f"Checked {len(sample)} word(s) - all look correct."}

    counts = Counter(w for w in sample if w in unknown)

    # Only flag RECURRING mistakes (appears 2+ times = likely typo, not a name)
    # And only if we can suggest a real correction
    likely_typos = {}
    for word, count in counts.items():
        if count >= 2:  # Only recurring mistakes
            suggestion = spell.correction(word)
            if suggestion and suggestion != word:
                likely_typos[word] = {"count": count, "suggestion": suggestion}

    if not likely_typos:
        return {
            "title": "Spelling & Typos", "ok": True, "warning_only": True,
            "summary": f"No spelling errors found. ({len(counts)} unknown words appear only once, "
                       f"likely character names or domain terms.)",
            "detail": "Only flagging words that recur multiple times - those are more likely real typos.",
        }

    # Format with corrections
    corrections = []
    for word, info in sorted(likely_typos.items(), key=lambda x: x[1]["count"], reverse=True)[:10]:
        corrections.append(f"\"{word}\" → \"{info['suggestion']}\" (appears {info['count']}x)")

    return {
        "title": "Spelling & Typos", "ok": False, "warning_only": True,
        "summary": f"Found {len(likely_typos)} spelling error(s) with suggested corrections.",
        "fix": "Use Find & Replace to fix each suggested correction. Only showing words that recur, "
               "which are more likely to be real typos.",
        "detail": "\n".join(corrections),
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
