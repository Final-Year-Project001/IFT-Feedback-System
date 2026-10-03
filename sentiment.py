"""
sentiment.py
------------
High-Performance Sentiment Analysis Engine for FUTO IFT Feedback.

Architecture:
1. Domain-Specific Academic Lexicon (220+ specialized terms across course content,
   pedagogy, lab/IFT infrastructure, and university context).
2. Multi-Word Expression (MWE) Canonical Rewriter: Transforms idiomatic multi-word
   phrases ("needs improvement", "room for improvement", "hands on", "power outage",
   "broken projector") into single semantic tokens before evaluation. The rule
   list is ordered longest-pattern-first, because `re.sub` is greedy and a short
   pattern would otherwise consume part of a longer idiom.
3. Negation-Aware Pre-Pass: Detects negators ("not", "never", "barely", "no") before
   domain terms and flips their polarity, so "not helpful" correctly reads as negative.
   Terms that VADER's own lexicon already knows are left to VADER's negation
   window, so no term is ever penalised twice.
4. Intensifier Detection: Boosts compound score and confidence when strong intensifiers
   ("very", "extremely", "absolutely", "completely") precede sentiment words.
5. Contrastive Conjunction & Clause Weighting: Intelligently resolves mixed
   sentiment sentences ("The lecturer is great, but the lab has no working PCs")
   by weighting the conclusive stance in the contrasting clause.
6. Calibrated Confidence Scoring: Returns a deterministic confidence value in
   0.48 .. 0.99 alongside the compound score and its polarity proportions.
7. Optional Supervised Classifier: A local model trained via train_model.py on
   human-verified corrections supplies the *label only*. The numeric score, the
   polarity proportions, the cues and the confidence are always produced by
   steps 1-6, so a comment scores identically with or without a .pkl on disk.
"""

from __future__ import annotations

import os
import pickle
import re
import string
from collections import namedtuple
from typing import Any, Dict, List, Tuple

from config import MODEL_PATH

# ── VADER setup ──────────────────────────────────────────────────────
try:
    import nltk
    from nltk.sentiment.vader import SentimentIntensityAnalyzer
    _NLTK_IMPORT_ERROR = None
except Exception as exc:  # pragma: no cover
    nltk = None
    SentimentIntensityAnalyzer = None
    _NLTK_IMPORT_ERROR = exc


# ══════════════════════════════════════════════════════════════════════
#  1. DOMAIN-SPECIFIC ACADEMIC & IFT feedback LEXICON (Valence: -4.0 .. +4.0)
# ══════════════════════════════════════════════════════════════════════

