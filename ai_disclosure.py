"""AI Disclosure & Detection-Risk Advisor (Pro).

Two independent things, kept separate on purpose:

1. A disclosure decision-tree grounded in KDP's actual published distinction
   (kdp.amazon.com Content Guidelines, "AI-generated" vs "AI-assisted"):
     - AI-GENERATED (must disclose): an AI tool created the actual text,
       images, or translation that appears in the book, even if you edited
       it heavily afterward. The classification is set at creation, not by
       how much you touched it up later, that's the part authors keep
       getting wrong.
     - AI-ASSISTED (no disclosure needed): you created the content yourself;
       AI only brainstormed, edited, refined, or error-checked it.

2. A manuscript scan for phrasing patterns that AI-detection tools commonly
   flag. This does NOT claim to detect whether text "is AI." Detectors have
   documented false-positive rates as high as 50%, hitting non-native
   English speakers and neurodivergent writers hardest. The scan exists to
   help a HUMAN author spot the passages a detector is most likely to
   misfire on, before Amazon's own scanner does, not to accuse anyone of
   anything.
"""
import re
import statistics

# ---------------------------------------------------------------------------
# 1. Disclosure decision tree
# ---------------------------------------------------------------------------

def classify_disclosure(used_ai: bool, ai_wrote_it: bool) -> dict:
    """used_ai: did any AI tool touch the text/images/translation at all?
    ai_wrote_it: did the AI produce the actual words/images from scratch,
    as opposed to you writing it and AI only editing/brainstorming?"""
    if not used_ai:
        return {
            "verdict": "No disclosure needed",
            "category": "none",
            "explanation": "You told us no AI tool was involved in the text, images, "
                            "or translations in this book. KDP's AI question doesn't apply.",
        }
    if not ai_wrote_it:
        return {
            "verdict": "AI-assisted - no disclosure needed",
            "category": "assisted",
            "explanation": "You wrote the content yourself and only used AI to brainstorm, "
                            "edit, refine, or check it, that's \"AI-assisted\" under KDP's "
                            "policy, and it does not need to be disclosed. This stays true "
                            "even if AI helped substantially with editing.",
        }
    return {
        "verdict": "AI-generated - disclosure required",
        "category": "generated",
        "explanation": "An AI tool produced the actual text, images, or translation here, "
                        "even if you edited it afterward. KDP classifies this as "
                        "\"AI-generated\" at the moment of creation, not by how much you "
                        "touched it up later, so you need to answer \"yes\" to KDP's AI "
                        "content question for this book.",
    }


# ---------------------------------------------------------------------------
# 2. Detection-risk scan
# ---------------------------------------------------------------------------

# Words/phrases repeatedly cited (by AI-detection researchers and editors) as
# disproportionately common in AI-generated text. Presence isn't proof of
# anything on its own, natural writers use these words too, but a cluster of
# them is exactly the kind of thing that trips detectors.
_FLAG_PHRASES = [
    "delve into", "delving into", "in the realm of", "in today's world",
    "it's important to note", "it is important to note", "moreover,",
    "furthermore,", "additionally,", "in conclusion,", "in summary,",
    "overall,", "navigate the complexities", "unlock the potential",
    "unleash the", "elevate your", "seamless", "seamlessly", "robust",
    "leverage", "leveraging", "landscape of", "when it comes to",
    "at the end of the day", "it goes without saying", "needless to say",
    "holistic", "multifaceted", "paramount", "meticulous", "meticulously",
    "comprehensive", "cutting-edge", "game-changer", "dive into", "let's dive in",
    "testament to", "underscore", "underscores", "boasts", "tapestry",
    "in essence", "on the other hand,",
]

# Leftover AI disclaimers, literal proof text was never cleaned up.
_LITERAL_AI_TELLS = [
    "as an ai language model", "as an ai, i", "i don't have personal experiences",
    "i cannot provide", "as of my last knowledge update", "i'm sorry, but i cannot",
    "i do not have the ability to", "as a large language model",
]

_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")
_WORD = re.compile(r"[A-Za-z']+")


def _sentences(text: str):
    return [s.strip() for s in _SENTENCE_SPLIT.split(text) if s.strip()]


def _first_word(sentence: str) -> str:
    m = _WORD.search(sentence)
    return m.group(0).lower() if m else ""


def scan_manuscript(text: str, max_examples: int = 8) -> dict:
    sentences = _sentences(text)
    total_sentences = len(sentences)
    low = text.lower()

    findings = []

    # Literal leftover AI disclaimer text: an unambiguous, real red flag.
    literal_hits = [p for p in _LITERAL_AI_TELLS if p in low]
    if literal_hits:
        findings.append({
            "severity": "high",
            "label": "Leftover AI assistant text found",
            "detail": "Found the phrase " + ", ".join(f"\"{h}\"" for h in literal_hits[:3]) +
                      " still in the manuscript. This is a clear sign an AI tool's raw output "
                      "was pasted in without being fully replaced, remove it.",
        })

    # Flagged phrase density.
    phrase_counts = {}
    for phrase in _FLAG_PHRASES:
        c = low.count(phrase)
        if c:
            phrase_counts[phrase] = c
    total_flagged = sum(phrase_counts.values())
    word_count = len(_WORD.findall(text)) or 1
    density_per_1000 = total_flagged / word_count * 1000

    if total_flagged:
        top = sorted(phrase_counts.items(), key=lambda kv: -kv[1])[:max_examples]
        severity = "high" if density_per_1000 > 3 else ("medium" if density_per_1000 > 1 else "low")
        findings.append({
            "severity": severity,
            "label": f"{total_flagged} instance(s) of phrasing detectors commonly flag",
            "detail": ", ".join(f"\"{p}\" x{n}" for p, n in top) +
                      f" - about {density_per_1000:.1f} per 1,000 words.",
        })

    # Burstiness: real human writing varies sentence length a lot; very
    # uniform sentence length is one of the most-cited AI-detector signals.
    cv = None
    if total_sentences >= 12:
        lengths = [len(_WORD.findall(s)) for s in sentences]
        mean_len = statistics.mean(lengths)
        if mean_len > 0:
            stdev_len = statistics.pstdev(lengths)
            cv = stdev_len / mean_len
            if cv < 0.35:
                findings.append({
                    "severity": "medium",
                    "label": "Very uniform sentence length",
                    "detail": f"Your sentences vary in length by only {cv:.2f} (coefficient of "
                              f"variation); natural human writing usually varies more. Detectors "
                              f"read very even sentence rhythm as a signal, mixing short and long "
                              f"sentences more will reduce that.",
                })

    # Repetitive sentence openers.
    if total_sentences >= 10:
        openers = [w for w in (_first_word(s) for s in sentences) if w]
        if openers:
            from collections import Counter
            counts = Counter(openers)
            top_word, top_n = counts.most_common(1)[0]
            share = top_n / len(openers)
            if share > 0.22 and top_n >= 5:
                findings.append({
                    "severity": "low",
                    "label": f"\"{top_word.capitalize()}\" starts {top_n} sentences ({share*100:.0f}%)",
                    "detail": "Repetitive sentence openers are another common detector signal. "
                              "Varying how sentences start usually fixes this naturally during a "
                              "normal edit pass.",
                })

    risk_score = 0
    for f in findings:
        risk_score += {"high": 30, "medium": 15, "low": 7}[f["severity"]]
    risk_score = min(risk_score, 95) if findings else 3

    return {
        "risk_score": risk_score,
        "findings": findings,
        "word_count": word_count,
        "sentence_count": total_sentences,
    }
