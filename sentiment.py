"""
sentiment.py
------------
Sentiment for FUTO IFT feedback, derived from the student's rating.

Why this module is small
------------------------
Earlier versions ran the written comment through NLTK's VADER analyser and let
its verdict stand beside the rating. That produced the contradiction this
replaces: a student ticking 4/5 and typing "the lecturer is good but the slides
are outdated" saw a positive star rating next to a negative sentiment chip,
because a general-purpose English lexicon had no idea what a concessive clause
about laboratories means.

Both sources of the disagreement are now gone:

  * **VADER and the NLTK dependency** — removed. The only opinion in the system
    is the star control.
  * **The free-text comment box** — removed from every feedback form. A rating
    on a 1-5 scale is an explicit, unambiguous, comparable judgement made
    through the same control for every submission. Prose is not, and a system
    that averages two disagreeing answers to one question has no answer.

The rule
--------
    1 - 2   Poor / Fair        -> Negative
    3       Good (average)     -> Neutral
    4 - 5   Very Good/Excellent-> Positive

There is no threshold to tune, no model file, no corpus download, and nothing
that can be unavailable: the thresholds below are integers, and the module
imports only the standard library.

The structured checkbox answers in each category (challenges flagged, courses
rated, facilities affected) are *not* sentiment. They are kept, and they are
what the administrative breakdowns are built from — see `full_dashboard` and
`decision_insights`.

Database columns `comment`, `sentiment_score`, `sentiment_confidence` and
`sentiment_cues` are left in place and still read, so submissions already on
disk keep their history. Nothing writes to them for new submissions.
"""

from __future__ import annotations

from typing import Any, Dict

# ── The thresholds ────────────────────────────────────────────────────
# Declared once, at module level, and read by `label_from_rating`. A second
# copy of these numbers anywhere else is how a dashboard ends up showing a
# different band from the one the engine applied.
NEGATIVE_MAX = 2
NEUTRAL = 3
POSITIVE_MIN = 4

RATING_LABELS: Dict[int, str] = {
    1: "Poor",
    2: "Fair",
    3: "Good",
    4: "Very Good",
    5: "Excellent",
}

# Recorded on every row, so the administrative diagnostics and the stored
# column can never report different engines for the same version.
ENGINE_NAME = "rating_threshold_engine"

# What a human reads on screen. `ENGINE_NAME` is a storage contract — rows
# already on disk carry it, and renaming it would split history — so the
# underscores are translated at display time instead, in exactly one place.
ENGINE_DISPLAY_NAME = "rating threshold engine"


def display_engine_name(name) -> str:
    """The on-screen form of a stored engine name.

    Anything unrecognised (including None) degrades to the current engine's
    display name rather than printing a raw constant or "None".
    """
    text = str(name or "").strip()
    if text == ENGINE_NAME:
        return ENGINE_DISPLAY_NAME
    return text.replace("_", " ") if text else ENGINE_DISPLAY_NAME

POSITIVE_RATING_COLOR = "#10b981"
NEGATIVE_RATING_COLOR = "#ef4444"
NEUTRAL_RATING_COLOR = "#f59e0b"


def label_from_rating(rating) -> str | None:
    """The sentiment a rating implies, or None when the rating is unusable.

    None means the value could not be read as a 1-5 rating — a missing value on
    a legacy row, for instance — and the caller should fall back rather than
    guess.
    """
    try:
        r = int(round(float(rating)))
    except (TypeError, ValueError):
        return None
    if r <= NEGATIVE_MAX:
        return "Negative"
    if r >= POSITIVE_MIN:
        return "Positive"
    return "Neutral"


def rating_label(rating) -> str:
    """The word under a set of stars: Poor / Fair / Good / Very Good / Excellent."""
    try:
        return RATING_LABELS.get(int(round(float(rating))), "—")
    except (TypeError, ValueError):
        return "—"


def normalize_rating(value, fallback: int = NEUTRAL) -> int:
    """Clamps anything into the 1-5 range, so no caller can store a 0 or a 6."""
    try:
        r = int(round(float(value)))
    except (TypeError, ValueError):
        return fallback
    return max(1, min(5, r))


def label_color(label: str) -> str:
    return {
        "Positive": POSITIVE_RATING_COLOR,
        "Negative": NEGATIVE_RATING_COLOR,
    }.get(label, NEUTRAL_RATING_COLOR)


# ══════════════════════════════════════════════════════════════════════
#  CONFIDENCE BAND & TIER LADDER
#
#  Confidence now describes how cleanly a rating maps onto a band — not how
#  confidently a piece of prose was read. A rating is never ambiguous, so this
#  is effectively fixed; it is kept because the tier badges are rendered on the
#  student's own statistics page and the numbers have to keep coming from one
#  place rather than from a literal on each page.
# ══════════════════════════════════════════════════════════════════════

CONFIDENCE_FLOOR = 0.90
CONFIDENCE_CEILING = 0.99

CONFIDENCE_TIERS = (
    (0.97, "Certain"),
    (0.94, "High"),
    (0.90, "Good"),
)
CONFIDENCE_FLOOR_TIER = "Good"


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


def rating_confidence(rating) -> float:
    """Confidence for a rating-derived label.

    A rating sits exactly on a threshold or a whole band away from it, so this
    is deliberately a flat value rather than a calculation. Anything else would
    imply precision that a 1-5 control does not carry.
    """
    return CONFIDENCE_CEILING if label_from_rating(rating) is not None else CONFIDENCE_FLOOR


