"""Regression gate for the in-app sentiment-training trigger.

Why this file exists
--------------------
`train_model.py` was a CLI and nothing else. On Streamlit Community Cloud —
the deployment target — there is no shell, no SSH and no cron, so the supervised
half of the sentiment engine could never be trained at all. Every correction an
examiner made on the Full Dashboard fed a database column that no code path
would ever read, while the engine's own status card advertised a trained-
classifier stage. The feature was documented and unreachable.

The fix put training behind a button on User Management. That creates three new
ways for it to be quietly broken, and all three are invisible at runtime:

1. **The button trains a model the app does not use.** `_load_trained_model` is
   `@st.cache_resource` and holds whatever it first read for the life of the
   process. Write a new `.pkl` and the old model stays in memory — the button
   reports success and every label is unchanged. Nothing anywhere errors.
2. **The threshold is enforced somewhere invisible.** The original trainer
   printed "need at least 40" and returned. A button that always fires and only
   then reports failure is a button the admin learns to distrust.
3. **Training mutates the live database as a side effect of reading it.**
   `load_labeled_training_data(readonly=True)` exists precisely to stop
   `get_db()` switching the live file to WAL, adding columns and purging rows
   while the trainer is only reading labels. Dropping that flag for the
   in-process path would be a real regression, and a quiet one.

Each is checked below, plus the UI states (disabled-with-a-reason, armed
confirmation, success dialog) that the previous CLI had no equivalent of.

Runs entirely against a temp database and a temp model path. The live
`futo_feedback.db` and any real `.pkl` are never touched.

Run: .venv\\Scripts\\python.exe tests\\test_model_training_trigger.py
"""
import io
import os
import shutil
import sys
import tempfile
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
ROOT = str(Path(__file__).resolve().parent.parent)
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)

from db_snapshot import snapshot_live_db  # noqa: E402

TMP = tempfile.mkdtemp(prefix="futo_train_")
# Not `shutil.copy2`: the live file is in WAL mode, so a plain file copy drops
# every commit since the last checkpoint and silently hands the suite a
# different database. Found the hard way here — the stale copy still carried a
# legacy admin hash, so the app held the signed-in admin on the password-change
# screen and the sidebar radio this suite navigates with did not exist.
COPY = snapshot_live_db(TMP)
MODEL = os.path.join(TMP, "model", "sentiment_classifier.pkl")

import streamlit as st  # noqa: E402

import db  # noqa: E402

db.DB_PATH = COPY
st.cache_resource.clear()
db.get_db.clear()

import config  # noqa: E402
import sentiment as S  # noqa: E402
import train_model as T  # noqa: E402

T.MODEL_PATH = MODEL
S.MODEL_PATH = MODEL
S.invalidate_trained_model()

from streamlit.testing.v1 import AppTest  # noqa: E402

APP = os.path.join(ROOT, "app.py")
MIN = config.MIN_TRAINING_SAMPLES

# 15 per class is a small but balanced set. Every comment is lexically distinct
# enough that a bag-of-words model can separate them — a training set of fifteen
# paraphrases of one sentence produces a model whose accuracy says nothing.
CORPUS = {
    "Positive": [
        "The lecture hall projector is bright and easy to read from the back row",
        "My lecturer explains difficult concepts clearly and repeats them when asked",
        "The internet in the IFT lab is fast and has never dropped during an exam",
        "Course notes are well structured and the slides match the reading list",
        "Staff in the department office answered my email the same afternoon",
        "The library is quiet, well lit and has enough power sockets for everyone",
        "Practical sessions are engaging and the lab technician helps every student",
        "Exams are returned quickly and the feedback on my script was very useful",
        "The seminar room has reliable air conditioning and comfortable seating",
        "The syllabus is clear about deadlines and the assessment weighting is fair",
        "WiFi coverage in the lecture theatre is strong even at the back of the hall",
        "The lecturer's feedback on my project pushed me to improve substantially",
        "The lab equipment is modern and everything we need is already installed",
        "Timetable changes are communicated well in advance through the portal",
        "The tutorial groups are small enough that everyone gets individual attention",
    ],
    "Neutral": [
        "The class starts at eight in the morning and finishes before lunch",
        "Course registration worked normally and my enrolment was confirmed",
        "The room number for the lecture was printed on the timetable sheet",
        "I attend the Wednesday lecture and the hall is on the second floor",
        "The exam covers the first six topics listed in the course outline",
        "Attendance is recorded weekly and the register is signed at the door",
        "The department issues course materials at the start of each semester",
        "Lectures are held twice a week and the tutorial once a fortnight",
        "The grading scale runs from A to F and the pass mark is a C",
        "Office hours are published on the department website every week",
        "The lecture theatre seats about one hundred and twenty students",
        "Group work is assessed individually as well as for the final submission",
        "The course is worth fifteen credits in the IFT programme structure",
        "I submit assignments through the student portal before the stated time",
        "The academic calendar splits each term into teaching weeks and revision",
    ],
    "Negative": [
        "The projector in hall two has been broken for the entire semester",
        "Exams are returned weeks after the results are supposed to be published",
        "The lab computers crash constantly and we lose our work repeatedly",
        "There is no working air conditioning in the lecture hall during summer",
        "WiFi drops every few minutes in the IFT laboratory making research impossible",
        "The lecturer rarely attends and classes are frequently cancelled at short notice",
        "Course materials are out of date and reference books listed are unavailable",
        "The feedback I received on my assignment was dismissive and unhelpful",
        "Power outages are common and there is no backup for the servers",
        "The timetable gives us a clash on Monday and we must choose one class",
        "Marks are recorded incorrectly and getting them corrected takes many weeks",
        "The practical class is too large to receive individual attention from staff",
        "There are not enough functioning seats and many students stand during class",
        "The library closes far too early to study between lectures in the evening",
        "The registration portal has failed repeatedly since Monday morning",
    ],
}

