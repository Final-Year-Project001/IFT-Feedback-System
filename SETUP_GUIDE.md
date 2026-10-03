# FUTO IFT Smart Feedback System — Complete Setup Guide

This guide has two parts:

- **Part A** is a strict, numbered recipe. Do every step in order, top to
  bottom, without skipping ahead. By the end of Part A, the app is
  running on your computer and you've proven it works by creating an
  account, submitting feedback, and viewing the admin dashboard.
- **Part B** is optional extra setup (real email sending, training the
  sentiment model) — come back to these once Part A is working.
- **Part C** is reference material — file explanations, customization
  instructions, troubleshooting, and deployment. You don't read this
  top-to-bottom; you look things up in it as needed.

Every step tells you three things: **what to do**, **exactly what to
type or click**, and **what you should see afterward** so you know it
worked before moving to the next step. If what you see doesn't match,
stop and check the troubleshooting table in Part C before continuing.

---

## Before you start: what is this app, in plain terms?

This is a web application — it runs on your own computer, and you view
it in a normal web browser (Chrome, Edge, Firefox, etc.), the same way
you'd view any website, except only you can see it (unless you
deliberately publish it — that's covered later, in Part C).

It has two kinds of users: **students**, who log in and submit feedback
about their courses, lecturers, facilities, and curriculum; and **one or
more admins**, who log in and see analytics and trends across everyone's
feedback. All the data — accounts, submitted feedback, everything — is
stored in a single file on your computer called `futo_feedback.db`. You
don't need to install or configure any separate database software;
Python creates and manages this file automatically.

---

# PART A — Get it running

## Step 1: Check whether Python is already installed

Python is the programming language this entire project is written in.
You need version 3.10 or newer.

**What to do:** Open a terminal.
- **Windows:** Press the `Win` key, type `cmd`, and press `Enter`. A
  black window opens — this is the Command Prompt.
- **macOS:** Press `Cmd + Space`, type `Terminal`, press `Enter`.

**Type this exactly, then press Enter:**
```
python --version
```
(On macOS, if that says "command not found," try `python3 --version`
instead.)

**What you should see:** A line like `Python 3.12.3`. Any number `3.10`
or higher is fine.

**If instead you see an error** like `'python' is not recognized` or
`command not found` — Python isn't installed yet. Go to Step 2. If
Python is already installed and the version is 3.10+, skip to Step 3.

---

## Step 2: Install Python (only if Step 1 failed)

**Windows:**
1. Open your browser and go to **python.org/downloads**.
2. Click the yellow **Download Python** button (it auto-detects
   Windows).
3. Open the downloaded file to start the installer.
4. **This is the step people most often get wrong:** on the very first
   installer screen, at the bottom, there is a checkbox that says
   **"Add python.exe to PATH."** Click it so it's checked, *before*
   clicking anything else.
5. Now click **Install Now** and wait for it to finish, then close the
   installer.
6. Close your terminal window completely and open a brand new one
   (Step 1's instructions), then re-run `python --version` to confirm
   it now works.

**macOS:**
1. Go to **python.org/downloads**, download the macOS installer
   (`.pkg` file), open it, and click through the installer with default
   options.
2. Close and reopen Terminal, then run `python3 --version` to confirm.

---

## Step 3: Install a code editor (VS Code)

You don't strictly need this — you could edit files in Notepad and run
commands in a plain terminal — but VS Code combines both in one window,
which makes everything in this guide easier to follow.

**What to do:**
1. Go to **code.visualstudio.com** and download the installer for your
   operating system.
2. Run the installer, accepting the default options.
3. Open VS Code once installation finishes, to confirm it launches.

---

## Step 4: Unzip the project and open it in VS Code

**What to do:**
1. Find the ZIP file you were given (e.g. `futo_feedback_system.zip`).
2. Right-click it and choose **Extract All…** (Windows) or double-click
   it (macOS) to unzip it. Extract it somewhere easy to find, such as
   your Desktop. You should end up with a normal folder called
   `futo_feedback` containing files like `app.py`, `config.py`, and an
   `app_pages` folder.
3. Open VS Code.
4. Go to the top menu: **File → Open Folder…**
5. Navigate to and select the `futo_feedback` folder (the one containing
   `app.py` directly inside it — not its parent folder).
6. Click **Select Folder** (Windows) / **Open** (macOS).

**What you should see:** On the left side of VS Code, a file list
(called the Explorer) showing `app.py`, `config.py`, `auth.py`, an
`app_pages` folder, and so on.

---

## Step 5: Open a terminal inside VS Code

Every command in the rest of this guide gets typed into this terminal.

**What to do:**
1. In VS Code's top menu, click **Terminal → New Terminal**.
2. A panel opens at the bottom of the VS Code window with a command
   prompt in it, already pointed at your `futo_feedback` folder.

**What you should see:** A cursor waiting for input, on a line ending in
something like `...\futo_feedback>` (Windows) or `...futo_feedback %`
(macOS). If it doesn't say `futo_feedback` at the end, you opened the
wrong folder in Step 4 — go back and redo it.

**Keep this terminal panel open for the rest of Part A.** If you ever
close VS Code and come back later, redo just this step to get a new
terminal before continuing.

---

## Step 6: Create a virtual environment

**What this means, in plain terms:** A virtual environment is a private,
isolated copy of Python just for this project, so the packages this app
needs don't get mixed up with anything else Python-related on your
computer. This is standard practice and something a project supervisor
will expect to see.

**What to do:** In the terminal from Step 5, type each line below and
press Enter after each one. Wait for each to finish before typing the
next.

**Windows:**
```
python -m venv venv
venv\Scripts\activate
```

**macOS:**
```
python3 -m venv venv
source venv/bin/activate
```

**What you should see:** After the second command, the very start of
your terminal's prompt line changes to show `(venv)` in front of
everything else, e.g. `(venv) C:\Users\You\futo_feedback>`.

**Important — remember this:** Every single time you close and reopen
the terminal to keep working on this project (today, tomorrow, next
week), you must re-run the second command above (`venv\Scripts\activate`
or `source venv/bin/activate`) first, before running anything else. If
you forget, you'll get "module not found" errors even though everything
is installed correctly — it just means you're not inside the virtual
environment.

**If you have Anaconda installed:** Anaconda sometimes auto-activates
its own `(base)` environment in every new terminal, which can look
similar to `(venv)` at a glance but is a completely different, separate
copy of Python — one that doesn't have this project's packages
installed at the right versions. If your prompt shows `(base)` instead
of `(venv)` after running the activate command above, or shows both,
run this to double check which Python is actually active:
```
python -c "import sys; print(sys.executable)"
```
The path it prints should contain your project's `venv` folder (e.g.
`...\futo_feedback\venv\Scripts\python.exe`). If instead it points into
an `anaconda3` folder, the venv isn't really active — close the
terminal, open a fresh one (Step 5), and run the activate command again
as the very first thing before typing anything else.

---

## Step 7: Install the project's dependencies

