"""Verify the trained-model round trip that B-03 / B-27 / B-29 were about.

The original design wrapped the sklearn Pipeline in a class defined *inside*
`_train_sklearn`, whose pickle reference (`<locals>._SklearnWrapper`) cannot be
resolved on load — so every model the trainer saved was dead on arrival and
sentiment.py's `except Exception: pass` hid it. This checks that a model
trained now survives the write/read/apply cycle in a fresh interpreter, that
both backends work, and that a stale/corrupt model produces a visible reason
instead of a silent "no model".

Run: .venv\\Scripts\\python.exe test_model_roundtrip.py
"""
import io
import os
import pickle
import shutil
import sys
import time
from pathlib import Path
import tempfile

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
ROOT = str(Path(__file__).resolve().parent.parent)
sys.path.insert(0, ROOT)

import streamlit as st  # noqa: E402

import sentiment as S  # noqa: E402
import train_model as T  # noqa: E402

SAMPLES = [
    ("The WiFi is fast and reliable in the lecture hall", "Positive"),
    ("Excellent internet speed, the labs are well equipped", "Positive"),
    ("The lecturer is very helpful and the course material is excellent", "Positive"),
    ("The library is quiet, spacious and well illuminated", "Positive"),
    ("Staff are friendly and the response time is quick", "Positive"),
    ("The system is okay, nothing special", "Neutral"),
    ("The course is average, the lecture hall is standard", "Neutral"),
    ("It is fine I guess, nothing to report", "Neutral"),
    ("The system works most of the time, it is acceptable", "Neutral"),
    ("The timetable is fine, the room is ordinary", "Neutral"),
    ("The internet is very slow and the computers crash constantly", "Negative"),
    ("Broken projector, dirty lab, no light in the hall", "Negative"),
    ("Lecturers are rude and the facilities are dilapidated", "Negative"),
    ("Exams arrive late and results are delayed, very frustrating", "Negative"),
    ("Power outage every day, the hall is overcrowded and noisy", "Negative"),
]

TMP = tempfile.mkdtemp(prefix="futo_model_")
FAKE_MODEL = os.path.join(TMP, "sentiment_classifier.pkl")

failures = []


def check(label, condition, detail=""):
    mark = "PASS" if condition else "FAIL"
    print(f"  [{mark}] {label}{('  — ' + detail) if detail else ''}")
    if not condition:
        failures.append(label)


def reload_engine(model_path):
    """Point the engine at `model_path` and drop every cached resource.

    `S.invalidate_trained_model()` rather than `_get_trained_model.clear()`:
    the cached function is now `_load_trained_model`, and `_get_trained_model`
    is a plain wrapper that no longer carries a `.clear`. It also resets the
    recorded mtime, which is what the wrapper's staleness check reads — without
    that the wrapper would consider the just-written file "newer than loaded"
    and reload on its own, which is correct behaviour but makes this helper's
    intent untestable.
    """
    S.MODEL_PATH = model_path
    S._MODEL_LOAD_ERROR = None
    try:
        st.cache_resource.clear()
    except Exception:
        pass
    S.invalidate_trained_model()


print("=" * 72)
print("  1. sklearn backend: train -> write -> read in this process")
print("=" * 72)
pipeline, metrics, engine_label = T._train_sklearn(
    [t for t, _ in SAMPLES], [l for _, l in SAMPLES], engine="logreg"
)
check("_train_sklearn returned a Pipeline", pipeline is not None)
if pipeline is None:
    print("  (sklearn backend unavailable; remaining checks will be skipped)")