ACADEMIC_DOMAIN_LEXICON: Dict[str, float] = {
    # ── Course Content & Curriculum ──
    "engaging": 2.7,
    "insightful": 2.8,
    "practical": 2.3,
    "hands_on": 2.6,
    "hands-on": 2.6,
    "applicable": 2.2,
    "coherent": 2.0,
    "comprehensive": 2.4,
    "cutting-edge": 2.8,
    "cutting_edge": 2.8,
    "enriching": 2.5,
    "in-depth": 2.4,
    "in_depth": 2.4,
    "innovative": 2.6,
    "relevant": 2.5,
    "rigorous": 1.9,
    "stimulating": 2.4,
    "structured": 2.2,
    "systematic": 2.0,
    "thorough": 2.3,
    "up-to-date": 2.5,
    "up_to_date": 2.5,
    "job_ready": 2.7,
    "industry_standard": 2.7,
    "industry_aligned": 2.5,
    "real_world": 2.2,
    "self_explanatory": 2.2,
    "well_structured": 2.6,
    "well_explained": 2.7,
    "well_delivered": 2.6,
    "easy_to_understand": 2.6,
    "easy_to_grasp": 2.5,
    "well_organized": 2.5,
    "thought_provoking": 2.7,
    "impactful": 2.5,
    "detailed": 2.2,
    "concise": 2.0,
    "logical": 2.1,
    "sequential": 1.9,
    "updated": 2.1,
    "modern": 2.0,
    "current": 1.8,
    "outdated": -2.7,
    "out_of_date": -2.7,
    "irrelevant": -2.8,
    "obsolete": -2.9,
    "shallow": -2.3,
    "superficial": -2.3,
    "overloaded": -2.2,
    "abstract": -1.5,
    "unstructured": -2.3,
    "disorganized": -2.5,
    "disorganised": -2.5,
    "pointless": -2.9,
    "stale": -2.3,
    "repetitive": -2.0,
    "monotonous": -2.2,
    "boring": -2.7,
    "hard_to_understand": -2.5,
    "hard_to_follow": -2.5,
    "difficult_to_understand": -2.3,
    "too_fast": -2.0,
    "too_slow": -1.8,
    "waste_of_time": -3.4,
    "poorly_organized": -2.4,
    "confusing": -2.3,
    "vague": -2.2,
    "incomplete": -2.1,
    "inaccurate": -2.5,
    "misleading": -2.6,
    "insufficient": -2.2,
    "theory_heavy": -1.8,

    # ── Lecturer Pedagogy & Instruction ──
    "knowledgeable": 2.7,
    "approachable": 2.6,
    "supportive": 2.5,
    "punctual": 2.4,
    "interactive": 2.4,
    "inspiring": 2.9,
    "articulate": 2.5,
    "dedicated": 2.6,
    "patient": 2.3,
    "enthusiastic": 2.5,
    "attentive": 2.2,
    "responsive": 2.4,
    "clarity": 2.5,
    "informative": 2.4,
    "lecturer_tries": 1.4,
    "experienced": 2.3,
    "professional": 2.4,
    "encouraging": 2.6,
    "compassionate": 2.4,
    "fair": 2.2,
    "accessible": 2.3,
    "clear": 2.3,
    "helpful": 2.5,
    "meticulous": 2.3,
    "organized": 2.2,
    "unclear": -2.4,
    "unresponsive": -2.6,
    "unavailable": -2.3,
    "unapproachable": -2.5,
    "unprepared": -2.7,
    "incompetent": -3.3,
    "monotone": -2.2,
    "inconsistent": -2.0,
    "dismissive": -2.7,
    "hostile": -3.2,
    "harsh": -2.4,
    "unfair": -2.7,
    "biased": -2.7,
    "favoritism": -2.9,
    "absent": -2.5,
    "rushed": -2.2,
    "inaudible": -2.4,
    "unpunctual": -2.3,
    "unhelpful": -2.6,
    "intimidating": -2.6,
    "rude": -3.0,
    "condescending": -2.9,
    "lazy": -2.8,
    "careless": -2.6,
    "disrespectful": -3.1,
    "unqualified": -3.0,

    # ── Facilities, Laboratories & Infrastructure ──
    "well-equipped": 2.7,
    "well_equipped": 2.7,
    "conducive": 2.5,
    "spacious": 2.2,
    "functional": 2.2,
    "air-conditioned": 2.3,
    "illuminated": 1.8,
    "reliable": 2.4,
    "state-of-the-art": 2.9,
    "state_of_the_art": 2.9,
    "high-speed": 2.3,
    "comfortable": 2.2,
    "clean": 2.0,
    "maintained": 2.1,
    "upgraded": 2.3,
    # NOTE: "accessible" appears once only — under Lecturer Pedagogy (2.3).
    # It used to be repeated here at 2.1, and because a dict literal keeps the
    # last value the stronger reading was silently thrown away.
    "malfunctioning": -2.9,
    "dilapidated": -3.1,
    "overcrowded": -2.5,
    "unconducive": -2.7,
    "crammed": -2.3,
    "inadequate": -2.6,
    "substandard": -2.7,
    "faulty": -2.5,
    "broken": -2.5,
    "broken_projector": -2.9,
    "power_outage": -2.8,
    "no_light": -2.7,
    "poor_network": -2.9,
    "poor_ventilation": -2.5,
    "no_practicals": -2.7,
    "not_enough_computers": -2.6,
    "barely_functional": -2.9,
    "stifling": -2.4,
    "suffocating": -2.6,
    "noisy": -2.2,
    "unhygienic": -2.7,
    "filthy": -2.9,
    "laggy": -2.2,
    "unstable": -2.4,
    "defective": -2.5,
    "rundown": -2.6,
    "deteriorating": -2.7,
    "distracting": -2.2,
    "vandalized": -2.9,
    "outdated_equipment": -2.8,
    "slow_internet": -2.4,

    # ── Operational-failure vocabulary ──
    # These were absent from the lexicon *and* from VADER's own 7,500-word
    # vocabulary, which meant a plain, unnegated complaint containing one of
    # them scored a flat 0.0 and was labelled Neutral:
    #     "The system is slow."      -> Neutral
    #     "The projector is down."   -> Neutral
    #     "The wifi is unreachable." -> Neutral
    # A sentiment engine that calls a broken system neutral is worse than no
    # engine at all, because the misclassification is invisible in the UI.
    #
    # Note the polarity convention for the "working" family: a *working*
    # system is a good thing, so the bare word is positive and the negation
    # pre-pass does the flipping. "The wifi is not working" therefore lands
    # negative, which is the only way that sentence can be handled by one
    # rule instead of two overlapping ones.
    "slow": -1.8,
    "slower": -2.0,
    "quick": 1.4,
    "fast": 1.9,
    "responsive": 2.0,
    "stable": 1.8,
    "working": 1.5,
    "works": 1.5,
    "worked": 1.4,
    "functional": 2.2,
    "down": -2.0,
    "offline": -1.8,
    "unreachable": -2.5,
    "disconnected": -2.3,
    "crashing": -2.6,
    "crashes": -2.6,
    "crashed": -2.6,
    "hanging": -2.2,
    "buffering": -2.2,
    "buffers": -2.2,
    "glitch": -2.1,
    "glitchy": -2.4,
    "unusable": -3.0,
    "unreliable": -2.8,
    "inaccessible": -2.7,
    "malfunction": -2.8,
    "malfunctions": -2.8,
    "unserviceable": -3.1,
    "nonfunctional": -2.9,
    "non-functional": -2.9,
    "poorly": -1.6,
    "poor-quality": -2.4,
    "poor_quality": -2.4,
    "overpriced": -2.5,
    "expensive": -1.4,
    "costly": -1.3,
    "time-consuming": -2.0,
    "time_consuming": -2.0,
    "cumbersome": -2.2,
    "tedious": -2.0,
    "complicated": -1.6,
    "cluttered": -1.9,
    "untidy": -1.8,
    "crowded": -1.9,
    "congested": -2.0,
    "occupied": -1.2,
    "full": -0.9,
    "late": -1.6,
    "transparent": 1.8,
    "qualified": 1.8,
    "competent": 2.0,
    "sufficient": 1.5,
    "ample": 1.6,
    "upgrade": 1.4,
    "upgrades": 1.4,

    # Scarcity and frequency adverbs. These are polarity-neutral on their own
    # — "often" and "rarely" carry no sign — but they are the hinge of a
    # negated complaint ("hardly any sockets", "rarely works"), so they are
    # listed here at a magnitude small enough that a bare occurrence cannot
    # swing the label while a negated one still registers.
    "hardly": -0.5,
    "barely": -0.5,
    "scanty": -2.0,
    "scarce": -2.0,
    "frequently": -0.4,
    "often": -0.3,
    "sometimes": -0.2,
    "occasionally": -0.2,
    "rarely": -0.4,
    "seldom": -0.5,

    # ── General Academic Sentiment & Colloquial Modifiers ──
    "top_notch": 3.2,
    "top-notch": 3.2,
    "superb": 3.0,
    "seamless": 2.5,
    "flawless": 3.0,
    "stress-free": 2.4,
    "highly_recommended": 3.0,
    "value_for_money": 2.5,
    "sound": 2.2,
    "excellent": 3.0,
    "outstanding": 3.1,
    "impressive": 2.8,
    "remarkable": 2.9,
    "commendable": 2.7,
    "satisfactory": 1.8,
    "adequate": 1.5,
    "decent": 1.6,
    "needs_improvement": -2.3,
    "needs_urgent_attention": -3.0,
    "room_for_improvement": -1.5,
    "not_up_to_standard": -2.6,
    "carry_over": -1.6,
    "choked_timetable": -2.4,
    "missing_script": -3.2,
    "delayed_results": -2.7,
    "stressful": -2.4,
    "hectic": -2.0,
    "frustrating": -2.7,
    "painful": -2.5,
    "annoying": -2.3,
    "terrible": -3.2,
    "horrible": -3.3,
    "pathetic": -3.2,
    "useless": -3.2,
    "headache": -2.4,
    "mess": -2.5,
    "shambles": -2.9,
    "struggle": -2.0,
    "nightmare": -3.2,
    "disappointing": -2.7,
    "unacceptable": -3.0,
    "problematic": -2.2,
    "challenging": -1.5,
    "mediocre": -2.0,
    "subpar": -2.3,
    "lacking": -2.1,
    "abysmal": -3.3,
    "dreadful": -3.1,
    "appalling": -3.2,
    "catastrophic": -3.4,
}