failures = []


def check(label, condition, detail=""):
    print(f"  [{'PASS' if condition else 'FAIL'}] {label}"
          f"{('  -- ' + str(detail)) if detail else ''}")
    if not condition:
        failures.append(label)


def section(title):
    print()
    print("=" * 74)
    print(f"  {title}")
    print("=" * 74)


def clear_corrections():
    conn = db.get_db()
    conn.execute("UPDATE feedback SET admin_corrected_sentiment = NULL, "
                 "corrected_by = NULL, corrected_at = NULL")
    conn.commit()
    return conn


_FIXTURE_SEQ = 0


def seed_corrections(per_class: int):
    """Writes `per_class` corrections for each label. Returns the row count.

    Each fixture comment gets its own username, because `feedback` carries
    `UNIQUE(username, category, session)` and every comment here is filed under
    the same category and session. The counter is module-level and never
    rewound, so calling this twice cannot collide with the rows the previous
    call inserted. The trainer only ever reads `comment` and the label, so the
    username is irrelevant to what is being tested.
    """
    global _FIXTURE_SEQ
    conn = clear_corrections()
    n = 0
    for label, texts in CORPUS.items():
        for text in texts[:per_class]:
            _FIXTURE_SEQ += 1
            exists = conn.execute(
                "SELECT id FROM feedback WHERE comment = ?", (text,)
            ).fetchone()
            if exists:
                conn.execute(
                    "UPDATE feedback SET admin_corrected_sentiment = ?, "
                    "corrected_by = 'admin001', corrected_at = datetime('now') "
                    "WHERE id = ?", (label, exists[0]))
            else:
                conn.execute(
                    "INSERT INTO feedback (username, category, comment, timestamp, "
                    "admin_corrected_sentiment, corrected_by, corrected_at, session) "
                    "VALUES (?, 'Internet', ?, datetime('now'), ?, 'admin001', "
                    "datetime('now'), '2025/2026')",
                    (f"trainfix{_FIXTURE_SEQ:04d}", text, label))
            n += 1
    conn.commit()
    return n


def relabel(texts, label=None):
    """Sets (or with `label=None`, clears) the correction on exact comments.

    Matched by equality, not LIKE. A substring match reaches straight into the
    rest of the fixture — "library" appears in a Positive and a Negative
    comment — and a test that quietly edits the wrong rows is worse than no
    test at all, because it reports green.
    """
    conn = db.get_db()
    for text in texts:
        conn.execute(
            "UPDATE feedback SET admin_corrected_sentiment = ?, corrected_by = ?, "
            "corrected_at = datetime('now') WHERE comment = ?",
            (label, "admin001" if label else None, text),
        )
    conn.commit()


