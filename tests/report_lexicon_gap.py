"""Report common IFT-feedback terms that neither the domain lexicon nor VADER
knows about, so a plain negative comment scores Neutral.
Run: .venv\\Scripts\\python.exe report_lexicon_gap.py"""
import io
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.path.insert(0, r"C:\Users\Hp\Downloads\futo_feedback")
import sentiment as S  # noqa: E402

vader = S._get_vader()
base = getattr(vader, "futo_base_lexicon_keys", frozenset())
print(f"vader base vocabulary: {len(base)} terms, "
      f"domain lexicon: {len(S.ACADEMIC_DOMAIN_LEXICON)} terms\n")

# (term, expected polarity sign) — plain, unnegated usage.
CANDIDATES = [
    # complaints
    "lag", "lagging", "lags", "buffering", "buffers", "freezing", "freezes",
    "crashing", "crashes", "crashed", "hanging", "glitch", "glitchy",
    "unusable", "unreliable", "inaccessible", "undisclosed", "broken",
    "malfunction", "malfunctions", "unserviceable", "nonfunctional",
    "fails", "failing", "failed", "fail", "frequently", "often", "sometimes",
    "occasionally", "rarely", "seldom", "hardly", "barely", "scanty", "scarce",
    "insufficient", "inadequate", "limited", "lacking", "missing", "absent",
    "unavailable", "unreachable", "disconnected", "offline", "down",
    "confusing", "confused", "unclear", "vague",
    "complicated", "tedious", "time-consuming", "cumbersome",
    "expensive", "costly", "overpriced", "unfair", "biased", "poor",
    "poorly", "weak", "poor-quality", "subpar", "inadequate",
    "noisy", "crowded", "congested", "full", "occupied",
    "unfriendly", "unhelpful", "indifferent", "neglect", "neglected",
    "ignored", "dismissive", "arrogant", "intimidating", "unapproachable",
    "chaotic", "confusing", "cluttered", "messy", "dirty", "untidy",
    "delayed", "late", "slow", "quick", "fast", "stable", "responsive",
    "helpful", "friendly", "supportive", "responsive", "efficient",
    "knowledgeable", "competent", "qualified", "dedicated", "committed",
    "punctual", "organized", "fair", "transparent", "flexible", "accessible",
    "recommend", "excellent", "great", "good", "bad", "poor", "terrible",
    "awful", "horrible", "worst", "best", "amazing", "impressive",
    "improvement", "improvements", "upgrade", "upgraded", "modern",
    "adequate", "sufficient", "ample", "adequate", "adequate",
    "adequate", "satisfactory", "worth", "worthwhile", "appreciate",
]

ours = set(S.ACADEMIC_DOMAIN_LEXICON)
missing_ours, missing_both = [], []
for t in CANDIDATES:
    if t in ours:
        continue
    (missing_both if t not in base else missing_ours).append(t)

print("In VADER's own lexicon but not ours (fine — VADER scores them):")
print("   ", ", ".join(missing_ours))
print()
print("In NEITHER lexicon (these score Neutral unless negated):")
print("   ", ", ".join(missing_both))

print("\n--- sentiment of a bare complaint sentence containing only these ---")
for t in missing_both:
    r = S.analyze_sentiment(f"The system is {t}")
    flag = "  <-- scores Neutral" if r.label == "Neutral" else ""
    print(f"   'The system is {t:<14}' -> {r.label:<9} {r.score:>6.3f}{flag}")