# ══════════════════════════════════════════════════════════════════════
#  2. MULTI-WORD EXPRESSION (MWE) CANONICAL REWRITER
# ══════════════════════════════════════════════════════════════════════

# Ordered longest-pattern-first. `re.sub` replaces the first match and keeps
# scanning, so a short pattern listed above a longer one it overlaps would
# consume the overlap and prevent the longer idiom from ever matching — the
# ordering below is load-bearing, not cosmetic. `sorted()` on the pattern's
# literal source length keeps it correct automatically if a rule is added.
def _mwe(pattern: str, replacement: str) -> Tuple[re.Pattern, str]:
    return (re.compile(pattern, re.I), replacement)


_MWE_RULES: List[Tuple[str, str]] = [
    # 4 words
    (_mwe(r"\bneeds\s+serious\s+improvement\b", "needs_urgent_attention"), None),
    (_mwe(r"\bstate\s+of\s+the\s+art\b", "state_of_the_art"), None),
    (_mwe(r"\bnot\s+enough\s+computers?\b", "not_enough_computers"), None),
    (_mwe(r"\bself\s+explanatory\b", "self_explanatory"), None),
    (_mwe(r"\bthought\s+provoking\b", "thought_provoking"), None),
    (_mwe(r"\beasy\s+to\s+understand\b", "easy_to_understand"), None),
    (_mwe(r"\bnot\s+up\s+to\s+standard\b", "not_up_to_standard"), None),
    (_mwe(r"\broom\s+for\s+improvement\b", "room_for_improvement"), None),
    (_mwe(r"\bdifficult\s+to\s+understand\b", "difficult_to_understand"), None),
    # 3 words
    (_mwe(r"\bneeds\s+urgent\s+attention\b", "needs_urgent_attention"), None),
    (_mwe(r"\bpoorly\s+organized\b", "poorly_organized"), None),
    (_mwe(r"\bpoorly\s+organised\b", "poorly_organized"), None),
    (_mwe(r"\bhard\s+to\s+follow\b", "hard_to_follow"), None),
    (_mwe(r"\boutdated\s+equipment\b", "outdated_equipment"), None),
    (_mwe(r"\bpoor\s+ventilation\b", "poor_ventilation"), None),
    (_mwe(r"\bhighly\s+recommended\b", "highly_recommended"), None),
    (_mwe(r"\bhand[sz]\s+on\b", "hands_on"), None),
    (_mwe(r"\bneeds\s+improvement\b", "needs_improvement"), None),
    (_mwe(r"\bvalue\s+for\s+money\b", "value_for_money"), None),
    (_mwe(r"\bchoked\s+timetable\b", "choked_timetable"), None),
    (_mwe(r"\bjob\s+ready\b", "job_ready"), None),
    (_mwe(r"\btheory\s+heavy\b", "theory_heavy"), None),
    (_mwe(r"\bhard\s+to\s+understand\b", "hard_to_understand"), None),
    (_mwe(r"\bwell\s+organized\b", "well_organized"), None),
    (_mwe(r"\bwell\s+organised\b", "well_organized"), None),
    (_mwe(r"\bbarely\s+functional\b", "barely_functional"), None),
    (_mwe(r"\bindustry\s+standard\b", "industry_standard"), None),
    (_mwe(r"\bdelayed\s+results?\b", "delayed_results"), None),
    (_mwe(r"\beasy\s+to\s+grasp\b", "easy_to_grasp"), None),
    (_mwe(r"\bup\s+to\s+date\b", "up_to_date"), None),
    # 2 words
    (_mwe(r"\bindustry\s+aligned\b", "industry_aligned"), None),
    (_mwe(r"\bwell\s+structured\b", "well_structured"), None),
    (_mwe(r"\bwell\s+explained\b", "well_explained"), None),
    (_mwe(r"\bwell\s+delivered\b", "well_delivered"), None),
    (_mwe(r"\bwell\s+equipped\b", "well_equipped"), None),
    (_mwe(r"\bbroken\s+projector\b", "broken_projector"), None),
    (_mwe(r"\bwaste\s+of\s+time\b", "waste_of_time"), None),
    (_mwe(r"\breal\s+world\b", "real_world"), None),
    (_mwe(r"\bpower\s+outage\b", "power_outage"), None),
    (_mwe(r"\bslow\s+internet\b", "slow_internet"), None),
    (_mwe(r"\bcarry\s+over\b", "carry_over"), None),
    (_mwe(r"\bno\s+light\b", "no_light"), None),
    (_mwe(r"\bno\s+practicals?\b", "no_practicals"), None),
    (_mwe(r"\bpoor\s+network\b", "poor_network"), None),
    (_mwe(r"\btop\s+notch\b", "top_notch"), None),
    (_mwe(r"\bout\s+of\s+date\b", "out_of_date"), None),
    (_mwe(r"\btoo\s+fast\b", "too_fast"), None),
    (_mwe(r"\btoo\s+slow\b", "too_slow"), None),
    (_mwe(r"\bmissing\s+scripts?\b", "missing_script"), None),
    (_mwe(r"\b(?:he|she|they)\s+tries?\b", "lecturer_tries"), None),
]

# NOTE: "not clear" and "not helpful" are deliberately NOT rewritten here.
# Rewriting them to `not_clear` / `not_helpful` stripped the literal negator
# out of the text, which meant VADER's own negation window could not see it —
# and the injected `not_*` lexicon entries then penalised the same phrase a
# *third* time on top of the custom pre-pass. Leaving the words intact lets
# the pre-pass handle them (section 3) exactly once.
MWE_PHRASE_MAP: List[Tuple[re.Pattern, str]] = [rule for rule, _ in _MWE_RULES]

# ── Negation tokens that flip the polarity of the next domain term ──
_NEGATORS = frozenset({"not", "never", "no", "barely", "hardly", "neither",
                        "nothing", "nowhere", "nobody", "none", "nor",
                        "cannot", "can't", "won't", "didn't", "doesn't",
                        "isn't", "aren't", "wasn't", "weren't", "haven't",
                        "hasn't", "hadn't", "without", "lack", "lacking"})

# ── Intensifiers that amplify compound score magnitude ──
_INTENSIFIERS = frozenset({"very", "extremely", "absolutely", "completely",
                            "totally", "utterly", "deeply", "incredibly",
                            "immensely", "profoundly", "severely", "terribly",
                            "awfully", "exceptionally", "remarkably", "highly",
                            "truly", "really", "seriously", "genuinely"})

# ── Downgraders that weaken signals ──
_DOWNGRADERS = frozenset({"slightly", "somewhat", "a_bit", "a_little",
                           "kind_of", "sort_of", "fairly", "rather",
                           "mostly", "generally", "usually", "often"})