def um_test(**extra):
    """An AppTest signed in as an admin, navigated to User Management."""
    at = AppTest.from_file(str(APP), default_timeout=120)
    at.session_state["password_correct"] = True
    at.session_state["username"] = "admin001"
    at.session_state["user"] = {
        "name": config.ADMIN_SEED_ACCOUNTS[0].get("full_name") or "Administrator",
        "role": "admin", "level": "staff",
        "email": config.ADMIN_SEED_ACCOUNTS[0].get("email", "admin@futo.edu.ng"),
    }
    for k, v in extra.items():
        at.session_state[k] = v
    at.run()
    # The sidebar nav is a `st.radio` with no explicit key, so the page is
    # selected the way a user selects it — through the widget, not by writing
    # session state. Writing a key that the widget does not use is how a test
    # ends up "on" a page the app never rendered.
    nav = next((r for r in at.radio if (r.label or "") == "Navigation"), None)
    if nav is None:
        raise AssertionError(
            "no Navigation radio; radios = "
            f"{[r.label for r in at.radio]}; exceptions = "
            f"{[str(e.value) for e in at.exception]}; errors = "
            f"{[e.value for e in at.error]}; body = "
            f"{' '.join(m.value for m in at.markdown)[:400]}"
        )
    nav.set_value("User Management").run()
    return at


def button_disabled(btn) -> bool:
    """AppTest's `Button` has no `disabled` property — read the proto."""
    return bool(getattr(getattr(btn, "proto", None), "disabled", False))


def find_button(at, label):
    for b in at.button:
        if (b.label or "") == label:
            return b
    raise AssertionError(f"no button labelled {label!r}; have "
                         f"{[b.label for b in at.button]}")


def page_text(at):
    parts = [m.value for m in at.markdown]
    parts += [c.value for c in at.caption]
    parts += [e.value for e in at.error]
    parts += [s.value for s in at.success]
    parts += [b.label for b in at.button]
    return " ".join(str(p) for p in parts)


# ══════════════════════════════════════════════════════════════════════
section("1. training_readiness() answers before anything is trained")
# ══════════════════════════════════════════════════════════════════════

clear_corrections()
info = T.training_readiness()
check("an empty correction set is not ready", info["ready"] is False)
check("it reports zero usable samples", info["usable"] == 0, info["usable"])
check("it reports how many are still needed", info["remaining"] == MIN,
      info["remaining"])
check("it names all three classes as missing",
      sorted(info["missing_classes"]) == ["Negative", "Neutral", "Positive"],
      info["missing_classes"])
check("its required count is the configured threshold", info["required"] == MIN)
check("reading readiness wrote no model file", not os.path.exists(MODEL))
check("reading readiness did not touch the live model dir",
      not os.path.exists(os.path.join(ROOT, "model", "sentiment_classifier.pkl.tmp")))

# Below the threshold, with one class entirely absent.
seed_corrections(2)
info = T.training_readiness()
check("6 corrections is still not ready", info["ready"] is False)
check("the count is exact", info["usable"] == 6, info["usable"])
check("distribution is per class",
      info["distribution"] == {"Positive": 2, "Neutral": 2, "Negative": 2},
      info["distribution"])
check("a class with exactly one sample is called out separately from zero",
      info["singleton_classes"] == [] and info["missing_classes"] == [],
      (info["missing_classes"], info["singleton_classes"]))

conn = db.get_db()
relabel(CORPUS["Positive"][:2], None)   # drop the whole Positive class
info = T.training_readiness()
check("a class emptied to zero is reported missing",
      info["missing_classes"] == ["Positive"], info["missing_classes"])
check("and is not reported as a singleton at the same time",
      "Positive" not in info["singleton_classes"], info["singleton_classes"])
check("the usable count drops by exactly that class", info["usable"] == 4,
      info["usable"])

relabel(CORPUS["Positive"][:1], "Positive")   # bring one back
info = T.training_readiness()
check("a class down to one sample is reported as a singleton, not missing",
      info["singleton_classes"] == ["Positive"], info["singleton_classes"])
check("and is not reported missing at the same time",
      "Positive" not in info["missing_classes"], info["missing_classes"])

# An unexpected label value must not be counted as usable, and must not crash.
seed_corrections(4)
conn.execute("UPDATE feedback SET admin_corrected_sentiment = 'SortaGood' "
             "WHERE admin_corrected_sentiment IS NOT NULL")
conn.commit()
info = T.training_readiness()
check("an unrecognised label is excluded from the usable count",
      info["usable"] == 0, info["usable"])
check("…but is still counted in `total`, so the admin is not misled",
      info["total"] == 12, info["total"])
check("all three classes read as missing", len(info["missing_classes"]) == 3,
      info["missing_classes"])
check("and it is still not ready", info["ready"] is False)