else:
    print(f"     engine : {engine_label}")
    print(f"     metrics: accuracy={metrics['accuracy']:.1%} macro_f1={metrics['macro_f1']:.1%}")

    bundle = {
        "classifier": pipeline,
        "backend": "sklearn",
        "meta": {
            "trained_at": "2026-09-28 10:00:00",
            "n_samples": len(SAMPLES),
            "accuracy": metrics["accuracy"],
            "macro_f1": metrics["macro_f1"],
            "engine_type": engine_label,
            "class_distribution": dict(T.Counter(l for _, l in SAMPLES)),
            "feature_spec": S.FEATURE_SPEC,
            "versions": T._library_versions(),
        },
    }
    with open(FAKE_MODEL, "wb") as fh:
        pickle.dump(bundle, fh, protocol=pickle.HIGHEST_PROTOCOL)

    check("no temp file left behind", not os.path.exists(FAKE_MODEL + ".tmp"))

    reload_engine(FAKE_MODEL)
    loaded = S._get_trained_model()
    check("sentiment.py loaded the bundle", isinstance(loaded, dict))
    check("backend key survived", (loaded or {}).get("backend") == "sklearn")
    check("_MODEL_LOAD_ERROR is clear", S._MODEL_LOAD_ERROR is None,
          S._MODEL_LOAD_ERROR or "")

    if loaded:
        label = S._classify_with_model(loaded, "The internet is very slow and crashes")
        check("sklearn backend classifies", label in ("Positive", "Neutral", "Negative"),
              f"-> {label}")

        r = S.analyze_sentiment("The internet is very slow and crashes")
        check("analyze_sentiment uses the model", S._classify_with_model(loaded, r and "The internet is very slow and crashes") == r.label)
        check("engine name advertises the classifier", "Supervised" in r.engine, r.engine)
        check("score still comes from the rule engine", abs(r.score) > 0.0,
              f"score={r.score}")
        check("confidence is in the calibrated band",
              S.CONFIDENCE_FLOOR <= r.confidence <= S.CONFIDENCE_CEILING,
              f"conf={r.confidence}")
        check("confidence is NOT the model's accuracy",
              abs(r.confidence - metrics["accuracy"]) > 0.01,
              f"conf={r.confidence} vs accuracy={metrics['accuracy']:.3f}")

        st_status = S.engine_status()
        check("engine_status reports the model", st_status["trained_model_available"] is True)
        check("engine_status reports no problems", not st_status["engine_problems"],
              str(st_status["engine_problems"]))

print()
print("=" * 72)
print("  2. nltk backend: the .classify(feature_dict) contract still holds")
print("=" * 72)
import nltk  # noqa: E402

dataset = [(S._features(S._tokenize(t)), l) for t, l in SAMPLES]
T.random.seed(42)
nltk_bayes = nltk.NaiveBayesClassifier.train(dataset)
nltk_bundle = {
    "classifier": nltk_bayes,
    "backend": "nltk",
    "meta": {"trained_at": "2026-09-28 10:00:00", "n_samples": len(SAMPLES),
             "accuracy": 0.9, "macro_f1": 0.88,
             "engine_type": "Supervised NaiveBayes (N-gram + MWE)",
             "feature_spec": S.FEATURE_SPEC, "versions": T._library_versions()},
}
with open(FAKE_MODEL, "wb") as fh:
    pickle.dump(nltk_bundle, fh, protocol=pickle.HIGHEST_PROTOCOL)
reload_engine(FAKE_MODEL)
nltk_loaded = S._get_trained_model()
check("nltk bundle loaded", isinstance(nltk_loaded, dict))
if nltk_loaded:
    out = S._classify_with_model(nltk_loaded, "the lab is dilapidated and rude staff")
    check("nltk backend classifies", out in ("Positive", "Neutral", "Negative"), f"-> {out}")

print()
print("=" * 72)
print("  3. Failure modes must be VISIBLE, not silent")
print("=" * 72)

# 3a. A model pickled against a different feature space.
with open(FAKE_MODEL, "wb") as fh:
    pickle.dump({**nltk_bundle, "meta": {**nltk_bundle["meta"], "feature_spec": "v0:ancient"}}, fh)
reload_engine(FAKE_MODEL)
check("stale feature_spec is refused", S._get_trained_model() is None)
check("…with a reason", bool(S._MODEL_LOAD_ERROR), S._MODEL_LOAD_ERROR or "(none)")
check("…surfaced in engine_status", bool(S.engine_status()["engine_problems"]))

# 3b. A corrupt / truncated file.
with open(FAKE_MODEL, "wb") as fh:
    fh.write(b"\x80\x04\x95 this is not a pickle at all")
reload_engine(FAKE_MODEL)
check("corrupt pkl is refused", S._get_trained_model() is None)
check("…with a reason", bool(S._MODEL_LOAD_ERROR), S._MODEL_LOAD_ERROR or "(none)")

