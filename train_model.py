"""
train_model.py
---------------
Trains a local supervised sentiment classifier on admin-corrected
feedback labels and saves it for sentiment.py to load automatically.

Usage:
    python train_model.py            # train with the default backend
    python train_model.py --engine svm

Features:
- N-gram feature representation (unigrams + bigrams with MWE canonical tokens).
- Negation-aware and MWE-preserved tokenisation (via sentiment._tokenize).
- Held-out test evaluation (Accuracy, Precision, Recall, Macro F1).
- Scikit-learn preferred backend (LogisticRegression / LinearSVC) with an
  automatic fallback to NLTK NaiveBayesClassifier if scikit-learn is absent.
- Automatic model packaging with metadata (including library versions) into
  MODEL_PATH, written atomically, with the previous model kept as `.prev.pkl`.

IMPORTANT — the model supplies the sentiment LABEL only. sentiment.py always
computes the numeric score, the polarity proportions, the cues and the
confidence from its own rule pipeline, so a comment scores the same way
whether or not a .pkl happens to be present.
"""

from __future__ import annotations

import os
import pickle
import platform
import random
import shutil
import sys
from collections import Counter
from datetime import datetime

import nltk

import db
from config import MIN_TRAINING_SAMPLES, MODEL_PATH
from sentiment import FEATURE_SPEC, _features, _tokenize


# ── Try to import scikit-learn ──────────────────────────────────────
try:
    from sklearn.linear_model import LogisticRegression
    from sklearn.svm import LinearSVC
    from sklearn.pipeline import Pipeline
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics import classification_report, confusion_matrix
    _SKLEARN_AVAILABLE = True
except ImportError:
    _SKLEARN_AVAILABLE = False

LABELS = ["Positive", "Neutral", "Negative"]