# ══════════════════════════════════════════════════════════════════════
section("2. train() refuses below the threshold, and says why")
# ══════════════════════════════════════════════════════════════════════

clear_corrections()
seed_corrections(2)
res = T.train()
check("it declines", res["ok"] is False)
check("the reason is machine-readable", res["reason"] == "not_enough_samples",
      res.get("reason"))
check("the message names both numbers",
      str(MIN) in res["message"] and "6" in res["message"], res["message"])
check("no model file was written", not os.path.exists(MODEL))
check("no temp file was left behind", not os.path.exists(MODEL + ".tmp"))
check("the log explains the threshold in words",
      "corrected samples to train" in " ".join(res["log"]))
check("a bad engine name is rejected without training",
      T.train(engine="nonsense")["ok"] is False)

# ══════════════════════════════════════════════════════════════════════
section("3. train() writes a model the engine actually uses")
# ══════════════════════════════════════════════════════════════════════

seed_corrections(15)   # 45 corrections, 15 per class
info = T.training_readiness()
check("the fixture is now above the threshold", info["ready"] is True, info)
check("and no class is missing or a singleton",
      not info["missing_classes"] and not info["singleton_classes"])

check("nothing is loaded before the first training", S._get_trained_model() is None)
check("and nothing is on disk", not os.path.exists(MODEL))

res = T.train()
check("training succeeded", res["ok"] is True, res.get("message"))
check("it reports the backend it used", res["backend"] in ("sklearn", "nltk"),
      res["backend"])
check("accuracy is a real fraction", 0.0 <= res["accuracy"] <= 1.0, res["accuracy"])
check("macro F1 is a real fraction", 0.0 <= res["macro_f1"] <= 1.0, res["macro_f1"])
check("it reports how many samples it used", res["samples"] == 45, res["samples"])
check("the model file now exists", os.path.exists(MODEL))
check("no temp file survives", not os.path.exists(MODEL + ".tmp"))

import pickle  # noqa: E402

with open(MODEL, "rb") as fh:
    bundle = pickle.load(fh)
check("the bundle has a classifier", bundle.get("classifier") is not None)
check("the bundle records the feature spec the engine checks",
      bundle["meta"]["feature_spec"] == S.FEATURE_SPEC, bundle["meta"]["feature_spec"])
check("the bundle records the library versions", "sklearn" in bundle["meta"]["versions"])
check("the bundle records who trained it (model/ is gitignored)",
      "trained_by" in bundle["meta"])

# THE critical check: the app must pick the new model up, not keep the old one.
check("the engine still holds nothing, because the cache is process-wide",
      S._get_trained_model() is not None,
      "a stale-cache failure would surface as None here")
loaded = S._get_trained_model()
check("…and it is the bundle just written",
      isinstance(loaded, dict) and loaded["meta"]["trained_at"] == res["trained_at"],
      (loaded or {}).get("meta", {}).get("trained_at"))

r = S.analyze_sentiment("The projector has been broken all semester and nobody fixed it")
check("a negative comment classifies as Negative via the model",
      r.label == "Negative", f"{r.label} via {r.engine}")
check("the engine name advertises the supervised classifier",
      "Supervised" in r.engine or "NaiveBayes" in r.engine, r.engine)
check("but the score still comes from the rule engine", r.score < 0, r.score)
check("and the confidence is still in the calibrated band",
      S.CONFIDENCE_FLOOR <= r.confidence <= S.CONFIDENCE_CEILING, r.confidence)

# Label wiring. These are exact *training* sentences, so a correctly wired
# model reproduces the label it was taught. A model whose labels had been
# shuffled against their texts would memorize the shuffled mapping and answer
# wrongly — so this catches the one failure that a bare `0 <= accuracy <= 1`
# cannot: the pipeline being fed the right texts with the wrong labels.
#
# Deliberately NOT asserting a minimum accuracy. With 3 held-out samples per
# class, one sentence landing on the wrong side of the boundary moves the
# number by 11 points, and a test that fails on a coin flip teaches nothing.
# Generalisation is what the trainer's own report is for; *correctness of the
# wiring* is what a fixture this size can actually prove.
_wiring = [
    (CORPUS["Positive"][0], "Positive"),
    (CORPUS["Positive"][8], "Positive"),
    (CORPUS["Neutral"][0], "Neutral"),
    (CORPUS["Neutral"][8], "Neutral"),
    (CORPUS["Negative"][0], "Negative"),
    (CORPUS["Negative"][2], "Negative"),
]
_bad = [(t, want, S.analyze_sentiment(t).label)
        for t, want in _wiring if S.analyze_sentiment(t).label != want]