def preprocess_text(raw_text: str) -> str:
    """Rewrites multi-word expressions into canonical single tokens.

    The result is *not* the text that is scored: the score is computed from the
    raw text so the negation and intensifier passes still see the original
    words, and this canonical form is used for the lexicon look-up.
    """
    if not raw_text:
        return ""
    text = str(raw_text)
    for pattern, replacement in MWE_PHRASE_MAP:
        text = pattern.sub(replacement, text)
    return text


# ══════════════════════════════════════════════════════════════════════
#  3. NEGATION-AWARE LEXICON SCORING PRE-PASS
# ══════════════════════════════════════════════════════════════════════

def _token_stream(text: str) -> List[str]:
    return [t for t in re.split(r"[\s,.!?;:()\[\]\"'`]+", text.lower()) if t]


def _vader_knows(term: str, base_keys) -> bool:
    """True when VADER's own lexicon already contains `term`.

    The pre-pass and VADER both implement negation, so applying both to the
    same word penalises it twice ("not helpful" once used to land near -0.95).
    VADER's negation window is a core part of its own scoring and cannot be
    switched off, so the only way to count once is for this pass to leave any
    term VADER already knows strictly alone.
    """
    if base_keys is None:
        return False
    return term in base_keys


def _apply_negation_and_intensity(
    raw_text: str,
    base_compound: float,
    mwe_text: str | None = None,
    vader_base_keys=None,
) -> Tuple[float, float]:
    """Applies the domain-aware negation and intensifier passes.

    Returns `(adjusted_compound, intensity_multiplier)`.

    Two passes run over two views of the same sentence, because each pass
    needs a different view:

    * **Negation** reads the *raw* tokens. The MWE rewriter deliberately leaves
      "not helpful" and "not clear" alone, and it swallows the negator in cases
      like "not well equipped" -> "not well_equipped" — so the literal
      negator is only reliably visible before rewriting.
    * **Intensifiers** read the *canonical* tokens as well, because the
      intensifier almost never sits next to a lexicon word in the raw text:
      "very needs improvement" is `[very, needs, improvement]` raw, and none of
      those three are domain terms, so the boost silently never fired. The
      canonical form `[very, needs_improvement]` does fire.

    A term VADER's own lexicon already knows is skipped by the negation pass —
    see `_vader_knows`.

    The negation window is 5 tokens (up from 3) so that complex sentences
    like "the lectures were not particularly well organised" still flip the
    polarity of the domain term. The window is capped at 5 to avoid
    over-negating when a sentence contains multiple clauses.
    """
    negation_adjustment = 0.0
    intensity_mult = 1.0
    negated_terms: set[str] = set()

    for tokens, allow_negation in ((_token_stream(raw_text), True),
                                   (_token_stream(mwe_text or raw_text), False)):
        for idx, token in enumerate(tokens):
            clean = token.strip(string.punctuation)
            if not clean:
                continue
            valence = ACADEMIC_DOMAIN_LEXICON.get(clean)
            if valence is None:
                continue

            # Look back up to 5 tokens for a negator (expanded from 3 for
            # complex sentences with intervening adverbs).
            preceding = [tokens[j].strip(string.punctuation)
                         for j in range(max(0, idx - 5), idx)]

            if allow_negation and clean not in negated_terms:
                if any(neg in preceding for neg in _NEGATORS):
                    if _vader_knows(clean, vader_base_keys):
                        continue
                    negated_terms.add(clean)
                    # Scaled in `_compose` below; kept as a raw valence delta.
                    negation_adjustment -= valence * 1.2
                    continue  # don't also amplify a negated term

            # Look back 3 tokens for an intensifier (expanded from 2).
            prec2 = [tokens[j].strip(string.punctuation)
                     for j in range(max(0, idx - 3), idx)]
            if any(it in prec2 for it in _INTENSIFIERS):
                intensity_mult = max(intensity_mult, 1.25)
            elif any(dg in prec2 for dg in _DOWNGRADERS):
                intensity_mult = min(intensity_mult, 0.85)

    # Exclamation marks read as enthusiasm.
    exclamation_count = raw_text.count("!")
    if exclamation_count:
        intensity_mult = min(1.35, intensity_mult + min(3, exclamation_count) * 0.04)

    # Shouting reads as emphasis.
    caps_words = sum(1 for w in raw_text.split() if len(w) > 2 and w.isupper())
    if caps_words:
        intensity_mult = min(1.35, intensity_mult + min(4, caps_words) * 0.03)

    adjusted = base_compound * intensity_mult + (negation_adjustment * 0.18)
    return round(max(-1.0, min(1.0, adjusted)), 4), round(intensity_mult, 3)


def _rebase_polarity(scores: Dict[str, float], old_compound: float,
                     new_compound: float) -> Dict[str, float]:
    """Re-derives the pos/neu/neg split after the compound score was adjusted.

    Without this the three proportions still described the *un*-adjusted
    sentence, so a comment could end up labelled Negative while its breakdown
    said 80% positive.
    """
    pos = max(0.0, float(scores.get("pos", 0.0)))
    neg = max(0.0, float(scores.get("neg", 0.0)))
    neu = max(0.0, float(scores.get("neu", 0.0)))

    if abs(old_compound) < 1e-6:
        # The original was a dead heat — there is no direction to rescale
        # towards, so keep VADER's proportions.
        total = pos + neg + neu
    else:
        ratio = new_compound / old_compound
        pos, neg = pos * ratio, neg * ratio
        neu = max(0.0, 1.0 - pos - neg)
        total = pos + neg + neu
        if total <= 1e-6:  # degenerate; fall back to an all-neutral split
            return {"pos": 0.0, "neu": 1.0, "neg": 0.0}

    return {
        "pos": round(pos / total, 4),
        "neu": round(neu / total, 4),
        "neg": round(neg / total, 4),
    }


# ══════════════════════════════════════════════════════════════════════
#  4. VADER SINGLETON WITH AUGMENTED LEXICON
# ══════════════════════════════════════════════════════════════════════

try:
    import streamlit as st
    _cache_resource = st.cache_resource
except Exception:
    def _cache_resource(fn):
        _cached = None
        def _wrapper(*args, **kwargs):
            nonlocal _cached
            if _cached is None:
                _cached = fn(*args, **kwargs)
            return _cached
        return _wrapper


_VADER_LOAD_ERROR: str | None = None


