"""
download_nltk_data.py
----------------------
One-time setup script: downloads the NLTK data this project actually uses.
Run once after `pip install -r requirements.txt`:

    python download_nltk_data.py

Only `vader_lexicon` is required — sentiment.py uses NLTK's VADER lexicon
analyzer, and the optional trained classifier (train_model.py) uses a small
hand-rolled tokenizer (lowercase + strip punctuation, split on whitespace)
rather than `nltk.word_tokenize`, specifically so that training never depends
on NLTK's `punkt`/`punkt_tab` tokenizer data — whose required package name has
changed across recent NLTK versions and is a common source of confusing
"Resource not found" errors. No other NLTK data package is needed.

The script verifies each download by looking the resource back up, because
`nltk.download()` returns `True` even when it merely queued the package and
then failed (offline, proxy, TLS error). The old version printed "Done."
unconditionally, so a failed download looked like a successful one and the
app then ran with a silently missing lexicon.
"""

import sys

import nltk

PACKAGES = ["vader_lexicon"]


def _is_available(package: str) -> bool:
    """True when `package` can actually be loaded from disk right now."""
    probe = {"vader_lexicon": lambda: nltk.data.find("sentiment/vader_lexicon.zip")}
    try:
        probe[package]()
        return True
    except (LookupError, KeyError):
        return False
    except Exception:
        return False


def main() -> int:
    print("Downloading NLTK data for the FUTO IFT Feedback System\n")

    failures = []
    for package in PACKAGES:
        if _is_available(package):
            print(f"  [ok]   '{package}' is already present — skipping.")
            continue

        print(f"  [..]   '{package}' …")
        try:
            nltk.download(package, quiet=False)
        except Exception as exc:
            failures.append((package, f"download raised {type(exc).__name__}: {exc}"))
            continue

        # nltk.download() swallows most failures and still returns True, so the
        # only trustworthy check is to look the resource back up.
        if _is_available(package):
            print(f"  [ok]   '{package}' downloaded.")
        else:
            failures.append((package, "still not found after the download attempt"))

    if failures:
        print("\nSome NLTK data could not be downloaded:")
        for package, reason in failures:
            print(f"  - {package}: {reason}")
        print("\nCheck your internet connection, proxy and firewall, then re-run "
              "this script.\nUntil then the sentiment engine will report itself "
              "unavailable and every comment will be scored Neutral.")
        return 1

    print("\nDone. You can now run: streamlit run app.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