# 3c. A well-formed pickle of the wrong shape.
with open(FAKE_MODEL, "wb") as fh:
    pickle.dump(["not", "a", "bundle"], fh)
reload_engine(FAKE_MODEL)
check("wrong-shape pkl is refused", S._get_trained_model() is None)
check("…with a reason", bool(S._MODEL_LOAD_ERROR), S._MODEL_LOAD_ERROR or "(none)")

# 3d. A bundle whose classifier raises mid-predict must not kill the record.
class Exploding:
    def classify(self, feats):
        raise RuntimeError("boom")


with open(FAKE_MODEL, "wb") as fh:
    pickle.dump({"classifier": Exploding(), "backend": "nltk",
                 "meta": {"feature_spec": S.FEATURE_SPEC, "engine_type": "Broken"}}, fh)
reload_engine(FAKE_MODEL)
r = S.analyze_sentiment("The lab is dilapidated")
check("a raising model degrades to the rule engine", r.label in ("Positive", "Neutral", "Negative"),
      f"{r.label} via {r.engine}")
check("…and says so in the engine name", "model error" in r.engine, r.engine)
check("…and the score is still real", abs(r.score) > 0.0, f"score={r.score}")

# 3e. No model at all.
os.remove(FAKE_MODEL)
reload_engine(FAKE_MODEL)
r = S.analyze_sentiment("The lab is dilapidated")
check("no model -> rule engine only", r.engine == "vader_academic_pro", r.engine)
check("no model -> no false 'unavailable'", S.engine_status()["vader_available"] is True)

print()
print("=" * 72)
print("  4. A model that APPEARS after the process first read must be noticed")
print("=" * 72)
# This is the failure mode the in-app training button creates. `_load_trained_model`
# is `@st.cache_resource`, so it holds whatever it first read. Without the
# staleness check, an admin trains a model, the new `.pkl` lands on disk, and
# the app keeps classifying with the old one — or with none at all — while the
# status card reports no problem anywhere.
check("no model is loaded right now", S._get_trained_model() is None)
check("nothing on disk, so nothing is stale", S.model_is_stale() is False)

with open(FAKE_MODEL, "wb") as fh:
    pickle.dump(nltk_bundle, fh, protocol=pickle.HIGHEST_PROTOCOL)
check("a model dropped in on disk registers as stale",
      S.model_is_stale() is True)

reloaded = S._get_trained_model()
check("…and the very next read picks it up without any explicit clear",
      isinstance(reloaded, dict) and reloaded.get("backend") == "nltk")
check("…and it is no longer stale", S.model_is_stale() is False)

# Rewriting the same path must be detected too, which is what training does.
with open(FAKE_MODEL, "wb") as fh:
    pickle.dump({**nltk_bundle, "meta": {**nltk_bundle["meta"],
                                         "engine_type": "Retrained"}}, fh)
os.utime(FAKE_MODEL, (time.time() + 2, time.time() + 2))
check("overwriting the file in place also registers as stale",
      S.model_is_stale() is True)
check("…and the new bundle is what loads",
      (S._get_trained_model().get("meta") or {}).get("engine_type") == "Retrained")

# The explicit invalidator must still work on its own, and must not disturb the
# VADER singleton: they share `st.cache_resource`, and clearing that wholesale
# would rebuild the analyzer on every page render.
vader_before = S._get_vader()
S.invalidate_trained_model()
check("invalidate reports that it cleared a cache", S.invalidate_trained_model() is True)
check("the VADER singleton survived the clear", S._get_vader() is vader_before)
check("and the model reloads from disk", S._get_trained_model() is not None)

os.remove(FAKE_MODEL)
S.invalidate_trained_model()
check("removing the file and invalidating returns to the rule engine",
      S._get_trained_model() is None)
check("…and engine_status is clean again", not S.engine_status()["engine_problems"],
      str(S.engine_status()["engine_problems"]))

shutil.rmtree(TMP, ignore_errors=True)
print()
print("=" * 72)
if failures:
    print(f"  {len(failures)} CHECK(S) FAILED:")
    for f in failures:
        print(f"    - {f}")
    raise SystemExit(1)
print("  ALL CHECKS PASSED")