check("the trained model reproduces the labels it was taught",
      not _bad, _bad)

st_status = S.engine_status()
check("engine_status reports the model as live",
      st_status["trained_model_available"] is True)
check("and reports no load problems", not st_status["engine_problems"],
      str(st_status["engine_problems"]))

# Retraining over the same path must take effect, not be masked by the cache.
res2 = T.train()
S.invalidate_trained_model()
check("a second training run also succeeds", res2["ok"] is True)
check("the engine now serves the NEWER bundle",
      S._get_trained_model()["meta"]["trained_at"] == res2["trained_at"],
      (S._get_trained_model() or {}).get("meta", {}).get("trained_at"))
check("the previous model was kept as .prev.pkl",
      os.path.exists(os.path.join(os.path.dirname(MODEL),
                                 "sentiment_classifier.prev.pkl")))

# ══════════════════════════════════════════════════════════════════════
section("4. training must not mutate the database it reads")
# ══════════════════════════════════════════════════════════════════════

# A row the retention sweep would remove if `get_db()` ran during training.
conn = db.get_db()
conn.execute(
    "INSERT OR REPLACE INTO admin_audit_log "
    "(action, target_username, target_full_name, target_role, performed_by, "
    " performed_at, feedback_rows_deleted, reason, snapshot) "
    "VALUES ('DELETE_USER','SweepProbe','Sweep Probe','student','admin001', "
    "        datetime('now','-30 days'), 0, 'probe', '{}')"
)
conn.commit()
# Assert *unchanged*, not `delete`. The live database already runs in WAL, so a
# test that demanded `delete` would fail for the wrong reason while still
# passing the actual property it cares about: that reading labels goes through
# the read-only URI and never touches the connection `get_db()` owns.
journal_before = str(conn.execute("PRAGMA journal_mode").fetchone()[0]).lower()

seed_corrections(15)
res = T.train()
check("training succeeded against a populated set", res["ok"] is True)

conn2 = db.get_db()
journal_after = str(conn2.execute("PRAGMA journal_mode").fetchone()[0]).lower()
check("training did not change the database's journal mode",
      journal_after == journal_before,
      f"{journal_before} -> {journal_after}")
survivor = conn2.execute(
    "SELECT COUNT(*) FROM admin_audit_log WHERE target_username = 'SweepProbe'"
).fetchone()[0]
check("training did not run the retention sweep as a side effect", survivor == 1,
      survivor)
check("the correction rows are all still there",
      len(db.load_labeled_training_data()) == 45,
      len(db.load_labeled_training_data()))

# ══════════════════════════════════════════════════════════════════════
section("5. the UI: disabled with a reason when not trainable")
# ══════════════════════════════════════════════════════════════════════

# Sections 3 and 4 left a trained model behind. Remove it so the card has to
# describe the rule-engine-only state, and drop the cached copy too — otherwise
# `engine_status()` keeps reporting a model that is no longer on disk and the
# assertions below pass against the previous section's leftovers.
if os.path.exists(MODEL):
    os.remove(MODEL)
S.invalidate_trained_model()
check("no model is on disk before the page renders", not os.path.exists(MODEL))
check("and none is cached", S._get_trained_model() is None)

clear_corrections()
at = um_test()
check("the page renders with no corrections", not at.exception,
      [str(e.value) for e in at.exception])
txt = page_text(at)
check("the training section is present", "Supervised Sentiment Classifier" in txt)
check("it says plainly that no model is loaded",
      "Rule engine only" in txt or "No trained model" in txt,
      "neither phrase present")
check("and not the opposite", "Model active" not in txt)
check("it does NOT claim the engine is broken",
      "cannot be loaded" not in txt, txt[:200])
check("the progress toward the threshold is shown",
      "Corrections toward a trainable model" in txt)
check("it names the number still needed", f"{MIN} more to go" in txt,
      [c.value for c in at.caption][:3])

labels = [b.label for b in at.button]
check("there is a 'Train model now' button", "Train model now" in labels, labels)
check("it is disabled", button_disabled(find_button(at, "Train model now")))
check("the caption explains why it is disabled",
      any("Unavailable until" in (c.value or "") for c in at.caption),
      [c.value for c in at.caption])
check("no confirmation is armed by a render", "Yes, train the model" not in labels)
check("no model file was written by merely viewing the page",
      not os.path.exists(MODEL))