def _calculate_metrics_nltk(classifier, test_set):
    """Calculates Accuracy, Precision, Recall, and F1 across sentiment classes
    for an NLTK NaiveBayes classifier.
    """
    if not test_set:
        return {"accuracy": 0.0, "macro_f1": 0.0}

    y_true = [label for _, label in test_set]
    y_pred = [classifier.classify(feat) for feat, _ in test_set]

    total = len(y_true)
    correct = sum(1 for yt, yp in zip(y_true, y_pred) if yt == yp)
    accuracy = correct / total if total else 0.0

    classes = [c for c in LABELS if c in set(y_true)]
    f1_scores = []

    print("\nDetailed Per-Class Performance:")
    print(f"{'Class':<12} {'Precision':<12} {'Recall':<12} {'F1-Score':<12}")
    print("-" * 48)

    for c in classes:
        tp = sum(1 for yt, yp in zip(y_true, y_pred) if yt == c and yp == c)
        fp = sum(1 for yt, yp in zip(y_true, y_pred) if yt != c and yp == c)
        fn = sum(1 for yt, yp in zip(y_true, y_pred) if yt == c and yp != c)

        precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = (2 * precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0
        f1_scores.append(f1)

        print(f"{c:<12} {precision:<12.1%} {recall:<12.1%} {f1:<12.1%}")

    macro_f1 = sum(f1_scores) / len(f1_scores) if f1_scores else 0.0
    print(f"\n{'Macro F1':<12} {'':<12} {'':<12} {macro_f1:<12.1%}")
    return {"accuracy": accuracy, "macro_f1": macro_f1}


def _train_sklearn(texts: list[str], labels: list[str], engine: str = "logreg"):
    """Trains a scikit-learn classifier using TF-IDF features + n-grams.

    Returns `(pipeline, metrics_dict, engine_type_str)`.

    The *raw* `Pipeline` is what gets stored. It used to be wrapped in a
    `_SklearnWrapper` class defined inside this function, and `pickle` records
    a class as `module.QualName`; a class nested in a function has a
    `QualName` containing `<locals>`, which cannot be looked up again when the
    app unpickles it in a different process. Every model the old code saved
    therefore failed to load — and `sentiment.py`'s `except Exception: pass`
    swallowed that, so training appeared to succeed while changing nothing.
    `sentiment.py` now branches on the bundle's `backend` key and calls
    `Pipeline.predict([text])` directly.
    """
    from sklearn.model_selection import train_test_split

    counts = Counter(labels)
    singletons = [c for c, n in counts.items() if n < 2]
    stratify = labels if len(counts) > 1 and not singletons else None
    if singletons and len(counts) > 1:
        print(f"[Notice] Not stratifying the split — {', '.join(singletons)} has fewer "
              f"than 2 samples.")

    if len(texts) < 5:
        print("[Error] At least 5 corrected comments are needed to hold any out "
              "for evaluation. Add more corrections and try again.")
        return None, None, None

    X_train, X_test, y_train, y_test = train_test_split(
        texts, labels, test_size=0.2, random_state=42, stratify=stratify,
    )
    if not X_test or not X_train:
        print("[Error] The train/test split produced an empty side. "
              "Add more corrected comments and try again.")
        return None, None, None

    vectorizer = TfidfVectorizer(
        ngram_range=(1, 2),
        min_df=1,
        max_features=8000,
        sublinear_tf=True,
        analyzer="word",
        token_pattern=r"\b[\w_-]+\b",   # preserves MWE underscore tokens
    )

    if engine == "svm":
        clf = LinearSVC(C=0.8, max_iter=2000, class_weight="balanced")
        engine_label = "Supervised LinearSVC (TF-IDF + Bigrams)"
    else:
        # NOTE: `multi_class="auto"` is deliberately absent. It was deprecated
        # in scikit-learn 1.5 and *removed* in 1.7, so passing it raised
        # TypeError on any current install.
        clf = LogisticRegression(
            C=1.0, max_iter=1000, class_weight="balanced", solver="lbfgs",
        )
        engine_label = "Supervised LogisticRegression (TF-IDF + Bigrams)"

    pipeline = Pipeline([("tfidf", vectorizer), ("clf", clf)])
    pipeline.fit(X_train, y_train)

    y_pred = pipeline.predict(X_test)
    report = classification_report(y_test, y_pred, output_dict=True, zero_division=0)
    macro_f1 = report.get("macro avg", {}).get("f1-score", 0.0)
    accuracy = report.get("accuracy", 0.0)

    print("\nDetailed Per-Class Performance:")
    print(classification_report(y_test, y_pred, zero_division=0))

    present = [c for c in LABELS if c in counts]
    if present:
        cm = confusion_matrix(y_test, y_pred, labels=present)
        print(f"Confusion Matrix ({' / '.join(present)}):")
        print(cm)

    return pipeline, {"accuracy": float(accuracy), "macro_f1": float(macro_f1)}, engine_label


def _library_versions() -> dict:
    """Versions of everything that decides whether a saved .pkl can be loaded.

    scikit-learn and NLTK both refuse to unpickle a model saved under a
    different version of themselves, so the bundle records them and the engine
    can report an actionable message instead of "no model available".
    """
    versions = {"python": platform.python_version()}
    for name in ("nltk", "sklearn", "numpy", "scipy"):
        try:
            versions[name] = __import__(name).__version__
        except Exception:
            versions[name] = None
    return versions


def training_readiness(session: str | None = None) -> dict:
    """How far along the training set is, without training anything.

    Split out of `train()` because the admin page needs to answer "can I train
    yet, and if not, how far off am I?" on *every* render — long before anyone
    presses a button. Running the trainer just to get that number would write
    a `.pkl` as a side effect of looking, which is exactly the sort of thing
    that should not happen inside a page render.
    """
    df = db.load_labeled_training_data(session=session, readonly=True)
    counts = Counter(df["label"].tolist()) if len(df) else Counter()
    usable = sum(counts.get(cls, 0) for cls in LABELS)
    return {
        "total": len(df),
        "usable": usable,
        "distribution": {cls: counts.get(cls, 0) for cls in LABELS},
        "required": MIN_TRAINING_SAMPLES,
        "remaining": max(0, MIN_TRAINING_SAMPLES - usable),
        "ready": usable >= MIN_TRAINING_SAMPLES,
        # A class with a single sample cannot be stratified and cannot be
        # evaluated, so "40 corrections" is not the same as "40 usable ones".
        # Surfacing it stops an admin spending an afternoon building a model
        # that cannot learn anything.
        "missing_classes": [c for c in LABELS if counts.get(c, 0) == 0],
        "singleton_classes": [c for c in LABELS if counts.get(c, 0) == 1],
    }


def train(engine: str = "logreg", session: str | None = None) -> dict:
    """Trains from the corrected labels and writes the `.pkl`. Returns a report.

    Callable from Python, not just the CLI. The whole point of the admin
    trigger is that an administrator can turn corrections into a model from
    inside the app — and that cannot shell out to `train_model.py`, because a
    subprocess on Streamlit Community Cloud has no shell, no writable temp
    space it can rely on, and no useful way to stream its output back.

    Returns a dict with `ok` and, on success, the metrics an admin needs to
    judge whether the model is worth keeping. `log` holds the human-readable
    trace, which `main()` prints and the admin page renders in a collapsible —
    so the CLI and the button produce the same report, from one code path.
    """
    log: list[str] = []

    def say(line: str = "") -> None:
        log.append(line)
        print(line)

    if engine not in ("logreg", "svm"):
        return {"ok": False, "reason": f"Unknown engine '{engine}'.",
                "log": log}

    # Read-only on purpose: training must not switch the live database to WAL,
    # add missing tables/columns, or delete expired password-reset rows.
    say(f"Reading labels from: {db.DB_PATH}  (read-only)")
    df = db.load_labeled_training_data(session=session, readonly=True)
    n_raw = len(df)
    say(f"Found {n_raw} human-verified sample(s) in the database.")

    counts = Counter(df["label"].tolist()) if n_raw else Counter()
    unknown = sorted(set(counts) - set(LABELS))
    if unknown:
        say(f"  [Warning] Ignoring unexpected label value(s): {', '.join(unknown)}")

    say("\nClass distribution:")
    peak = max(counts.values()) if counts else 0
    for cls in LABELS:
        cnt = counts.get(cls, 0)
        bar = "█" * int(cnt / peak * 20) if peak else ""
        say(f"  {cls:<12} {cnt:>4} samples  {bar}")

    usable = sum(counts.get(cls, 0) for cls in LABELS)
    if usable < MIN_TRAINING_SAMPLES:
        say(
            f"\n[Notice] Need at least {MIN_TRAINING_SAMPLES} corrected samples to train "
            f"a reliable supervised model (have {usable})."
            f"\nContinue reviewing & correcting comments on the admin Full Dashboard."
            f"\nThe system will continue using the high-performance VADER Academic Pro engine."
        )
        return {
            "ok": False,
            "reason": "not_enough_samples",
            "message": (
                f"{usable} of {MIN_TRAINING_SAMPLES} corrections needed. "
                f"{MIN_TRAINING_SAMPLES - usable} more to go."
            ),
            "samples": usable, "required": MIN_TRAINING_SAMPLES,
            "log": log,
        }

    if counts:
        dominant = counts.most_common(1)[0]
        minority = counts.most_common()[-1]
        if minority[1] > 0:
            imbalance = dominant[1] / minority[1]
            if imbalance > 3:
                say(f"\n[Warning] Class imbalance detected ({dominant[0]}: {dominant[1]} vs "
                    f"{minority[0]}: {minority[1]}, ratio {imbalance:.1f}×). "
                    f"Consider collecting more '{minority[0]}' samples.")

    df = df[df["label"].isin(LABELS)]
    texts = [str(t).strip() for t in df["comment"]]
    labels_list = list(df["label"])
    n = len(texts)

    # ── Choose backend ──────────────────────────────────────────────
    backend = "nltk"
    classifier = metrics = engine_type = None
    notes: list[str] = []

    if _SKLEARN_AVAILABLE:
        say(f"\n[Scikit-learn available] Training {engine} with TF-IDF + bigrams...")
        try:
            classifier, metrics, engine_type = _train_sklearn(texts, labels_list, engine=engine)
        except Exception as exc:
            say(f"[Warning] sklearn training failed ({type(exc).__name__}: {exc}); "
                f"falling back to NLTK NaiveBayes.")
            notes.append(f"scikit-learn failed ({type(exc).__name__}); used NLTK instead.")
            classifier = None
        if classifier is not None:
            backend = "sklearn"
    else:
        say("\n[Info] scikit-learn not installed. Training NLTK NaiveBayes on n-gram features.")
        notes.append("scikit-learn is not installed, so this model uses NLTK NaiveBayes.")

    if classifier is None:
        dataset = [(_features(_tokenize(text)), label) for text, label in zip(texts, labels_list)]
        random.seed(42)
        random.shuffle(dataset)
        split = max(1, int(len(dataset) * 0.8))
        train_set, test_set = dataset[:split], dataset[split:]
        say(f"Dataset Split: {len(train_set)} training, {len(test_set)} test samples.")
        say("Training NLTK NaiveBayes classifier...")
        classifier = nltk.NaiveBayesClassifier.train(train_set)
        metrics = _calculate_metrics_nltk(classifier, test_set)
        engine_type = "Supervised NaiveBayes (N-gram + MWE)"
        backend = "nltk"

    say(f"\n{'-' * 48}")
    say(f"  Held-out Test Accuracy : {metrics['accuracy']:.1%}")
    say(f"  Macro F1-Score         : {metrics['macro_f1']:.1%}")
    say(f"  Backend                : {engine_type}")
    say(f"{'-' * 48}")

    weak = metrics["accuracy"] < 0.60
    if weak:
        # Kept, but said out loud. An admin who spends an hour correcting
        # comments and gets a 41%-accurate model back has no way to tell
        # "my corrections were bad" from "there is not enough data yet", and
        # the honest answer is usually the second one.
        say("\n[Warning] Held-out accuracy is below 60%, so the classifier is more "
            "likely to hurt than help. The app still loads it — re-run after "
            "correcting more comments.")
        notes.append(
            f"Held-out accuracy was only {metrics['accuracy']:.0%}. More "
            "corrections are needed before this model is worth trusting."
        )

    os.makedirs(os.path.dirname(MODEL_PATH) or ".", exist_ok=True)
    if os.path.exists(MODEL_PATH):
        backup = os.path.join(os.path.dirname(MODEL_PATH),
                              "sentiment_classifier.prev.pkl")
        try:
            shutil.copy2(MODEL_PATH, backup)
            say(f"Previous model kept as {os.path.basename(backup)}.")
        except OSError as exc:
            say(f"[Warning] Could not back up the previous model: {exc}")
            notes.append(f"The previous model could not be backed up ({exc}).")

    bundle = {
        "classifier": classifier,
        "backend": backend,
        "meta": {
            "trained_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "n_samples": n,
            "accuracy": metrics["accuracy"],
            "macro_f1": metrics["macro_f1"],
            "engine_type": engine_type,
            "sklearn_available": _SKLEARN_AVAILABLE,
            "class_distribution": dict(Counter(labels_list)),
            # Kept in sync with sentiment.FEATURE_SPEC; a model built on a
            # different feature space is refused at load time.
            "feature_spec": FEATURE_SPEC,
            "versions": _library_versions(),
            # Trained by whom, and from where. `trained_by` is not cosmetic:
            # `model/` is gitignored, so a model that appears on a shared host
            # has to be attributable to whoever put it there.
            "trained_by": os.environ.get("USER") or os.environ.get("USERNAME") or "",
        },
    }

    # Write to a temp file and move it into place, so a crash or a full disk
    # cannot leave a truncated .pkl that fails to unpickle from then on.
    tmp_path = f"{MODEL_PATH}.tmp"
    try:
        with open(tmp_path, "wb") as fh:
            pickle.dump(bundle, fh, protocol=pickle.HIGHEST_PROTOCOL)
        os.replace(tmp_path, MODEL_PATH)
    except Exception as exc:
        if os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except OSError:
                pass
        # Previously this re-raised, which is right for the CLI (a non-zero
        # exit) and wrong for the button (a red traceback in the middle of the
        # admin page, with the real cause in the console nobody opens). Both
        # callers get `ok: False` and a message they can act on.
        return {
            "ok": False,
            "reason": "write_failed",
            "message": f"The model could not be saved ({type(exc).__name__}: {exc}).",
            "log": log,
        }

    say(f"\nSuccessfully saved the trained model to '{MODEL_PATH}'.")
    say("Note: the model supplies the sentiment LABEL only — the score, the "
        "polarity split and the confidence always come from the rule engine.")

    if backend == "nltk":
        say("\nMost Informative Sentiment Features:")
        try:
            classifier.show_most_informative_features(15)
        except Exception:
            pass

    return {
        "ok": True,
        "backend": backend,
        "engine_type": engine_type,
        "accuracy": metrics["accuracy"],
        "macro_f1": metrics["macro_f1"],
        "samples": n,
        "trained_at": bundle["meta"]["trained_at"],
        "model_path": MODEL_PATH,
        "weak": weak,
        "notes": notes,
        "log": log,
    }


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    engine = "logreg"
    if "--engine" in argv:
        if argv.index("--engine") + 1 >= len(argv):
            print("[Error] --engine needs a value: logreg or svm")
            return 1
        engine = argv[argv.index("--engine") + 1]
        if engine not in ("logreg", "svm"):
            # A usage error, not a training outcome, so it exits non-zero. The
            # earlier version folded this into `train()`'s return value, which
            # made an unrecognised flag and "not enough corrections" the same
            # exit code — a shell could not tell them apart.
            print(f"[Error] Unknown engine '{engine}'. Use 'logreg' or 'svm'.")
            return 1

    print("=" * 62)
    print("  FUTO IFT Feedback — Supervised Sentiment Model Trainer")
    print("=" * 62)
    result = train(engine=engine)
    # The CLI says to restart Streamlit, which is only true for the CLI: a
    # process that trained the model has a live `_get_trained_model` cache
    # holding the previous one, and the button clears it explicitly.
    if result["ok"]:
        print("Restart Streamlit for the application to activate this trained model.")
        return 0
    # "Not enough corrections" is the trainer's normal starting state, not a
    # failure of the tool, so it still exits 0. A genuine write failure does not.
    print(f"Not trained: {result.get('message') or result.get('reason')}")
    return 1 if result.get("reason") in ("write_failed",) else 0


if __name__ == "__main__":
    raise SystemExit(main())
