"""Exercise the sentiment engine against comments that previously
mis-scored. Run: .venv\\Scripts\\python.exe report_sentiment_engine.py"""
import sys

sys.path.insert(0, r"C:\Users\Hp\Downloads\futo_feedback")
import sentiment as S  # noqa: E402

CASES = [
    ("The WiFi is not helpful in the lecture hall", "negative (negation of a positive domain term)"),
    ("The lab computers are not working today", "negative"),
    ("The projector is not clear from the back row", "negative (the old MWE rewrite broke this)"),
    ("The internet is very fast and the staff are helpful", "strong positive + intensifier"),
    ("The internet is fast", "plain positive"),
    ("okay", "neutral"),
    ("The library is fine I guess", "neutral"),
    ("The lecturer is helpful but the lab equipment is broken", "contrastive: should lean negative"),
    ("The hall is NOT well equipped", "negation over a MWE (negator survives rewriter)"),
    ("The hall is well equipped", "positive MWE, no negator"),
    ("VERY BAD!!!", "caps + exclamation intensity"),
    ("not enough computers in the lab", "negative"),
    ("The course content needs improvement", "mild negative"),
    ("The course content really needs improvement", "intensifier over an MWE (never fired before)"),
]

print(f"{'label':<9} {'score':>7} {'conf':>6}  {'pos':>5} {'neu':>5} {'neg':>5}  "
      f"{'x':>5}  note")
print("-" * 104)
for text, note in CASES:
    r = S.analyze_sentiment(text)
    print(f"{r.label:<9} {r.score:>7.3f} {r.confidence:>6.2f}  "
          f"{r.pos:>5.2f} {r.neu:>5.2f} {r.neg:>5.2f}  "
          f"{S.CONFIDENCE_TIERS and '':>5}  {note}")

print()
print("empty text        :", tuple(S.analyze_sentiment("")))
print("None              :", tuple(S.analyze_sentiment(None)))
print("whitespace only   :", tuple(S.analyze_sentiment("   ")))
print("unicode           :", tuple(S.analyze_sentiment("The WiFi is greeaaaaat — ṣùṅ")))
print()
print("tier ladder:")
for c in (0.0, 0.48, 0.54, 0.55, 0.64, 0.65, 0.77, 0.78, 0.89, 0.90, 0.99, 1.0):
    print(f"   {c:>5.2f} -> {S.confidence_tier(c)}")
print()
print("estimate_confidence_from_score:",
      [S.estimate_confidence_from_score(x) for x in (-1.0, -0.5, 0.0, 0.5, 1.0)])
print()
st = S.engine_status()
for k in ("vader_available", "engine_name", "domain_lexicon_terms", "mwe_rules_count",
          "negation_tokens", "intensifier_tokens", "trained_model_available",
          "confidence_range", "confidence_tiers", "engine_problems"):
    # `confidence_tiers` renders as "Very High >= 0.90" — cp1252 (this
    # machine's default console code page) has no glyph for U+2265, so the
    # print raised UnicodeEncodeError and the last two lines of engine
    # status never appeared. Encode explicitly and replace, rather than
    # relying on the console code page.
    val = str(st[k])
    print(f"   {k:<26} {val.encode('ascii', 'backslashreplace').decode('ascii')}")
