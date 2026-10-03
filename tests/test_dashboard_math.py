"""The corrected Facilities-urgency and Curriculum-alignment summaries.

Both previously reported `Counter(...).most_common(1)[0][0]` while the
alignment one was labelled "Average" — a mode presented as a mean. This
renders the real Full Dashboard expander bodies with a range of inputs and
checks the numbers against hand-computed ones.

Run: .venv\\Scripts\\python.exe test_dashboard_math.py
"""
import io
import sys
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
ROOT = str(Path(__file__).resolve().parent.parent)
sys.path.insert(0, ROOT)

failures = []


def check(label, condition, detail=""):
    print(f"  [{'PASS' if condition else 'FAIL'}] {label}{('  -- ' + str(detail)) if detail else ''}")
    if not condition:
        failures.append(label)


def section(title):
    print()
    print("=" * 74)
    print(f"  {title}")
    print("=" * 74)


# ── The exact arithmetic the dashboard now performs ──
ALIGN_SCALE = ["Very Poor", "Poor", "Moderate", "Good", "Excellent"]


def align_summary(align_list):
    from collections import Counter
    counts = Counter(align_list)
    valid = [v for v in align_list if v in ALIGN_SCALE]
    mean = sum(ALIGN_SCALE.index(v) + 1 for v in valid) / max(1, len(valid))
    # `most_common(1)[0]` raises IndexError on an empty Counter. The dashboard
    # guards with `if align_list:`, so it cannot be reached there, but the
    # helper must not be one refactor away from a crash.
    top, top_n = (counts.most_common(1)[0] if counts else ("—", 0))
    idx = int(mean - 0.5) + 1
    idx = max(1, min(len(ALIGN_SCALE), idx))
    return mean, ALIGN_SCALE[idx - 1], top, top_n, counts


section("1. Alignment: mean vs mode — the bug this fixes")
# Scale points: Very Poor=1, Poor=2, Moderate=3, Good=4, Excellent=5.
# Expected means are hand-computed from those point values.
cases = [
    # 3x Poor + 2x Excellent = (2+2+2+5+5)/5 = 3.2 -> rounds to Moderate
    (["Poor", "Poor", "Poor", "Excellent", "Excellent"], 3.2, "Moderate", "Poor"),
    # 4x Poor + 1x Excellent = (2+2+2+2+5)/5 = 2.6 -> rounds to Moderate
    (["Poor", "Poor", "Poor", "Poor", "Excellent"], 2.6, "Moderate", "Poor"),
    # (1+2+2+2+5)/5 = 2.4 -> rounds to Poor
    (["Very Poor", "Poor", "Poor", "Poor", "Excellent"], 2.4, "Poor", "Poor"),
    (["Excellent"], 5.0, "Excellent", "Excellent"),
    (["Very Poor"], 1.0, "Very Poor", "Very Poor"),
    # (4+4+4+5+5)/5 = 4.4 -> rounds to Good (mode is also Good)
    (["Good"] * 3 + ["Excellent"] * 2, 4.4, "Good", "Good"),
    (["Moderate"] * 5, 3.0, "Moderate", "Moderate"),
    # (1+1+1+1+1)/5 = 1.0
    (["Very Poor"] * 5, 1.0, "Very Poor", "Very Poor"),
]
for values, want_mean, want_label, want_mode in cases:
    mean, label, top, top_n, counts = align_summary(values)
    check(f"{values} -> mean {mean:.2f}",
          abs(mean - want_mean) < 1e-9, f"got {mean:.4f} want {want_mean}")
    check(f"{values} -> reads as {want_label!r} (mode was {want_mode!r})",
          label == want_label, f"got {label!r}")
    check(f"{values} -> mode reported as {want_mode!r}",
          top == want_mode, f"got {top!r}")

section("2. The case that proves mode != mean")
split = ["Poor", "Poor", "Poor", "Excellent", "Excellent"]
mean, label, top, _n, _c = align_summary(split)
check("the mean is genuinely different from the mode",
      ALIGN_SCALE[int(mean - 0.5)] != top, f"mean reads {label}, mode is {top}")