def estimate_confidence_from_score(score: float) -> float:
    """Kept for callers that still pass a stored score.

    Scores are no longer produced, so this exists only so historical rows and
    any surviving call site get a valid band instead of an exception.
    """
    try:
        s = float(score)
    except (TypeError, ValueError):
        return CONFIDENCE_FLOOR
    return round(min(CONFIDENCE_CEILING, CONFIDENCE_FLOOR + abs(s) * 0.09), 2)


# ══════════════════════════════════════════════════════════════════════
#  RESULT CONTAINER
# ══════════════════════════════════════════════════════════════════════

class SentimentResult(tuple):
    """(label, score, engine) with the breakdown attached as attributes.

    Still a 3-tuple so every existing `label, score, engine = ...` unpack keeps
    working. `score` is the rating placed on -1.0 .. 1.0, which keeps the
    existing progress bars and colour scales meaningful:
    1 -> -1.0, 2 -> -0.5, 3 -> 0.0, 4 -> +0.5, 5 -> +1.0.
    """

    # No __slots__: this is a tuple subclass, and `__slots__ = ()` removes the
    # instance __dict__ that the attribute assignments below need.
    def __new__(cls, label: str, score: float, engine: str, confidence: float = 0.99,
                pos: float = 0.0, neu: float = 1.0, neg: float = 0.0,
                rating: "int | None" = None):
        obj = super().__new__(cls, (label, score, engine))
        obj.label = label
        obj.score = score
        obj.engine = engine
        obj.confidence = confidence
        obj.pos = pos
        obj.neu = neu
        obj.neg = neg
        obj.rating = rating
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
            "rating": self.rating,
        }

    @property
    def compound(self) -> float:
        """Alias for score, kept because callers and stored rows use both names."""
        return self.score

    @property
    def confidence_pct(self) -> int:
        return int(self.confidence * 100)

    @property
    def confidence_label(self) -> str:
        return confidence_tier(self.confidence)


# ══════════════════════════════════════════════════════════════════════
#  PUBLIC API
# ══════════════════════════════════════════════════════════════════════

def rating_to_score(rating) -> float:
    """Places a 1-5 rating on -1.0 .. 1.0 for the existing visual scales."""
    r = normalize_rating(rating)
    return round((r - 3) / 2.0, 2)


def _split_from_label(label: str) -> Dict[str, float]:
    """A 100% one-sided split, so the donut chart reads as decisive.

    Half the circle rather than all of it: a full disc implies the other
    polarity was measured and found absent, which is not what a 5-star rating
    says. The empty half reads as "not opposed", which is what it means.
    """
    half = {"pos": 0.0, "neu": 0.0, "neg": 0.0}
    half[{"Positive": "pos", "Negative": "neg"}.get(label, "neu")] = 0.5
    return half


def analyze_sentiment(text=None, rating=None) -> SentimentResult:
    """Returns the sentiment implied by `rating`.

    `text` is accepted and ignored. It is the first positional parameter, so
    call sites written for the old free-text engine keep working unchanged —
    but the argument can no longer change the answer. That is the point of the
    change: there is no second opinion left to disagree.

    If `rating` is unusable and no label can be derived, the result is Neutral
    at the confidence floor, never a confident guess.
    """
    label = label_from_rating(rating)
    if label is None:
        return SentimentResult("Neutral", 0.0, ENGINE_NAME,
                               confidence=CONFIDENCE_FLOOR,
                               pos=0.0, neu=1.0, neg=0.0, rating=None)

    split = _split_from_label(label)
    return SentimentResult(
        label=label,
        score=rating_to_score(rating),
        engine=ENGINE_NAME,
        confidence=rating_confidence(rating),
        pos=split["pos"], neu=split["neu"], neg=split["neg"],
        rating=normalize_rating(rating),
    )


def sentiment_label(text=None, rating=None) -> str:
    """Just the label string."""
    return analyze_sentiment(text, rating).label


def sentiment_breakdown(text=None, rating=None) -> dict:
    """A full breakdown dict, ready for display."""
    r = analyze_sentiment(text, rating)
    return {
        **r.to_dict(),
        "confidence_pct": r.confidence_pct,
        "confidence_label": r.confidence_label,
        "pos_pct": round(r.pos * 100, 1),
        "neu_pct": round(r.neu * 100, 1),
        "neg_pct": round(r.neg * 100, 1),
        "rating_word": rating_label(rating),
    }


def engine_status() -> dict:
    """Diagnostics for the administrative portal.

    There is deliberately nothing that can fail here. The old version reported
    whether NLTK was installed and whether a corpus had downloaded, because
    both could be missing and both silently changed the numbers. A rating
    engine has no install step, no corpus, and no model file, so the only thing
    worth reporting is which thresholds are in force.
    """
    return {
        "engine_name": ENGINE_NAME,
        "active_engine": ENGINE_NAME,
        "rating_thresholds": (
            f"1-{NEGATIVE_MAX} Negative · {NEUTRAL} Neutral · "
            f"{POSITIVE_MIN}-5 Positive"
        ),
        "negative_max": NEGATIVE_MAX,
        "neutral": NEUTRAL,
        "positive_min": POSITIVE_MIN,
        "confidence_range": f"{CONFIDENCE_FLOOR:.0%} – {CONFIDENCE_CEILING:.0%}",
        "confidence_tiers": [f"{name} ≥ {thr:.0%}" for thr, name in CONFIDENCE_TIERS],
        # Always empty, and kept as a key rather than removed: the admin card
        # loops over it to render error pills, so an engine that cannot fail
        # still has to have somewhere to say so. A rating engine has no install
        # step, no corpus and no model file — there is nothing that can go
        # missing between deployments, which is the whole reason it replaced
        # the one that had three such failure modes.
        "engine_problems": [],
    }