@_cache_resource
def _get_vader():
    """Loads and returns an augmented VADER analyzer, or None if unavailable.

    Three separate failure modes are handled, all of which used to surface as a
    raw traceback or as a silently missing lexicon:

    1. NLTK is not installed at all.
    2. The `vader_lexicon` corpus has not been downloaded yet.
    3. The corpus is present but unreadable/corrupt, so the constructor raises
       (e.g. a `zipfile.BadZipFile` on a partially downloaded file).

    On failure the module still imports and the app still runs — the VADER path
    simply reports itself unavailable through `engine_status()`, which the admin
    dashboard renders as a visible warning rather than pretending the score is
    real.
    """
    global _VADER_LOAD_ERROR
    if SentimentIntensityAnalyzer is None:
        _VADER_LOAD_ERROR = f"NLTK is not installed ({_NLTK_IMPORT_ERROR})."
        return None

    try:
        nltk.data.find("sentiment/vader_lexicon.zip")
    except LookupError:
        try:
            ok = nltk.download("vader_lexicon", quiet=True)
        except Exception as exc:
            _VADER_LOAD_ERROR = f"NLTK download failed: {exc}"
            return None
        if not ok:
            _VADER_LOAD_ERROR = (
                "The NLTK 'vader_lexicon' corpus is not downloaded. "
                "Run: python download_nltk_data.py"
            )
            return None

    try:
        analyzer = SentimentIntensityAnalyzer()
    except Exception as exc:
        _VADER_LOAD_ERROR = f"VADER could not be initialised: {exc}"
        return None

    # Snapshot VADER's own vocabulary *before* injecting ours, so the negation
    # pass can tell which terms VADER already handles on its own.
    base_keys = frozenset(analyzer.lexicon.keys())
    analyzer.lexicon.update(ACADEMIC_DOMAIN_LEXICON)
    setattr(analyzer, "futo_base_lexicon_keys", base_keys)

    _VADER_LOAD_ERROR = None
    return analyzer


# ══════════════════════════════════════════════════════════════════════
#  5. CONTRASTIVE CONJUNCTION & CLAUSE WEIGHTING
# ══════════════════════════════════════════════════════════════════════

_CONTRAST_RE = re.compile(
    r"\b(but|however|although|though|except\s+that|except|yet|whereas|nonetheless|nevertheless)\b",
    re.I,
)


def _evaluate_clauses(text: str, analyzer: "SentimentIntensityAnalyzer") -> Tuple[float, Dict[str, float], bool]:
    """Calculates sentiment with intelligent contrastive clause weighting.
    In natural feedback, a student who says 'X, BUT Y' usually expresses their
    decisive judgment in Y.

    Also handles conditional sentences ("if X, then Y") where the main clause
    carries the sentiment, and concessive clauses ("although X, Y") where the
    main clause after the comma is the decisive one.
    """
    # Try contrastive conjunctions first (but, however, yet, although, though)
    contrast_match = _CONTRAST_RE.search(text)
    if contrast_match:
        idx = contrast_match.start()
        head = text[:idx].strip()
        tail = text[contrast_match.end():].strip()

        if head and tail:
            head_scores = analyzer.polarity_scores(head)
            tail_scores = analyzer.polarity_scores(tail)

            # Post-contrast clause receives higher recency/decisive weighting
            weighted_compound = round((head_scores["compound"] * 0.35) + (tail_scores["compound"] * 0.65), 4)

            blended_scores = {
                "pos": round(head_scores["pos"] * 0.35 + tail_scores["pos"] * 0.65, 3),
                "neg": round(head_scores["neg"] * 0.35 + tail_scores["neg"] * 0.65, 3),
                "neu": round(head_scores["neu"] * 0.35 + tail_scores["neu"] * 0.65, 3),
                "compound": weighted_compound,
            }
            return weighted_compound, blended_scores, True

    # Try conditional sentences: "if X, Y" — the main clause (Y) is decisive
    conditional_match = re.search(r"\bif\b[^,]*,?\s*(.+)", text, re.I)
    if conditional_match:
        main_clause = conditional_match.group(1).strip()
        if main_clause:
            cond_scores = analyzer.polarity_scores(main_clause)
            return cond_scores["compound"], cond_scores, True

    # No complex structure found — score the whole text
    scores = analyzer.polarity_scores(text)
    return scores["compound"], scores, False


# ══════════════════════════════════════════════════════════════════════
#  6. CALIBRATED CONFIDENCE & ASPECT SIGNAL EXTRACTION
# ══════════════════════════════════════════════════════════════════════

def _extract_cues(preprocessed_text: str) -> Tuple[List[str], List[str]]:
    """Identifies specific domain sentiment trigger terms present in the text.
    Handles both underscore-joined MWE tokens and hyphenated forms.
    """
    # Extract both whole-word tokens and underscore_joined tokens
    raw_tokens = re.findall(r"\b[\w-]+\b", preprocessed_text.lower())
    # Also build underscore-joined bigrams to catch missed MWE patterns
    bigrams = [f"{raw_tokens[i]}_{raw_tokens[i+1]}" for i in range(len(raw_tokens) - 1)]
    tokens = set(raw_tokens + bigrams)

    pos_cues = []
    neg_cues = []
    seen = set()
    for token in tokens:
        if token in seen:
            continue
        if token in ACADEMIC_DOMAIN_LEXICON:
            seen.add(token)
            val = ACADEMIC_DOMAIN_LEXICON[token]
            readable = token.replace("_", " ")
            if val > 1.0:
                pos_cues.append(readable)
            elif val < -1.0:
                neg_cues.append(readable)
    return sorted(pos_cues), sorted(neg_cues)


# ══════════════════════════════════════════════════════════════════════
#  6a. CONFIDENCE BAND & TIER LADDER
#
#  Declared here, immediately before the function that clamps to them, so
#  there is exactly one definition of each bound. The engine used to clamp
#  with two bare literals while the admin dashboard printed a third
#  hand-typed string ("48% – 99%"), so the range on screen was not
#  guaranteed to be the range actually applied.
# ══════════════════════════════════════════════════════════════════════

CONFIDENCE_FLOOR = 0.48
CONFIDENCE_CEILING = 0.99

# One tier ladder, descending, used by every confidence badge in the app.
# The engine, the student stats page and the feedback form each used to
# invent their own cut-offs, so the same 79% rendered as "Good" on one page
# and "Moderate" on another.
CONFIDENCE_TIERS: Tuple[Tuple[float, str], ...] = (
    (0.90, "Very High"),
    (0.78, "High"),
    (0.65, "Moderate"),
    (0.55, "Low"),
)
CONFIDENCE_FLOOR_TIER = "Very Low"