**What this means:** The app depends on a handful of external Python
packages (Streamlit for the web interface, Pandas for handling data,
Plotly for charts, NLTK for sentiment analysis) that don't come with
Python by default. `pip` is Python's package installer — the tool that
downloads and installs them. `requirements.txt` is a plain text file in
the project that lists exactly which packages and versions are needed.

**What to do:** With `(venv)` still showing at the start of your
terminal prompt, type:
```
pip install -r requirements.txt
```
Press Enter and wait — this downloads and installs several packages, so
It can take one to a few minutes depending on your internet connection.
You'll see a lot of text scroll past; that's normal.

**What you should see:** The scrolling stops and you're returned to a
normal prompt, with no red "ERROR" text at the very end. (Some
yellow/informational warnings are fine and can be ignored.)

**This step requires an internet connection.** If it fails with a
connection error, check you're online and try the command again.

---

## Step 8: Download the sentiment-analysis data

**What this means:** The app scores every feedback comment as Positive,
Neutral, or Negative using a component called VADER, part of the NLTK
library you just installed. VADER needs a small data file (a "lexicon" —
essentially a big list of words with pre-scored emotional weight) that
isn't included in the pip install itself and has to be downloaded once,
separately.

**What to do:** Still in the same terminal, type:
```
python download_nltk_data.py
```

**What you should see:** A line saying `Downloading NLTK package:
vader_lexicon ...` followed by `Done. You can now run: streamlit run
app.py`.

**This also requires an internet connection**, but it's a very small,
fast download (well under a second on most connections). You only ever
need to run this command once per computer — not once per project, and
not again every time you work on the app.

---

## Step 9: Run the app for the first time

**What to do:** Still in the same terminal, type:
```
streamlit run app.py
```

**What you should see, in order:**
1. In the terminal, several lines of text appear, ending with something
   like:
   ```
     Local URL: http://localhost:8501
   ```
2. Within a second or two, your default web browser opens automatically
   to that address and shows the app.
3. Inside your `futo_feedback` folder there should now be
   `futo_feedback.db` — the database file — plus the two WAL sidecars
   `futo_feedback.db-wal` and `futo_feedback.db-shm`. Check the VS Code
   file list on the left; you may need to right-click and choose
   "Refresh." **A copy of this project already ships with a populated
   `futo_feedback.db` containing real data, so "the file exists" proves
   nothing.** What proves the app started is that the three files are
   **newer than the moment you launched it** — sort the file list by
   *Date Modified* and confirm `-wal` and `-shm` appeared too. They are
   SQLite's write-ahead log and shared-memory index, and they only appear
   while a process has the database open.

**If you want to start from an empty database**, see *Resetting the
database* in Part C — and read the warning there first, because it
destroys all feedback.

**What the app should look like:** A centered page with a toggle showing
**Student Portal** / **Administrator**, and below it a "Welcome back"
sign-in form.