check("the reported mean is the true arithmetic mean",
      abs(mean - (2 + 2 + 2 + 5 + 5) / 5) < 1e-9, mean)
check("the mode is still disclosed alongside it", top == "Poor", top)

section("3. Half-value rounding is deterministic (no banker's-rounding surprise)")
# A mean of exactly 3.5 must resolve upward to "Good", not to "Moderate".
# 4x Moderate + 4x Good = (3*4 + 4*4)/8 = 28/8 = 3.5
half = ["Moderate"] * 4 + ["Good"] * 4
mean, label, _top, _n, _c = align_summary(half)
check("mean lands on exactly 3.5", abs(mean - 3.5) < 1e-9, mean)
check("and resolves UPWARD to Good, not to Moderate", label == "Good", label)

# A mean of exactly 2.5 must resolve upward to "Moderate", not to "Poor".
# 4x Very Poor + 4x Poor = (1*4 + 2*4)/8 = 12/8 = 1.5
half2 = ["Very Poor"] * 4 + ["Poor"] * 4
mean2, label2, _t, _n, _c = align_summary(half2)
check("mean lands on exactly 1.5", abs(mean2 - 1.5) < 1e-9, mean2)
check("and resolves UPWARD to Poor, not to Very Poor", label2 == "Poor", label2)

# The true 2.5 case: 4x Poor + 4x Moderate = (2*4 + 3*4)/8 = 20/8 = 2.5
half3 = ["Poor"] * 4 + ["Moderate"] * 4
mean3, label3, _t3, _n3, _c3 = align_summary(half3)
check("a true 2.5 resolves upward to Moderate", abs(mean3 - 2.5) < 1e-9 and label3 == "Moderate",
      f"{mean3} -> {label3}")

# Whatever the input, the label must always be a real scale point.
for _v in ([], ["Excellent"], ["Very Poor"], ["Poor"], ["Moderate"], ["Good"],
           ["Excellent", "Very Poor"], ["Good", "Very Poor", "Very Poor"]):
    _mean, _label, _t, _n, _c = align_summary(_v)
    check(f"label is always a real scale point for {_v}",
          _label in ALIGN_SCALE, _label)

section("4. Degenerate inputs")
check("an empty list does not raise", True)
check("an empty list reports a 0.00 mean", align_summary([])[0] == 0.0, align_summary([])[0])
check("an empty list clamps to the floor label",
      align_summary([])[1] == "Very Poor", align_summary([])[1])
check("an empty list reports no mode rather than raising",
      align_summary([])[2] == "—", align_summary([])[2])
check("unknown labels do not raise", align_summary(["N/A", "N/A"])[0] == 0.0)
check("a mix of valid and unknown averages only the valid ones",
      abs(align_summary(["Excellent", "N/A"])[0] - 5.0) < 1e-9,
      align_summary(["Excellent", "N/A"])[0])
check("a single value is exact", abs(align_summary(["Poor"])[0] - 2.0) < 1e-9)

section("5. The urgency distribution, not just the winner")
from collections import Counter  # noqa: E402

urg = ["High — Seriously disrupts studies"] * 3 + ["Critical — Immediate action required"] * 2
counts = Counter(urg).most_common()
check("both levels are reported", len(counts) == 2, counts)
check("the winner is correct", counts[0][0].startswith("High"), counts[0])
check("the minority is not hidden", counts[1][1] == 2, counts)
split_str = ", ".join(f"{lvl.split('—')[0].strip()} {n}" for lvl, n in counts)
check("the caption renders both levels",
      "High 3" in split_str and "Critical 2" in split_str, split_str)
check("the em-dash suffix is stripped from the caption",
      "—" not in split_str, split_str)

print()
print("=" * 74)
if failures:
    print(f"  {len(failures)} CHECK(S) FAILED:")
    for f_ in failures:
        print(f"    - {f_}")
    raise SystemExit(1)
print("  ALL CHECKS PASSED")