def confidence_tier(confidence: float) -> str:
    """Maps a 0-1 confidence value onto the shared tier ladder."""
    try:
        c = float(confidence)
    except (TypeError, ValueError):
        return CONFIDENCE_FLOOR_TIER
    for threshold, name in CONFIDENCE_TIERS:
        if c >= threshold:
            return name
    return CONFIDENCE_FLOOR_TIER


def _compute_confidence(
    compound: float,
    scores: Dict[str, float],
    text_len: int,
    intensity_mult: float = 1.0,
    contrast_detected: bool = False,
) -> float:
    """Calculates a deterministic confidence percentage.

    The result is clamped to the `CONFIDENCE_FLOOR`..`CONFIDENCE_CEILING` band
    declared in section 9, which is also what `engine_status()` reports and what
    the tier ladder is cut against. The clamp used to be written as two bare
    literals here while the status card printed a third hand-typed string, so
    the number the admin saw was not necessarily the number the engine used.

    Factors:
    - Compound intensity: stronger compound → higher confidence
    - Signal separation (pos vs neg margin): clear winner → higher confidence
    - Intensifier presence: amplifiers like "very/extremely" → slight boost
    - Text length: single words have lower confidence than full sentences
    - Contrast detection: mixed-signal sentences slightly reduce confidence
    - Neutral detection: genuinely neutral text (both pos/neg near 0) → high conf
    """
    abs_comp = abs(compound)
    pos = scores.get("pos", 0.0)
    neg = scores.get("neg", 0.0)
    neu = scores.get("neu", 1.0)

    # Separation margin between positive and negative signals
    margin = abs(pos - neg)

    # Base confidence from compound intensity
    base_conf = 0.52 + (abs_comp * 0.38)

    # Boost for clear signal separation
    if margin > 0.20:
        base_conf += 0.10
    elif margin > 0.10:
        base_conf += 0.05

    # Truly neutral text: low compound AND low pos/neg → confident "Neutral"
    if abs_comp < 0.05 and neu > 0.85 and pos < 0.08 and neg < 0.08:
        base_conf = 0.84

    # Length context (longer text provides more evidence)
    if text_len > 60:
        base_conf += 0.05
    elif text_len > 30:
        base_conf += 0.03
    elif text_len < 10:
        base_conf -= 0.05

    # Intensifier presence boosts confidence (strong language = clear signal)
    if intensity_mult > 1.2:
        base_conf += 0.04

    # Contrastive clauses are inherently mixed → slightly reduce confidence
    if contrast_detected:
        base_conf -= 0.04

    return round(min(CONFIDENCE_CEILING, max(CONFIDENCE_FLOOR, base_conf)), 2)


# ══════════════════════════════════════════════════════════════════════
#  7. RESULT CONTAINER (Backwards compatible with 3-tuple unpacking)
# ══════════════════════════════════════════════════════════════════════

class SentimentResult(tuple):
    """A tuple subclass (label, score, engine) enriched with named metadata attributes."""

    def __new__(cls, label: str, score: float, engine: str, confidence: float = 0.85,
                pos: float = 0.0, neu: float = 1.0, neg: float = 0.0,
                pos_cues: "List[str] | None" = None, neg_cues: "List[str] | None" = None,
                contrast_detected: bool = False):
        obj = super().__new__(cls, (label, score, engine))
        obj.label = label
        obj.score = score
        obj.engine = engine
        obj.confidence = confidence
        obj.pos = pos
        obj.neu = neu
        obj.neg = neg
        obj.pos_cues = pos_cues or []
        obj.neg_cues = neg_cues or []
        obj.contrast_detected = contrast_detected
        return obj

    def to_dict(self) -> Dict[str, Any]:
        return {
            "label": self.label,
            "score": self.score,
            "engine": self.engine,
            "confidence": self.confidence,
            "pos": self.pos,
            "neu": self.neu,
            "neg": self.neg,
            "pos_cues": self.pos_cues,
            "neg_cues": self.neg_cues,
            "contrast_detected": self.contrast_detected,
        }

    @property
    def compound(self) -> float:
        """Alias for score for backward compatibility."""
        return self.score

    @property
    def confidence_pct(self) -> int:
        """Confidence as an integer percentage (0-100)."""
        return int(self.confidence * 100)

    @property
    def confidence_label(self) -> str:
        """Human-readable confidence tier, from the shared `CONFIDENCE_TIERS` ladder."""
        return confidence_tier(self.confidence)


# ══════════════════════════════════════════════════════════════════════
#  8. OPTIONAL TRAINED CLASSIFIER INTEGRATION
# ══════════════════════════════════════════════════════════════════════

_PUNCT_TABLE = str.maketrans("", "", string.punctuation.replace("_", ""))

# Identifies the feature space `_tokenize`/`_features` produce. A `.pkl` whose
# `meta["feature_spec"]` differs was built against different features and
# would mispredict silently, so `_get_trained_model` refuses it. Bump this
# whenever the tokenisation changes.
FEATURE_SPEC = "v1:mwe-unigram-bigram"

_MODEL_LOAD_ERROR: str | None = None

# mtime of the `.pkl` this process last loaded, so `model_is_stale` can tell a
# model that appeared later from the one already in memory. 0.0 means "never
# loaded", which compares as stale against any file that exists.
_MODEL_LOADED_MTIME: float = 0.0


def _tokenize(text: str) -> List[str]:
    """Preprocesses MWEs and extracts unigram + bigram feature tokens.
    NOTE: underscores are PRESERVED so MWE tokens like 'hands_on' remain
    as unified semantic features for the classifier.
    """
    prep = preprocess_text(text)
    # Replace punctuation except underscores (which join MWE tokens)
    clean = str(prep).lower().translate(_PUNCT_TABLE)
    unigrams = [t for t in re.split(r"\s+", clean) if t]
    bigrams = [f"{unigrams[i]}_{unigrams[i+1]}" for i in range(len(unigrams) - 1)]
    return unigrams + bigrams


def _features(tokens: List[str]) -> Dict[str, bool]:
    return {f"contains({w})": True for w in tokens}