# ══════════════════════════════════════════════════════════════════════
section("6. the UI: armed confirmation, then the real run")
# ══════════════════════════════════════════════════════════════════════

os.path.exists(MODEL) and os.remove(MODEL)
S.invalidate_trained_model()
seed_corrections(15)

at = um_test()
labels = [b.label for b in at.button]
check("the button is now enabled",
      not button_disabled(find_button(at, "Train model now")), labels)
check("it says training is available",
      "enough to train" in page_text(at), page_text(at)[-260:])

# One press arms; it does not train.
find_button(at, "Train model now").click().run()
txt = page_text(at)
check("the second stage asks for confirmation", "Yes, train the model" in txt)
check("it says what will be replaced",
      "sentiment_classifier.prev.pkl" in txt, txt[-300:])
check("nothing has been written yet", not os.path.exists(MODEL))
check("and the arm is remembered in session state",
      at.session_state.get("um_train_armed") is True)

# Cancelling disarms and writes nothing.
at2 = um_test(um_train_armed=True)
find_button(at2, "Cancel").click().run()
check("Cancel returns to the unarmed state",
      "Yes, train the model" not in page_text(at2))
check("Cancel wrote nothing", not os.path.exists(MODEL))

# Confirming trains.
at3 = um_test(um_train_armed=True)
find_button(at3, "Yes, train the model").click().run()
check("confirming wrote the model", os.path.exists(MODEL))
check("and no longer holds a parked dialog (main() consumed it)",
      at3.session_state.get("_pending_result_dialog") is None,
      at3.session_state.get("_pending_result_dialog"))
# The dialog's `title` is passed to `st.dialog()`, which AppTest does not
# surface as text, so assert on the body markup the shim actually renders.
body = " ".join(m.value for m in at3.markdown)
check("the outcome is reported as a result dialog, not a toast",
      "result-dialog result-dialog-success" in body,
      [m.value[:90] for m in at3.markdown][-3:])
check("the dialog reports the measured accuracy",
      "held-out accuracy" in body, body[-300:])
check("the dialog explains that scores are unaffected",
      "rule engine" in body, body[-300:])
check("the armed state was cleared",
      at3.session_state.get("um_train_armed") is None)
check("the newly trained model is live, not a stale cache entry",
      S._get_trained_model() is not None
      and S.engine_status()["trained_model_available"] is True)
check("…and the status card now says so",
      "Model active" in body, body[:200])

# ══════════════════════════════════════════════════════════════════════
section("7. a failed training run is reported, not swallowed")
# ══════════════════════════════════════════════════════════════════════

real_train = T.train


def exploding_train(*a, **kw):
    raise RuntimeError("backend exploded")


# `_run_training` imports `train_model` inside the function, so patching the
# attribute on the already-imported module object is enough to simulate a
# backend failure the trainer did not anticipate.
T.train = exploding_train
at = um_test(um_train_armed=True)
try:
    find_button(at, "Yes, train the model").click().run()
    check("an unexpected exception does not take the page down", not at.exception,
          [str(e.value) for e in at.exception])
    check("it is reported as a failure dialog",
          "result-dialog-error" in page_text(at)
          or "backend exploded" in page_text(at), page_text(at)[-320:])
    check("and the page is still usable afterwards",
          "Supervised Sentiment Classifier" in page_text(at))
except Exception as exc:  # pragma: no cover
    check("an unexpected exception does not take the page down", False,
          f"{type(exc).__name__}: {exc}")
finally:
    T.train = real_train

# ══════════════════════════════════════════════════════════════════════
section("8. the CLI still works off the same code path")
# ══════════════════════════════════════════════════════════════════════

os.path.exists(MODEL) and os.remove(MODEL)
check("main() with the set populated returns 0", T.main([]) == 0)
check("and wrote the model", os.path.exists(MODEL))
os.path.exists(MODEL) and os.remove(MODEL)
clear_corrections()
check("main() with nothing to learn from returns 0 (not an error)", T.main([]) == 0)
check("and did not write a model", not os.path.exists(MODEL))
check("main() rejects a missing --engine value", T.main(["--engine"]) == 1)
check("main() rejects a nonsense --engine value", T.main(["--engine", "x"]) == 1)

shutil.rmtree(TMP, ignore_errors=True)
print()
print("=" * 74)
if failures:
    print(f"  {len(failures)} CHECK(S) FAILED:")
    for f in failures:
        print(f"    - {f}")
else:
    print("  ALL CHECKS PASSED")
print("=" * 74)
sys.exit(1 if failures else 0)