**Leave this terminal window open and running** for as long as you want
to use the app — closing it, or pressing `Ctrl+C` inside it, stops the
app and the browser page will stop working. If that happens, just run
`streamlit run app.py` again to restart it (you don't need to redo Steps
6–8 again unless you reopened the terminal from scratch, in which case
redo Step 6's activate line first).

---

## Step 10: Create your first account (as a student)

**What to do, exactly:**
1. In the browser, make sure the toggle near the top says **Student**
   is selected (it's the default).
2. Look below the sign-in form for two buttons side by side:
   **"Create an account"** and **"Forgot password?"**. Click
   **"Create an account."**
3. A form appears with these fields, top to bottom: **Full Name**,
   **Choose a Username**, **Email Address**, **Academic Level**,
   **Password**, **Confirm Password**.
4. Fill them in:
   - Full Name: your real name is fine for testing, e.g. `Jane Doe`.
   - Choose a Username: something short with no spaces, e.g.
     `jane.doe` (must be at least 4 characters — letters, numbers, dots,
     dashes, and underscores are allowed).
   - Email Address: any email you can access (it doesn't have to be
     real for this first test, but use a real one later once you set up
     email in Part B, so you can test password recovery for real).
   - Academic Level: pick any option from the dropdown, e.g.
     `300 Level`.
   - Password: at least 8 characters, e.g. `TestPass123`.
   - Confirm Password: type the exact same password again.
5. Click the **"Create Account →"** button at the bottom of the form.

**What you should see:** A green success message ("Account created!
Taking you to your dashboard…") and then, after less than a second, you
land on the app's **Home** page, showing your name in a welcome message
and some statistic cards.

**If you instead see red error text under the form:** it's telling you
exactly what to fix (e.g. "Passwords do not match," or "Username already
taken" if you're repeating this step). Fix the highlighted field and
click **Create Account →** again.

---

## Step 11: Sign out and sign back in

This proves your account and password actually work, not just that
registration worked.

**What to do:**
1. On the left side of the screen is a sidebar with your name and a
   navigation menu. Near the bottom of that sidebar is a button labeled
   **"Sign Out."** Click it.
2. You're returned to the sign-in screen. With **Student Portal** still
   selected in the toggle at the top, type the **email address** and
   **password** you just chose into the **"Email Address"** and
   **"Password"** fields, and click **"Sign In →."**

   There is no username field on this form, and there is not supposed to
   be — students sign in with the email address they registered. Your
   username still exists (you chose it at registration) and is shown on
   the sidebar once you're signed in; it is what your feedback records are
   stamped with.

**What you should see:** You're back on the Home page, logged in as the
same account.

---

## Step 12: Submit a test piece of feedback

This confirms the core feature of the whole app works end to end.

**What to do:**
1. In the left sidebar, under "Navigation," click one of the four
   category names — for example, **"Course Content."**
2. You'll see a structured section first (a dropdown to pick a course,
   and a set of checkboxes for topics you'd like emphasized) — pick
   anything, or leave it blank, it's optional.
3. Below that, a **"Rate from 1 (Poor) to 5 (Excellent)"** slider —
   drag it to any number.
4. Below that, a text box labeled **"Provide a detailed account of your
   experience"** — type a real sentence, e.g. `The lecturer was very
   engaging and the labs were genuinely useful.` (A comment is required —
   you can't submit without one.)
5. Click **"Submit Feedback →."**

**What you should see:** A green confirmation banner, then the page
switches to a read-only **"Submission Confirmed"** card summarising what
you submitted, with a brief confetti animation. The editable form is gone
and there is no submit button left — returning to that same category later
shows the same read-only summary. That is intentional: the constraint is
one submission per student, per category, **per academic session** (so if
a new session is later set as the default, you get a fresh set of forms
for it).

**If you instead see "You have already submitted feedback for this
category and academic session,"** the row already existed — usually
because this category was submitted in an earlier test. That message
reflects a uniqueness rule enforced by the database, not a failed save;
check *My Statistics* to see what is on record.

---

## Step 13: Sign in as the administrator and view the dashboard

Every fresh copy of this project automatically creates one built-in
admin account the very first time you run it (Step 9 created it, behind
the scenes, inside `futo_feedback.db`). Its default login is:

- Username: `admin001`
- Password: `password123`

**What to do:**
1. Click **"Sign Out"** in the sidebar again.
2. On the sign-in screen, click the toggle at the top to switch it from
   **Student Portal** to **Administrator**. Notice the whole page changes
   to a plain, centered card — this is deliberate (an admin console is
   meant to look different from a student-facing landing page).
3. Enter Email `admin001@futo.edu.ng` and Password `password123`, then
   click **"Sign In."**

**What you should see:** A sidebar labeled "Analytics Dashboard" with
four items: **Overview**, **Full Dashboard**, **Decision Insights** and
**User Management**. Click **Overview** — you should see summary numbers,
including at least one response (the one you submitted in Step 12), and a
couple of charts.

**Checkpoint — if you've reached here successfully, the app is fully
working.** Everything from this point on (Part B) is optional
enhancement, not required for the app to function.

### ⚠ Change the default admin password now — before anything else

`admin001` / `password123` is a known, public default. It exists only so
that a fresh checkout can be signed into once. **Do not skip this**, and do
not leave it until after you have entered real student data — anyone who
reads this repository knows the credentials.

**How to change it (do it in the app — do NOT delete the database):**

1. Stay signed in as `admin001`.
2. In the left sidebar, click **"User Management."**
3. In the *Account Directory*, click the row for the account you want to
   change (or search for the username to find it).
4. In the *"Change password"* panel that appears, type the new password
   twice and give a short reason.
5. Click **"Update password."**

The new password takes effect immediately and you are not signed out.

**Never "reset" a forgotten admin password by deleting
`futo_feedback.db`.** That file is the whole application state — every
student account, every feedback row, every admin note, every academic
session. Deleting it destroys all of it, and the app will re-seed
`admin001` / `password123` from scratch on next start. If you genuinely
cannot sign in and no other admin account exists, see
*Recovering from a lost admin password* in Part C — it is a surgical SQL
update, not a deletion.

---

# PART B — Optional but recommended setup

You can stop after Part A and the app will work correctly for a demo or
local testing. The two things below make it behave more like a real
production system: sending real emails, and improving the sentiment
model's accuracy on your specific data.

## Step 14: Set up real email sending

Right now, without this step, the app still works completely — but
instead of *emailing* a password-reset code, it displays the code
directly on screen with a warning that this is for local testing only.
Setting up real email fixes that, and also enables the "your account was
created" and "thank you for completing all feedback categories" emails.

### 14.1 — Turn on 2-Step Verification on a Google account

You need a Gmail address to send from (a personal one is fine for
testing; a real deployment would use a department mailbox).

1. Go to **myaccount.google.com** and sign in.
2. In the left menu, click **Security**.
3. Find **"2-Step Verification"** and make sure it's turned **On**. If
   it isn't, click it and follow Google's prompts to turn it on (usually
   verifying your phone number).

*(This step is a prerequisite set by Google — you cannot generate an App
Password, which is what the next step needs, until 2-Step Verification
is on.)*

### 14.2 — Generate a Gmail "App Password"

An App Password is a special 16-character code Google generates
specifically for one application to use, separate from your real Google
password — safer, because if it ever leaks, you can revoke just that one
code without changing your main password.

1. Go to **myaccount.google.com/apppasswords** (you must already be
   signed in, and 2-Step Verification must be on, or this page won't let
   you in).
2. Under "App name," type something recognizable, e.g. `FUTO Feedback
   System`, and click **Create**.
3. Google shows you a 16-character code in a yellow box, in the format
   `xxxx xxxx xxxx xxxx`. **Copy this now** — you won't be able to see
   it again after closing this screen (you can always generate a new one
   later if you lose it).

### 14.3 — Add your email credentials to the project

**If you don't see a `.streamlit` folder in the project at all** — this
folder's name starts with a dot, and some Windows zip tools (and some
Explorer view settings) hide or skip dot-prefixed folders when
extracting, even though the zip file itself has them. Two ways to fix
that first:
- In Windows Explorer, open the **View** tab and turn on **Hidden
  items** — then look again.
- If it's still genuinely missing after that, just create it by hand:
  in VS Code's file list, right-click the `futo_feedback` folder →
  **New Folder** → name it exactly `.streamlit` (the leading dot
  matters — Streamlit only looks for that exact name). Then create two
  files inside it the same way (**New File**): one named `config.toml`
  and one named `secrets.toml.example`, and paste in the content below
  for each.

  `config.toml`:
  ```toml
  [theme]
  base = "light"
  primaryColor = "#2563eb"
  backgroundColor = "#f6f8fb"
  secondaryBackgroundColor = "#ffffff"
  textColor = "#0f172a"
  font = "sans serif"
  ```
  `secrets.toml.example`:
  ```toml
  SMTP_HOST = "smtp.gmail.com"
  SMTP_PORT = "587"
  SMTP_USERNAME = "your.department.mailbox@gmail.com"
  SMTP_PASSWORD = "your-16-character-app-password"
  SMTP_FROM_EMAIL = "your.department.mailbox@gmail.com"
  ```
  (`config.toml` is what makes the app's tables and charts render with
  the right light theme instead of guessing — see the note inside the
  file itself for why it matters. `secrets.toml.example` is just a
  template; Step 14.3 below has you copy it to a real `secrets.toml`.)

Now, to actually add your own credentials:

1. In VS Code's file list, find the `.streamlit` folder and inside it
   the file `secrets.toml.example`.
2. Right-click `secrets.toml.example` → **Copy**, then right-click the
   `.streamlit` folder → **Paste**. This creates a duplicate.
3. Rename the duplicate file to exactly: `secrets.toml` (remove the
   `.example` part — right-click the new file → **Rename**).
4. Open `secrets.toml` and edit it to look like this, replacing the
   placeholder values with your own:
   ```toml
   SMTP_HOST = "smtp.gmail.com"
   SMTP_PORT = "587"
   SMTP_USERNAME = "youraddress@gmail.com"
   SMTP_PASSWORD = "the16characterapppassword"
   SMTP_FROM_EMAIL = "youraddress@gmail.com"
   ```
   For `SMTP_PASSWORD`, paste the App Password from Step 14.2 — you can
   include or remove the spaces in it, both work.
5. Save the file (`Ctrl+S` / `Cmd+S`).

### 14.4 — Restart the app and test it

1. Click into the terminal running the app and press `Ctrl+C` to stop
   it.
2. Run `streamlit run app.py` again.
3. In the browser, register a brand-new test account (Step 10) using an
   email address you can actually check.
4. Check that inbox — you should receive a "Welcome" email within a
   minute or two. If you do, email is working correctly.
5. To test password recovery for real: sign out, click **"Forgot
   password?,"** enter that account's username and email, and confirm a
   real 6-digit code arrives by email instead of being shown on screen.

**Never share or commit `secrets.toml` anywhere public** (like GitHub) —
it's already listed in this project's `.gitignore` file specifically so
Git won't accidentally track it.

### 14.5 — If you get "Connection unexpectedly closed: timed out"

This specific error means your computer couldn't even *reach* Gmail's
mail server — it's not a wrong username or password (a bad login gets a
different, clearer "authentication failed" response). Almost always
this means something on the network is silently blocking outbound email
traffic. This is extremely common on:
- Campus Wi-Fi (many universities block outbound SMTP by policy)
- Some mobile network / ISP connections
- Antivirus software with "web protection" or "email scanning" turned on
- A VPN

**Confirm it's the network, not your credentials.** Open a terminal,
activate your virtual environment, then run `python` to open a Python
shell and paste this in (replace the placeholders):

```python
import smtplib, ssl
host, port = "smtp.gmail.com", 587
with smtplib.SMTP(host, port, timeout=10) as s:
    s.starttls(context=ssl.create_default_context())
    s.login("youraddress@gmail.com", "your16charapppassword")
    print("Connected and logged in successfully!")
```

- If this hangs and eventually times out the same way → it's your
  network. Try a completely different network (e.g. a phone's mobile
  hotspot) and run it again — if that works, the original network is
  the culprit, and you'll need to use that alternate network (or ask
  campus/network it to unblock port 587/465) whenever you want email to
  actually send.
- If this fails instantly with an authentication error instead of
  hanging → it's your `SMTP_USERNAME`/`SMTP_PASSWORD`, not the network.
  Double check the App Password was copied correctly (Step 14.2).
- Try changing `SMTP_PORT` to `"465"` in `secrets.toml` and re-running
  the test with `smtplib.SMTP_SSL(host, 465, ...)` instead — some
  networks block one port but not the other.

**In the meantime, the app still works without this fixed.** When an
email genuinely fails to send, the app doesn't leave anyone stuck —
the "Forgot password" screen shows the reset code directly on screen
as a fallback instead, clearly labeled that this is for local
testing/troubleshooting only.

---

## Step 15: Train the sentiment classifier on your own data

**Why this is optional and can wait:** the app already scores sentiment
accurately out of the box using VADER (a proven, deterministic
rule-based method — explained fully in Part C). This step lets you go
one step further: train an additional model specifically on your own
department's actual feedback wording, which can outperform the generic
baseline once you have enough real, human-verified examples.

**What to do:**
1. Log in as an admin and go to **Full Dashboard** in the sidebar.
2. Scroll down to the **Sentiment Engine** section. Its diagnostics card
   shows which engine is currently active (before any model exists:
   **"VADER Academic Pro"**), plus the lexicon size, the confidence range
   actually in force, and — importantly — a list of any
   **engine problems**. If that list is non-empty, read it before going
   further: it says exactly why a model is not being used (a stale
   `feature_spec`, a corrupt `.pkl`, a shape mismatch, a missing
   scikit-learn install).
3. Below that, click to open the expander titled **"Review & correct
   sentiment labels (0 corrected so far)."**
4. You'll see a table of every comment submitted so far, with its
   current sentiment label in a dropdown column. Wherever you disagree
   with the automatic label, click that row's dropdown and pick the
   correct one (Positive / Neutral / Negative).
5. Click **"Save corrections"** once you've reviewed some rows. Repeat
   this over time as more feedback comes in — the number in the
   expander's title increases with each save.
6. Once that count reaches **40 or more** (this threshold is
   configurable — `MIN_TRAINING_SAMPLES` in `config.py`), stay in the app
   and open **User Management** in the sidebar. At the bottom of the page
   is the **Supervised Sentiment Classifier** card. It reads the
   corrections directly and shows how many are ready, how many are
   required, and the Positive / Neutral / Negative split — so the
   threshold is never something you discover by pressing a button that
   then refuses.
7. When it is ready, the **Train model now** button becomes enabled. Click
   it, then click **Yes, train the model**. Training is deliberately
   **two clicks**: like every other irreversible action in this app, it
   will not start on a single press, and **Cancel** backs out without
   writing anything.
8. Training runs inside the running app — there is no shell on Streamlit
   Community Cloud, so it is done in-process rather than by launching a
   script. When it finishes, a **result dialog** reports how many
   corrections it learned from, the held-out accuracy, the macro F1, and
   the fact that it is live. The new model is picked up immediately: no
   `Ctrl+C`, no restart, no browser refresh. If accuracy is below 60% the
   dialog says so plainly and still loads the model — a weak model can
   only change the label, never the score (see the note at the end of
   this step).

**Training from a terminal instead.** The same trainer is still a script,
which is useful if you want it in a cron job or want to pick the
algorithm. Stop or keep the app running, then:

```
python train_model.py
```

`--engine logreg` is the default; `--engine svm` selects the linear SVM.
The script writes `model/sentiment_classifier.pkl` atomically — to a
temporary file first, then renamed into place — so an interrupted run can
never leave a half-written model behind that later loads as corrupt. It
prints the held-out accuracy and the per-class report, and keeps the
previous model as `.prev.pkl`.

If you use the terminal route rather than the in-app button, **restart the
app** — `Ctrl+C` then `streamlit run app.py`. **Simply revisiting the page
is not enough.** The model is loaded once per process and cached, so a
browser refresh re-reads the same cached result and the engine line will
look unchanged no matter what is on disk. (The in-app button refreshes
that cache for you, which is why it needs no restart.) This is also why
the engine name alone is not proof the model is working: it is a label,
not a live health check.

**How to actually verify the trained model is in use.** A real check,
not a reload:

1. On the **Full Dashboard**, open the **Live Sentiment Preview** box.
2. Type a sentence whose polarity is unambiguous and which contains
   domain vocabulary the rules would weigh heavily — for example
   *"The lab equipment is excellent and the lecturer is very helpful."*
   Click **Analyse**. Expect **Positive**.
3. Clear it and type *"The projector is broken and the lab network is
   useless."* Expect **Negative**.
4. If both land on the right label, the pipeline is working end to end.
   If the engine diagnostics card lists a problem, that line names the
   cause — fix it before assuming the model is at fault.

You can repeat Step 15 at any time as more corrected data accumulates —
each training run retrains from scratch on the complete, current set of
corrections.

> **A note on what the trained model actually changes.** it supplies the
> sentiment **label** only. The numeric score, the positive/neutral/
> negative split, the highlighted cues and the confidence figure are
> always produced by the rule pipeline, whether or not a model is
> present. That is deliberate: it means a comment scores identically
> whether you have trained a model or not, so turning the model on or off
> cannot silently change what the confidence numbers mean.

---

# PART C — Reference material

## What each file does (plain English)

| File | What it's responsible for |
|---|---|
| `app.py` | The app's entry point. Decides which page to show, builds the sidebar, loads the CSS. This is the file you run. |
| `st_compat.py` | A small safety net: some Streamlit buttons use an `icon=` option only available in newer Streamlit versions. This file detects your installed version and skips that option gracefully instead of crashing if it's not supported — see the Troubleshooting table if you ever hit an `icon` related error anyway. |
| `config.py` | Every setting you're likely to want to change lives here: the list of courses, checklist items, the current academic session, the seeded admin account, email sender name, and sentiment-training threshold. |
| `auth.py` | Checks whether a typed username/password is correct, checks whether a new registration is valid (e.g. passwords match, username isn't taken), and a simple "too many failed logins" lockout. |
| `db.py` | Everything to do with the database file: creating accounts, saving feedback, generating and checking password-reset codes, saving admin notes, managing academic sessions, and the guarded user-deletion / restoration engine (with the audit log it writes to). It also migrates an older database file in place, adding anything missing rather than crashing. |
| `sentiment.py` | Scores a comment's sentiment. The domain-lexicon rule engine (shown in the app as "VADER Academic Pro") is always what produces the score, the polarity split, the cues and the confidence; a trained classifier, if one exists, supplies the label only (Step 15). |
| `train_model.py` | Trains that classifier from admin-corrected data. It can be run as a script (`python train_model.py`, with `--engine logreg|svm`) or driven in-process from the **Train model now** button on the User Management page (Step 15). |
| `download_nltk_data.py` | A script you run once per computer (Step 8) to fetch the NLTK corpora the sentiment engine needs. |
| `email_service.py` | Sends emails via SMTP (Step 14) — registration confirmations, password-reset codes, submission and completion acknowledgements, password-changed notices. Fully optional: with no SMTP configured the app still works and just skips the mail. |
| `charts.py` | Builds every chart (bar, radar, pie, line) shown in the app, using Plotly. |
| `components.py` | Small reusable building blocks used across every page — metric cards, alert boxes, page headers — plus the two helpers that keep user-typed text safe: `esc()`, and `html_alert()`, which escapes by default and only emits raw HTML if you explicitly ask for it. |
| `icons.py` | The small icons used throughout the interface. Every one is an SVG path stored locally in this file and inlined at render time, so nothing is fetched from the internet. |
| `styles.py` | All of the app's visual styling (colors, spacing, fonts) in one place. |
| `app_pages/login.py` | The sign-in, create-account, and forgot-password screens. |
| `app_pages/home.py` | The student's landing page after signing in. |
| `app_pages/feedback_form.py` | The four feedback category forms. |
| `app_pages/my_stats.py` | A student's personal submission history and charts. |
| `app_pages/admin_overview.py` | The admin's landing page. |
| `app_pages/full_dashboard.py` | The admin's detailed analytics, CSV export, and the sentiment-correction tool from Step 15. |
| `app_pages/decision_insights.py` | The admin's priority-ranked recommendations per category, plus the action-notes tool. |
| `app_pages/user_management.py` | The admin's account directory: search, sort and filter every user; reset any account's password; permanently delete an account and all its feedback behind a two-stage confirmation; the audit trail with one-click restore; and the **Supervised Sentiment Classifier** card that trains the model in-app (Step 15). |
| `tests/` | A folder of verification scripts. Nothing here runs when you use the app — it exists so you can prove the app still works after changing something. See "Verifying your build" below. |

## Verifying your build

After you change any file in this project, you can check you haven't broken
anything:

```
.venv\Scripts\python.exe tests\run_all.py
```

You should see a line per test group ending in `0 failed`, and a final line
reading `0 failed, 0 suite(s) failed`. There are 20 groups and it takes
roughly five minutes — the long ones at the end open the real app in a
headless browser and click through it, so be patient.

It is safe to run. The end-to-end tests copy your real database to a
temporary folder using SQLite's own backup API and work on the copy, so
running the tests **cannot** modify your students' feedback. If you add a new
feature, running this is how you find out you broke something three files
away.

Some of the checks test the *testers* rather than the app — three scripts
prove that the XSS scanner, the undefined-name scanner and the icon sweep
genuinely detect problems instead of always reporting success. If one of
those fails, the fix is usually in the checker, not the app.

## Page-by-page tour

**Student sidebar:**
| Page | What's on it |
|---|---|
| Home | Your completion progress, and a card for each of the 4 categories showing whether you've submitted it yet |
| Course Content / Lecturer Teaching Style / Facilities / Curriculum | The feedback form for that category (or, if already submitted, a read-only summary of what you sent) |
| My Statistics | Your own submission history and two personal charts |

**Admin sidebar (Analytics Dashboard):**
| Page | What's on it |
|---|---|
| Overview | Headline numbers and two quick charts across all feedback |
| Full Dashboard | A full set of charts, a session filter, per-category breakdowns, structured-data tables, a CSV export button, the raw data table, and the sentiment review/correction tool |
| Decision Insights | Each category ranked by how urgently it needs attention, with a written recommendation and an editable action note |
| User Management | Every account, searchable and sortable, with password changes, a guarded permanent delete that cascades to the account's feedback, the audit trail of who did what, and the button that trains the sentiment classifier in-app |

## Changing the seeded admin password

**Do this in the app.** Sign in as `admin001`, open **User Management** in
the sidebar, select the account, and use the **Change password** panel. It
takes effect immediately and does not sign you out. Full walkthrough in
Part A, Step 13.

The `config.py` route below only exists for the case where you are
preparing a *fresh* database and have not run the app yet.

### Changing the seed for future installs only

1. Open `config.py` in VS Code.
2. Find the `ADMIN_SEED_ACCOUNTS` block and change
   `"password": "password123"` to a new password of your choosing.
3. **This only affects brand-new databases.** `db.seed_admins()` runs on
   startup and inserts an account only if that username does not already
   exist, so an account already in your `futo_feedback.db` keeps its
   current password no matter what you put here. It is a seed, not a
   synchronisation mechanism — don't use it to change a password on a
   database that already exists, and above all don't delete the database
   to force it to apply.

## Recovering from a lost admin password

If you are the only admin and have forgotten the password, the fix is one
SQL row. It does **not** touch any other data.

**What to do:**
1. Stop the app (`Ctrl+C` in the terminal running it). Do not skip this —
   SQLite will refuse the write while the app holds the database open.
2. In your `.venv`, run:

   ```bash
   python -c "import db; print(db.admin_set_password('admin001', 'NewPassword123'))"
   ```

   Replace `admin001` with the username and `NewPassword123` with the new
   password (8 characters or more). It prints
   `(True, 'Password updated…')` on success.
3. Run `streamlit run app.py` again and sign in.

`admin_set_password` writes a PBKDF2-HMAC-SHA256 hash with a fresh random
salt — the same format used by every password the app sets today.

### Accounts still on the old unsalted hash

A copy of this project from before the hashing change may hold a password as
an unsalted SHA-256 digest. Those accounts still sign in, but the moment they
do the app holds them on a **Choose a New Password** screen until they set a
new one. No page renders behind it and the sidebar is hidden, so the step
cannot be skipped. The screen refuses to accept the password they just signed
in with, so the stored row is always genuinely re-hashed as PBKDF2-SHA256 with
a fresh salt; nothing else about the account changes. When it succeeds, a
**Password Updated** dialog confirms it and the person is already signed in.

There is nothing to trigger or configure: on every sign-in the app reads the
stored hash (`db.password_is_legacy`) and decides from the row alone. There is
no session flag to clear, no migration script to run, and no way for an
already-upgraded account to get stuck on the screen.

## Starting a new academic session

**Do this in the app, not by editing `config.py`.**

**What to do:**
1. Sign in as an admin and open **Full Dashboard**.
2. Scroll to **Academic Sessions Management**.
3. Create the new session (e.g. `2026/2027`), tick **Set as active
   default**, and save.

Everything the app does afterwards follows that: new submissions are
stamped with the new session, and the sidebar session selector defaults to it.

**The `CURRENT_SESSION` constant in `config.py` is only the fallback** for
a database that has no sessions configured at all, and for the column
default. Editing it does **not** switch the running app's session, because
the active session is read from the `academic_sessions` table once you
have any. A copy of this documentation used to tell you to edit it; that
was wrong.

Existing data is never re-stamped — it stays tagged with whichever session
was current when it was submitted, and remains fully visible via the
session filter dropdown on the admin pages. Students get a fresh set of
forms for a new session, because the one-submission-per-category rule is
enforced **per session**.

## Adding or removing checklist items, courses, or facilities

Open `config.py`. Each checklist is a plain Python list of strings —
add a new line in the same format to add an item, or delete a line to
remove one. Relevant lists: `COURSE_CONTENT_EMPHASIS_AREAS`,
`TEACHING_STYLE_METHODS`, `TEACHING_STYLE_CHALLENGES`,
`FACILITIES_ITEMS`, `CURRICULUM_ALIGNMENT_AREAS`,
`CURRICULUM_OUTDATED_AREAS`. No other file needs to change.

**Courses work a little differently, on purpose.** The Course Content
form asks the student to pick their semester (Harmattan or Rain) first,
then only shows courses from *that semester, at their own registered
academic level* — a 300 Level student picking Rain semester sees only
300 Level Rain courses, not the full catalogue. This is driven by
`COURSES_BY_LEVEL_SEMESTER` in `config.py`: a dictionary keyed by level
("100" through "500"), each holding a `"Harmattan"` list and a
`"Rain"` list, sourced from the Department Handbook's official syllabus
tables. To add, remove, or correct a course:
1. Open `config.py` and find `COURSES_BY_LEVEL_SEMESTER`.
2. Find the level and semester (e.g. `"300": {"Harmattan": [...], "Rain": [...]}`)
   and add/edit/remove a line in the same `"CODE – Title"` format.
3. That's it — the Course Content dropdown reads straight from this
   dictionary. (The optional course field on Lecturer Teaching Style
   uses `courses_for_level()`, which shows both semesters combined for
   that level — since a lecturer might be relevant across the whole
   year, not just one semester.)

Facilities and Curriculum are deliberately **not** level-filtered — a
broken projector or an outdated curriculum topic affects every level
equally, so those two categories always show the same options to
everyone, regardless of what level the student registered with.

## Changing the color scheme

Open `styles.py` and look near the very top for a block starting with
`:root {`. The two most important lines are `--accent: #2563eb;` (the
main blue) and `--accent2: #7c3aed;` (the purple used in gradients).
Change the hex color codes and every button, header, and highlight
across the app updates to match.

## Resetting the database (start completely fresh)

> ⚠ **This destroys all application data — there is no undo.** Every
> registered student account, every submitted feedback entry, every admin
> note, every academic session, the audit log and the trained-model
> corrections go with it. The app then re-seeds `admin001` /
> `password123` on the next start.
>
> This project ships with a `futo_feedback.db` that **already contains
> real feedback**. Resetting is not a harmless way to "start fresh" — take
> a proper backup first, with the method below, and only then delete.

### Backing up correctly

**Do not just copy `futo_feedback.db`.** The database runs in WAL mode, so
recently committed transactions can still be sitting in
`futo_feedback.db-wal` and have not been folded back into the main file.
Copying only the main file can produce a backup that opens without error
and is silently missing the last few writes.

Two safe options:

**A. Use SQLite's own backup command (best — works while the app is
running):**

```bash
sqlite3 futo_feedback.db ".backup backup/futo_feedback_$(date +%F).db"
```

**B. Copy all three files together, with the app stopped:**

1. Press `Ctrl+C` in the terminal running the app and wait for it to exit.
2. Copy `futo_feedback.db`, `futo_feedback.db-wal` and
   `futo_feedback.db-shm` into your backup folder. Keep the names.
3. To restore, put all three back and start the app.

On Windows, if the `sqlite3` command-line tool isn't installed, option B
works just as well — but stop the app first, or the `-wal` you copy may
change underneath the copy.

### Then, and only then, reset

1. Stop the app if it's running (click the terminal, press `Ctrl+C`).
2. In VS Code's file list, right-click `futo_feedback.db` and choose
   **Delete**. Delete `futo_feedback.db-wal` and `futo_feedback.db-shm`
   too, if they're present — leaving them behind next to a fresh database
   is at best confusing.
3. Run `streamlit run app.py` again. A brand new, empty database is
   created automatically, including a fresh seeded admin account using
   whatever is currently set in `config.py`.

## Deleting a user account (admin, in the app)

This is different from resetting the database, and much smaller in scope.
Sign in as an admin, open **User Management**, select an account, and use
the **Danger zone** at the bottom of the page.

Deleting an account is **permanent** and cascades: the account and *all of
that student's feedback* are removed in a single transaction, so nothing
of theirs keeps counting in any chart, the CSV export, the session
statistics, or the sentiment training set.

Three things make it hard to do by accident:

- The delete button only becomes active once you have selected a target,
  read the **deletion preview** (how many feedback rows, reset codes and
  admin corrections will go), and written a reason.
- A confirmation dialog then requires you to **type the exact username**.
  For an admin account it additionally requires typing `DELETE ADMIN`.
- The app refuses outright to delete **your own account**, and refuses to
  delete the **last remaining admin**, so you cannot lock everyone out.

Every deletion is written to the **audit trail** further down the same
page, together with a full JSON snapshot of the deleted rows — so if an
account is removed by mistake, you can **Restore** it from that table.

> **The restore window is 5 days.** For the first 5 days after a deletion the
> entry — including the snapshot **Restore** needs — is kept and the Restore
> button is available. Once that window closes the entry is **permanently
> removed**, along with the account's details, its password hash and the full
> text of every feedback comment it held. After that there is no record that
> the account was ever deleted and no way to undo it. The panel deliberately
> shows only the last 5 days so it stays a record of what is happening *now*
> rather than an archive that grows forever. **If you are unsure about a
> deletion, restore it within 5 days or accept that it is gone** — and if you
> need a permanent record, copy the page or the database before the window
> closes.

The same page's **Audit trail** section lists who deleted whom, when, why,
and how many records were affected, and offers a one-click Restore per
row. Restored accounts come back with their original username, email, and
feedback; password-reset codes are deliberately *not* restored, because
re-arming a consumed one-time code is a security hazard with no upside.

## Deploying so someone else can access it over the internet

Running it locally (Part A) is normally all you need for a project
defense — you demo it on your own laptop. If you specifically want a
public link others can open in their own browser:

1. Create a free account at **share.streamlit.io** using GitHub.
2. Set your Git identity once per machine (skip if you've already done
   this — `git commit` fails without it, and the error message does not
   say so clearly):
   ```
   git config --global user.email "you@example.com"
   git config --global user.name  "Your Name"
   ```
3. Push this project folder to a new GitHub repository. In the terminal
   (with your venv active, inside the project folder):
   ```
   git init
   git add .
   git status                 # ← review this before committing
   git commit -m "Initial commit"
   git branch -M main
   git remote add origin https://github.com/<your-username>/<repo-name>.git
   git push -u origin main
   ```
   **Look at `git status` output before you commit.** `.gitignore` keeps
   `futo_feedback.db`, `futo_feedback.db-wal`, `futo_feedback.db-shm`,
   `model/`, `nltk_data/` and `.streamlit/secrets.toml` out of the commit;
   confirm none of them is listed as a file to be added. If
   `futo_feedback.db` **or either `-wal` / `-shm` sidecar** appears there,
   the ignore rule isn't matching — stop and fix it, because that commit
   would publish every student's feedback. (The database runs in WAL mode,
   so the sidecars hold recently committed rows even when the main file
   looks small.)
   (This requires Git to be installed — see the installer at git-scm.com
   if `git` isn't recognized.)
4. On share.streamlit.io, click **New app**, choose your repository, set
   the main file to `app.py`, and click **Deploy**.
5. If you want email to work on the deployed version too, open the
   deployed app's **Settings → Secrets** on share.streamlit.io and paste
   in the same key/value pairs you put in `.streamlit/secrets.toml`
   locally.

   > ⚠ **Use a brand-new App Password for this, and revoke any old one
   > first.** If an App Password was ever typed into a file inside this
   > project — even `.streamlit/secrets.toml`, which `.gitignore` keeps out
   > of Git — treat it as compromised, because the folder itself is what
   > gets zipped and uploaded. Go to
   > [myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords),
   > delete the old App Password, generate a new one, and paste only that
   > into Streamlit's Secrets box. An App Password grants full access to
   > the mailbox, so leaving an exposed one live undoes the rest of this
   > checklist.
6. Wait for the build to finish; you'll get a public link like
   `https://something.streamlit.app`.

> ⚠ **The free hosting tier does not persist the database.** Because
> `futo_feedback.db` is gitignored, every redeploy starts from an empty
> database and re-seeds `admin001` / `password123` — all feedback entered
> through the deployed link is gone. This is acceptable for a demo, but
> if this is ever used department-wide for real, deploy to a host with
> persistent storage (and back the database up on a schedule).

## Troubleshooting

| What you're seeing | What it means / what to do |
|---|---|
| No `.streamlit` folder after extracting the zip, or it's there but empty | This folder's name starts with a dot, and some Windows extraction tools/Explorer views hide dot-prefixed folders. Turn on **Hidden items** in Explorer's View tab and look again — if it's still missing, see Step 14.3 for how to recreate it by hand in under a minute (exact file contents included there). |
| `'python' is not recognized` or `command not found` | Python isn't installed, or wasn't added to PATH. Redo Step 2, making sure to tick "Add python.exe to PATH." |
| `'streamlit' is not recognized` right after opening a new terminal | You forgot to activate the virtual environment in this new terminal session — run the activate line from Step 6 again. |
| `ModuleNotFoundError: No module named '...'` | Either the venv isn't active (see above), or Step 7 didn't finish successfully — run `pip install -r requirements.txt` again. |
| Every comment shows "Neutral," no matter what you type | The VADER lexicon isn't downloaded. Run `python download_nltk_data.py` (Step 8), then restart the app. |
| Password reset code never arrives by email | Either email isn't set up yet (Step 14) — in which case the code is shown directly on screen instead, which is expected — or your `secrets.toml` values have a typo. Double-check the App Password was copied correctly. |
| "Username already taken" / "Email already registered" while testing | Expected — you're reusing details from an earlier test account. **Either** register with a different username/email **or**, if this app is running as an admin, open **User Management**, search for that account, and use the **Danger zone** to delete it (which also removes its feedback, so the one-submission-per-category rule frees up again). Deleting `futo_feedback.db` also works but throws away *all* data — see the warning in *Resetting the database*. |
| Browser shows "This site can't be reached" | The terminal running the app must stay open. Check it's still running (look for a red error in it — if it crashed, scroll up to read why). |
| "Port 8501 already in use" | Something else (maybe an earlier copy of this same app) is already running on that port. Either close that other terminal, or run `streamlit run app.py --server.port 8502` and open `http://localhost:8502` instead. |
| Edited a `.py` file but the app in the browser looks unchanged | Click the **"Rerun"** button that appears in the top-right corner of the app, or press the `R` key while your mouse is over the app. |
| "You have already submitted feedback for this category" while testing | Expected — the system deliberately allows only one submission per student, per category, **per academic session**. Register a second test account, switch the sidebar to a different academic session, or (as an admin) delete that account from **User Management**. Do not delete the whole database for this. |
| `TypeError: ...got an unexpected keyword argument 'icon'` | Your terminal is running an older, different Streamlit than the one Step 7 installed — usually because a new terminal reset to a global/Anaconda Python instead of your `venv`. Check the traceback's file paths: if they point into `anaconda3\Lib\site-packages\...` instead of `venv\Lib\site-packages\...`, that confirms it. Fix: re-run the activate line from Step 6 in this terminal, then `pip install --upgrade streamlit` and restart the app. (The app also now tolerates this automatically via `st_compat.py` — updating your zip to the latest version fixes it even without touching your environment, but getting the venv active is still worth doing so the rest of your installs match what's expected.) |
| `train_model.py` says it needs more samples | You haven't corrected enough sentiment labels yet — go back to Step 15 and correct more rows in the Full Dashboard first. |
| Icons look like blank squares | **Check you're online first** — but note that no icon in this app loads from the internet. Every Lucide icon is stored as an SVG path string directly in `icons.py` and inlined into the HTML at render time, so the UI looks identical with the network cable unplugged. A blank icon is therefore always a *code* problem, not a connectivity one: a name in the code doesn't exist in the `_SVG_PATHS` dictionary at the top of `icons.py`. `icons.i()` falls back to a safe generic icon in that case, so a mismatch shows up as one odd-looking icon, never a crash. To fix it, find the name you used, look it up at lucide.dev/icons, and copy its `<path>`/`<circle>` elements into `_SVG_PATHS` under that key. |
| Sidebar shows a second, plain/unstyled list of items like "app," "admin overview," "decision insights," "feedback form" — sitting above your properly styled sidebar, sometimes with a stray line of text like "keyboard_double_arrow_left" near it | This was a real bug in earlier copies of this project, now fixed — you shouldn't see it if you're using the current version. It happened because the page-logic folder was originally named `pages/`, and Streamlit reserves that exact folder name to auto-generate its *own* navigation menu from whatever filenames it finds inside — completely separate from, and stacked on top of, this app's own hand-built sidebar. The fix was renaming that folder to `app_pages/` (see the note at the top of `app.py`) so Streamlit no longer treats it as special. **Never rename `app_pages/` back to `pages/`** — that will bring this bug straight back. |
| A button's label text is grey/washed-out against its colored background instead of clearly white | Also a real, now-fixed bug. Streamlit wraps a button's label in its own inner element with its own text-color rule, which can beat a color set only on the outer `<button>` — no amount of `!important` on our side reliably won that fight, since it depends on the exact order Streamlit injects its own styles, which we can't control. The real fix was to stop fighting it: every button meant to look like a bold call-to-action is now created with Streamlit's own `type="primary"` option, which Streamlit *always* pairs with white label text by convention — our CSS then only touches the button's `background` (to swap the flat theme color for this app's gradient), never `color`. If you add a brand-new button anywhere in the app and want it styled the same way, pass `type="primary"` to it, the same as every existing button in `app_pages/login.py` does. |
| A data table (`st.dataframe`, e.g. the "Review & correct sentiment labels" or "Structured Feedback Aggregations" tables) renders with a jarring black background even though the rest of the page is light | Also fixed, and worth understanding: unlike almost everything else in this app, `st.dataframe`'s grid is drawn on an HTML canvas, not as regular styled elements — CSS genuinely cannot reach its cell colors. It reads Streamlit's *actual configured theme* instead, and this project never had a `.streamlit/config.toml` setting one — so it silently fell back to guessing from the visitor's OS/browser dark-mode preference. The fix was adding `.streamlit/config.toml` with an explicit light theme matching this app's palette. **Don't delete that file** — if it goes missing, dataframes (and a few other native, canvas-or-portal-rendered widgets like the password show/hide toggle) can revert to a random guessed theme again. |
| Sign-in says *"The credentials provided are incorrect"* (admin) or one of two student messages | For **students**, the message is now specific: *"This email address is not registered. Please create an account to get started."* means no account exists for that email — click **Create an account**. *"Your login credentials are incorrect. Please check your email and password, then try again."* means the email is known but the password did not match. That split is deliberate — it is what tells a first-time visitor to register rather than to keep guessing — but it does mean the form reveals whether an email is registered. If you would rather not expose that, collapse the two messages back into one in `app_pages/login.py`. For **admins**, the message stays generic. Remember the password **is** case-sensitive — `Futo2026!` and `futo2026!` are different — while usernames are matched case-insensitively. There is no "forgot username" recovery, only "forgot password" via email. |
| An expander's arrow/chevron, or a button's small icon, renders as a raw word (like `check_circle`, `keyboard_arrow_right`, or `arrow_right_alt`) sitting on top of or beside the label text, instead of a small icon glyph | Also fixed in the current version. Streamlit renders its own built-in icons as special ligature text that a specific icon font converts into a glyph — but this app's global CSS used to force *every* element to use the Sora font, which broke that conversion and left the raw icon name showing as plain text. `styles.py` now explicitly excludes Streamlit's own icon elements from that rule. If you ever add new custom CSS with a blanket `* { font-family: ... }` rule, keep the `[data-testid="stIconMaterial"]` exception directly below it in `styles.py` intact. |
| `tests\run_all.py` reports failures right after you edited a file | That's it working. Read the failing group's name, then re-run just that one script (e.g. `python tests\test_css.py`) to see which specific check failed and the line it points at. If the failure is in `test_xss_static_selftest.py`, `test_undefined_names_selftest.py` or `test_streamlit_calls_selftest.py`, read the message carefully: those three test the *checkers*, and a failure there usually means you changed a variable name an allowlist entry refers to, or removed an icon the sweep expects to exist. |

## Preparing this for your project defense

A few things examiners commonly ask about this kind of system, and where
to show them the answer live in the running app:

- **"How do you stop duplicate submissions?"** Log in, submit feedback
  for a category, then click that same category again in the sidebar —
  show that the form is now replaced by a read-only summary. Mention
  that this is enforced twice over: once in the interface — the
  submitted form is *replaced* by a read-only summary, so there is no
  submit button left to press — and again as an unbreakable
  `UNIQUE(username, category, session)` constraint inside SQLite
  itself. The second layer is the one that matters: the save in
  `db.save_data` is a plain `INSERT`, and if the slot is somehow taken
  the resulting `sqlite3.IntegrityError` is caught and shown as "you
  have already submitted", so it can't be bypassed by unusual use of
  the app or by writing your own SQL. Then note the session is *part of
  the key*: start a new academic session and the same student gets a
  fresh set of forms, with no old submission altered.
- **"Prove the sentiment analysis isn't random."** Submit the exact same
  sentence from two different test accounts and show the score is
  identical both times — because VADER (Step 8) is a deterministic,
  rule-based method, not a guess.
- **"How does password recovery work securely?"** Walk through the
  Forgot Password flow (Step 14.4) and mention: the code expires after
  15 minutes, is never stored as plain text in the database, locks out
  after 5 wrong attempts, and the request form deliberately never
  reveals whether the username or the email was the part that didn't
  match (so it can't be used to guess valid accounts).
- **"How is student data kept separate from admin analytics?"** Log in
  as an admin and point out the sidebar has no feedback-submission links
  at all — the underlying routing code in `app.py` never even evaluates
  those pages for an admin session, so there's no way to reach them.
- **"What happens if a student asks to be removed?"** This is the one to
  demo if you have time for a second feature. Sign in as an admin, open
  **User Management**, and show the three separate barriers to a
  mistake: the delete button is inert until you've picked a target, read
  its deletion preview and written a reason; a dialog then makes you
  *type the exact username* (plus `DELETE ADMIN` for an admin account);
  and the server refuses outright to delete your own account or the last
  remaining admin. Then scroll to the **Audit trail** to show that the
  deletion recorded who did it, when, why, and a full JSON snapshot of
  every deleted row — and that **Restore** brings the account and its
  feedback straight back. The reason deletion is safe here despite there
  being **no foreign keys** between `users` and `feedback` (a plain
  `DELETE FROM users` would silently orphan the student's rows, which
  would then keep counting in every chart and in the training set) is
  that `db.delete_user_account` deletes the children explicitly inside
  one transaction. Say that explicitly if asked — it is the most
  interesting engineering decision in the project.
- **"How would this scale to another department?"** Open `config.py` and
  show that every department-specific list (courses, facilities,
  curriculum topics) lives in that one file — adapting the whole system
  for a different department is a matter of editing this file, not
  rewriting the application.

Good luck with the defense.