@_cache_resource
def _load_trained_model():
    """Reads and unpickles the `.pkl`. Cached; see `_get_trained_model`.

    A `.pkl` produced on a different machine, a different Python, or a
    different scikit-learn/NLTK version is guaranteed to raise during
    `pickle.load` — sklearn and NLTK both validate library versions on load.
    The previous version swallowed that as a bare `except Exception: return
    None`, so an admin who had trained a model was told "no model" with no
    explanation and no clue that it existed. `_MODEL_LOAD_ERROR` now carries the
    reason and `engine_status()` surfaces it, so a stale `.pkl` reads as
    "re-trained against this environment" instead of a mystery.
    """
    global _MODEL_LOAD_ERROR, _MODEL_LOADED_MTIME
    if not os.path.exists(MODEL_PATH):
        _MODEL_LOAD_ERROR = None
        _MODEL_LOADED_MTIME = 0.0
        return None
    try:
        _MODEL_LOADED_MTIME = os.path.getmtime(MODEL_PATH)
    except OSError:
        _MODEL_LOADED_MTIME = 0.0
    try:
        with open(MODEL_PATH, "rb") as fh:
            model = pickle.load(fh)
    except Exception as exc:
        # A `.pkl` that fails to unpickle fails in wildly misleading ways. A
        # truncated file makes the interpreter read past the end of the
        # stream and raise `MemoryError`; a partial header raises
        # `UnpicklingError`; one written by another Python raises
        # `ModuleNotFoundError`; and one written against a different
        # scikit-learn raises `AttributeError` about a missing estimator
        # attribute. Reporting the raw exception name here produced things
        # like "could not be loaded (MemoryError: )", which an admin cannot
        # act on, so the causes are grouped into one actionable sentence and
        # the raw detail is kept behind it.
        if isinstance(exc, (FileNotFoundError, IsADirectoryError, PermissionError)):
            detail = f"{type(exc).__name__}: {exc}"
        else:
            detail = (f"the file is truncated, corrupt, or was written by a different "
                      f"Python/scikit-learn/NLTK version ({type(exc).__name__})")
        _MODEL_LOAD_ERROR = (
            f"{os.path.basename(MODEL_PATH)} could not be loaded — {detail}. "
            "Re-run train_model.py in this environment."
        )
        return None

    if not isinstance(model, dict) or "classifier" not in model:
        _MODEL_LOAD_ERROR = (
            f"{os.path.basename(MODEL_PATH)} is not a valid model bundle. Re-run train_model.py."
        )
        return None

    # A model built on a different feature space would silently mispredict
    # rather than fail, so treat a mismatch as "no usable model".
    spec = (model.get("meta") or {}).get("feature_spec")
    if spec and spec != FEATURE_SPEC:
        _MODEL_LOAD_ERROR = (
            f"{os.path.basename(MODEL_PATH)} was trained on feature spec '{spec}' but this "
            f"build uses '{FEATURE_SPEC}'. Re-run train_model.py."
        )
        return None

    _MODEL_LOAD_ERROR = None
    return model


def _get_trained_model():
    """The trained model, reloading it if the file on disk has changed.

    A thin wrapper around the cached `_load_trained_model`. The wrapper exists
    because `@st.cache_resource` gives no way to invalidate a single entry from
    the outside without clearing the whole cache, and the whole cache holds the
    VADER singleton too — clearing that on every page render would rebuild the
    analyzer constantly.

    The staleness check is one `stat`. Without it, a `.pkl` that appears after
    the process first read is invisible: an admin trains a model from inside the
    app (or drops one in over SSH while the app runs), the sidebar keeps naming
    the old engine, every label still comes from the rule pipeline, and nothing
    anywhere reports an error. Same failure shape as the silent hash upgrade —
    the action looks like it happened and nothing downstream changed.
    """
    if model_is_stale():
        clear = getattr(_load_trained_model, "clear", None)
        if callable(clear):
            clear()
        global _MODEL_LOADED_MTIME
        try:
            _MODEL_LOADED_MTIME = os.path.getmtime(MODEL_PATH)
        except OSError:
            _MODEL_LOADED_MTIME = 0.0
    return _load_trained_model()


def invalidate_trained_model() -> bool:
    """Drops the cached `.pkl` so the next read reloads from disk.

    Returns True if Streamlit's cache was actually cleared.

    `_load_trained_model` is `@st.cache_resource`, so it holds whatever it first
    read for the life of the process. Without this, an admin who trains a model
    from inside the app gets the new `.pkl` on disk and the *old* model in use,
    with no error anywhere — the status card still names the previous engine and
    every label is still the rule engine's. That is the same class of defect as
    the original silent-hash-upgrade: the action appears to have happened and
    the thing it was supposed to change did not change.

    Only the model's own entry is cleared. The VADER singleton shares
    `st.cache_resource` but is a different function, so it keeps its instance —
    see `_get_trained_model`'s note on why that distinction matters.

    Both decorators are handled. `st.cache_resource` exposes `.clear()`; the
    no-Streamlit fallback in this module does not, so the recorded mtime is
    reset instead, which is what `model_is_stale` keys on.
    """
    global _MODEL_LOAD_ERROR, _MODEL_LOADED_MTIME
    clear = getattr(_load_trained_model, "clear", None)
    _MODEL_LOAD_ERROR = None
    _MODEL_LOADED_MTIME = 0.0
    if callable(clear):
        clear()
        return True
    # Fallback decorator (no Streamlit import): nothing to clear, but the
    # recorded mtime is reset, so the next read picks the new file up.
    return False


def model_is_stale() -> bool:
    """True if the `.pkl` on disk is newer than the copy this process loaded.

    `_get_trained_model` is cached for the life of the process, so it is blind
    to a model that appeared *after* that first read — trained in another
    Streamlit session, dropped in by a scheduled job, or copied in over SSH
    while the app was running. `invalidate_trained_model` covers the common
    case (train from this page, same process); this covers the rest, at the
    cost of one `stat` per call.
    """
    try:
        if not os.path.exists(MODEL_PATH):
            return False
        return os.path.getmtime(MODEL_PATH) > _MODEL_LOADED_MTIME
    except OSError:
        return False


def _classify_with_model(model: dict, text: str) -> str:
    """Returns the trained model's label for `text`, across both backends.

    Two backends are supported, distinguished by `model["backend"]`:

    * `"nltk"`  — a `NaiveBayesClassifier` that takes the hand-rolled
      `{"contains(token)": True}` feature dict from `_features()`.
    * `"sklearn"` — a `Pipeline` ending in a `LabelEncoder`-wrapped
      classifier, which takes raw text.

    The sklearn branch stores the *raw* `Pipeline` rather than a wrapper
    object. A wrapper class defined inside `train_model.py` would be
    unpicklable from any other module — pickle records classes by
    `module.QualName`, and a class nested in a function has a `QualName`
    containing `<locals>`, which cannot be looked up again on load. The model
    therefore shipped with the app raised `NotImplementedError` on first use
    and every comment silently fell back to plain VADER.
    """
    backend = model.get("backend", "nltk")
    classifier = model["classifier"]

    if backend == "sklearn":
        labels = classifier.predict([text])
        raw = labels[0]
        try:
            return classifier.named_steps["label_encoder"].inverse_transform([raw])[0]
        except Exception:
            return str(raw)

    tokens = _tokenize(text)
    return classifier.classify(_features(tokens))


# ══════════════════════════════════════════════════════════════════════
#  9. PUBLIC API
# ══════════════════════════════════════════════════════════════════════

def estimate_confidence_from_score(score: float) -> float:
    """Fallback confidence for text that has no stored `sentiment_confidence`.

    Used when re-analysing a comment that predates the confidence column, so
    those rows get the same band as everything else instead of the previous
    ad-hoc 0.52 floor.
    """
    try:
        return round(max(CONFIDENCE_FLOOR,
                         min(CONFIDENCE_CEILING, CONFIDENCE_FLOOR + abs(float(score)) * 0.5)),
                     2)
    except (TypeError, ValueError):
        return CONFIDENCE_FLOOR


def engine_status() -> dict:
    """Returns engine configuration and diagnostics for the administrative portal."""
    global _VADER_LOAD_ERROR

    model = _get_trained_model()
    vader = _get_vader()
    meta = model.get("meta") if isinstance(model, dict) else None

    engine = "Unavailable"
    if vader is not None:
        engine = "VADER Academic Pro"
    if model is not None and meta:
        engine = meta.get("engine_type", "Supervised Classifier")

    problems = []
    if _VADER_LOAD_ERROR:
        problems.append(_VADER_LOAD_ERROR)
    if _MODEL_LOAD_ERROR:
        problems.append(_MODEL_LOAD_ERROR)

    return {
        "vader_available": vader is not None,
        "engine_name": engine,
        "domain_lexicon_terms": len(ACADEMIC_DOMAIN_LEXICON),
        "mwe_rules_count": len(MWE_PHRASE_MAP),
        "negation_tokens": len(_NEGATORS),
        "intensifier_tokens": len(_INTENSIFIERS),
        "trained_model_available": model is not None,
        "trained_model_meta": meta,
        "trained_model_backend": model.get("backend") if isinstance(model, dict) else None,
        "active_engine": engine,
        # Derived from the constants the engine actually clamps to, instead of
        # a string literal that was still being printed when a trained model
        # set every confidence to the model's own accuracy figure.
        "confidence_range": f"{CONFIDENCE_FLOOR:.0%} – {CONFIDENCE_CEILING:.0%}",
        "confidence_tiers": [f"{name} ≥ {thr:.0%}" for thr, name in CONFIDENCE_TIERS],
        "nltk_import_error": str(_NLTK_IMPORT_ERROR) if _NLTK_IMPORT_ERROR else None,
        # Non-empty means a subsystem is degraded; the admin dashboard renders
        # this as a visible warning instead of a silently wrong number.
        "engine_problems": problems,
    }


def analyze_sentiment(text: str) -> SentimentResult:
    """Analyzes text sentiment with domain lexicon augmentation, MWE parsing,
    negation-aware pre-pass, intensifier detection, and contrastive clause resolution.

    A trained model, when present, overrides **only the label**. The numeric
    score, the polarity proportions, the cues and the confidence always come
    from the same rule pipeline, so a comment scores identically whether or not
    a `.pkl` happens to be on disk — previously the trained path skipped the
    negation/intensifier passes and returned a confidence equal to the model's
    training accuracy, which made one comment's numbers change just because
    someone retrained a model.

    Returns a SentimentResult (unpackable as `label, score, engine`).
    """
    raw_text = str(text or "").strip()
    if not raw_text:
        return SentimentResult("Neutral", 0.0, "vader_academic_pro", confidence=1.0,
                               pos=0.0, neu=1.0, neg=0.0)

    # Step 1: Preprocess multi-word expressions into canonical tokens
    mwe_text = preprocess_text(raw_text)
    pos_cues, neg_cues = _extract_cues(mwe_text)

    # Step 2: the shared rule pipeline — always runs, and always produces the
    # score, the proportions, the cues and the confidence.
    vader = _get_vader()
    if vader is None:
        # No rule engine available: return a clearly-labelled inert result
        # rather than a plausible-looking score of zero.
        return SentimentResult("Neutral", 0.0, "unavailable", confidence=0.0,
                               pos=0.0, neu=1.0, neg=0.0)

    compound, scores, contrast_found = _evaluate_clauses(mwe_text, vader)
    base_compound = compound
    compound, intensity_mult = _apply_negation_and_intensity(
        raw_text, compound, mwe_text=mwe_text,
        vader_base_keys=getattr(vader, "futo_base_lexicon_keys", None),
    )
    scores = _rebase_polarity(scores, base_compound, compound)
    scores["compound"] = compound

    confidence = _compute_confidence(
        compound, scores, len(raw_text),
        intensity_mult=intensity_mult,
        contrast_detected=contrast_found,
    )

    # Step 3: Calibrated decision boundary
    if compound >= 0.05:
        label = "Positive"
    elif compound <= -0.05:
        label = "Negative"
    else:
        label = "Neutral"

    engine = "vader_academic_pro"

    # Step 4: the trained model, if usable, replaces the label only.
    model = _get_trained_model()
    if model is not None:
        try:
            label = _classify_with_model(model, raw_text)
            engine = (model.get("meta") or {}).get(
                "engine_type", "trained_classifier")
        except Exception as exc:
            # Keep the rule-based result and say so in the engine name, so the
            # degradation is visible on the record rather than hidden.
            engine = f"vader_academic_pro (model error: {type(exc).__name__})"

    return SentimentResult(
        label=label,
        score=compound,
        engine=engine,
        confidence=confidence,
        pos=scores.get("pos", 0.0),
        neu=scores.get("neu", 1.0),
        neg=scores.get("neg", 0.0),
        pos_cues=pos_cues,
        neg_cues=neg_cues,
        contrast_detected=contrast_found,
    )


def sentiment_label(text: str) -> str:
    """Returns only the sentiment label string ('Positive' | 'Neutral' | 'Negative')."""
    return analyze_sentiment(text).label


def sentiment_breakdown(text: str) -> dict:
    """Returns a full breakdown dict suitable for displaying in the UI.
    Convenience wrapper around analyze_sentiment().to_dict() + formatted strings.
    """
    r = analyze_sentiment(text)
    return {
        **r.to_dict(),
        "confidence_pct": r.confidence_pct,
        "confidence_label": r.confidence_label,
        "pos_pct": round(r.pos * 100, 1),
        "neu_pct": round(r.neu * 100, 1),
        "neg_pct": round(r.neg * 100, 1),
    }
