# Putting your feedback system online — a complete beginner's guide

This guide takes you from where you are now to a working, publicly reachable
website with your data safely stored. It assumes you have never deployed
anything before.

**Read Part 0 first.** It explains, in plain words, what is about to happen to
your files and why one decision in this guide matters more than all the others.

---

# Part 0 — What you are actually doing

## Your app and its notebook

Your feedback system keeps everything it knows in one file, like a notebook:
student accounts, their feedback, the administrator account, the audit trail.
That single file is your entire dataset.

Right now that notebook sits on your computer's hard drive. That is safe, and it
stays safe.

## What changes when you publish it

When you put the app online, it does **not** run on your computer. It runs on a
**rental computer in someone else's warehouse** — Streamlit gives you one for
free.

The problem with a rental computer is that it gets **wiped clean** whenever it is
switched off, restarted, or updated. Streamlit switches it off whenever nobody
has used your app for a while, and it restarts it whenever you change the code.

If your notebook were on that rental computer, one quiet hour would delete
everything. Students would log in the next morning and find every account and
every feedback record gone.

## The solution: a database that does not get wiped

A **database** is a program that stores your data on a computer of its own, which
is never switched off and never wiped.

You already have one. It is called **Neon**, you created it, and it is working —
this has been tested end to end, with every page of your app loading from it.

So your setup will be:

| Piece | Where it lives | What happens if it is lost |
|---|---|---|
| Your app's code | GitHub (a copy) | You still have it on your computer |
| Your data (the notebook) | **Neon** | Nothing. It is permanent. |

The app is a temporary visitor. Your data lives somewhere safe.

---

# Part 1 — The things only you can do

These need your accounts, your passwords, and your decisions. Nobody can do them
for you.

- [ ] **1.1** Change your Neon password (it has been shared in a chat)
- [ ] **1.2** Cancel your old Gmail app password
- [ ] **1.3** Install Git
- [ ] **1.4** Create a GitHub account and push your files
- [ ] **1.5** Deploy to Streamlit Community Cloud
- [ ] **1.6** Add the database address to Streamlit's secrets
- [ ] **1.7** Change the administrator password

---

# Part 2 — Turn your database address into a new one

## Why this is first

Your Neon password was typed into a chat while we were setting this up. Treat it
as seen by someone else, even if that is only me. Changing it takes two minutes
and removes the problem entirely.

## 2.1 — Change the Neon password

1. Go to **https://console.neon.tech**
2. Sign in.
3. Click your project (**neondb**).
4. Find **Connection** or **Roles**, depending on how Neon has arranged the page.
5. Click the **neondb_owner** role and choose to reset its password.
6. Neon shows you a **new** password. Copy it.

> **What "role" means.** A database has accounts of its own, separate from your
> Neon login. Your app connects using one called `neondb_owner`, and that is the
> one whose password you are changing. You are *not* changing your Neon sign-in.

## 2.2 — Write the new address down somewhere safe

Neon gives you an address that looks like this:

```
postgresql://neondb_owner:THE_NEW_PASSWORD@ep-xxxx-yyyy.pooler.c-7.us-east-2.aws.neon.tech/neondb?sslmode=require&channel_binding=require
```

Copy the **whole thing**, including the `postgresql://` at the start and everything
after the password. Put it in a password manager or a text file you will not
publish.

You will need it in Steps 6 and 7.

---

# Part 3 — Cancel the old Gmail app password

## 3.1 — Why

Your `.streamlit/secrets.toml` file held a working Gmail app password, and that
password also appeared in a chat. A Gmail app password grants complete access to
that mailbox. It must be cancelled, not just replaced.

## 3.2 — How

1. Go to **https://myaccount.google.com/apppasswords**
2. Sign in to the Gmail account your app sends from.
3. You will see a list of app passwords.
4. Click **Delete** (or the bin icon) next to the one for "Mail".
5. Confirm.

> **Then:** create a replacement only when you actually need email sending —
> for example password-reset emails. Creating a new one and pasting it into a
> file or a chat re-creates the same problem. Streamlit's secrets box (Step 7)
> is the right place for it.

---

# Part 4 — Install Git

## 4.1 — What Git is

Git is a program that copies your project to GitHub. Streamlit Cloud builds your
app *from* GitHub, so without Git there is nothing for it to build.

Git is **not currently installed** on this computer. That is why this folder has
never been a repository.

## 4.2 — Install it

1. Go to **https://git-scm.com/download/win**
2. Click the big **Download for Windows** button.
3. Run the downloaded file.
4. Accept the defaults. Click **Next** through every screen.
5. Click **Install**.
6. Click **Finish**.

## 4.3 — Check it worked

1. Close and reopen your terminal (see 4.4 below if you do not have one).
2. Type this and press Enter:

```
git --version
```

**You want to see** something like `git version 2.43.0`. Any version is fine.

**If you see** `'git' is not recognized` — the terminal was opened before the
install finished. Close it, open a new one, and try again.

## 4.4 — Opening a terminal in the right folder

You will type several commands, and they must go in the right place.

1. Open **File Explorer**.
2. Click the **address bar** at the top — the strip showing your folder path.
3. Type the word `cmd` and press Enter.

A black window opens. It is already in your project folder. You can check by
typing `dir` and seeing your files listed.

---

# Part 5 — Put your project on GitHub

## 5.1 — Why GitHub is involved twice

GitHub does two different jobs for you:

1. It is the **master copy of your code**, so Streamlit can build from it.
2. It is what lets you deploy and redeploy by clicking a button.

## 5.2 — Create the account

1. Go to **https://github.com**
2. Click **Sign up** and follow the prompts.
3. Choose the **Free** plan. Nothing needs paying for this.

## 5.3 — Create the repository

A **repository** is one project's folder on GitHub.

1. Once signed in, click the **+** in the top-right corner.
2. Click **New repository**.
3. Fill in:
   - **Repository name:** `futo-feedback`
   - **Description:** anything, or leave blank
   - **Visibility:** choose **Private**

     > **Why private?** Your code is yours. Private repositories are free and
     > unlimited for personal accounts, and nobody is affected.

   - **Do NOT tick** "Add a README file", "Add a .gitignore", or "Choose a
     licence". All of these already exist in your project, and letting GitHub
     create its own causes a clash.
4. Click **Create repository**.

## 5.4 — Send your files up

GitHub shows you a page headed **"...or push an existing repository"**. It
contains two lines of commands. Type them into your terminal one at a time,
pressing Enter after each.

The first three are the same for everyone:

```
git init
git add .
git commit -m "First version of the feedback system"
```

Then two with **your** details — copy them from the GitHub page rather than
typing from this guide, so the spelling is exactly right:

```
git branch -M main
git remote add origin https://github.com/YOUR-NAME/futo-feedback.git
git push -u origin main
```

Replace `YOUR-NAME` with your GitHub username.

**What each one does:**

| Command | Meaning |
|---|---|
| `git init` | Turns this folder into a project Git is tracking |
| `git add .` | Selects every file to include |
| `git commit` | Records them as one saved point |
| `git branch -M main` | Names that point `main`, the convention everywhere |
| `git remote add origin` | Tells Git where your GitHub repository is |
| `git push` | Uploads everything |

## 5.5 — Two things that look alarming and are not

**You will see thousands of lines** like:

```
 create mode 100644 styles.py
 create mode 100644 db.py
 db.py      | 1400 ++++++++++++++++++
```

That is Git describing every line of every file. **It is not an error.**

**Git may say** `LF will be replaced by CRLF`. **That is not an error** either.
It means Git will store the files with Unix line endings, which is what Streamlit
needs.

## 5.6 — Confirm it worked

Refresh the GitHub page. You should see your files listed, including `app.py`,
`db.py` and `styles.py`.

**Critical check — is your data private?** Look for these four. They must **not**
be listed:

- `futo_feedback.db`
- `.streamlit/secrets.toml`
- `nltk_data`
- `backup`

Your `.gitignore` already hides them and it worked. If you see any of these four,
**stop and tell me** before going any further.

---

# Part 6 — Check your database works before deploying

## 6.1 — Why bother, when the app will test it for you?

Because this check tells you *what is wrong* if something is. If you skip it and
the app fails, you are reading a confusing Streamlit log instead.

This step was run on your actual Neon database and passed every stage.

## 6.2 — Run it

In your terminal, in the project folder, type the following. Replace
`YOUR-NEW-PASSWORD` with the password from Step 2.

```
set FUTO_POSTGRES_URL=postgresql://neondb_owner:YOUR-NEW-PASSWORD@ep-xxxx-yyyy.pooler.c-7.us-east-2.aws.neon.tech/neondb?sslmode=require&channel_binding=require
```

Press Enter. Then, on a new line:

```
.venv\Scripts\python.exe verify_postgres.py
```

> **What is `set`?** It sets a variable for this terminal window only. It
> disappears when you close the window. That is on purpose — see Part 10.

## 6.3 — What success looks like

You want to see:

```
  [PASS] connected -- PostgreSQL 18.6
  [PASS] schema DDL translates and runs
  [PASS] parameterised INSERT and SELECT round-trip
  [PASS] upsert conflict clause
  [PASS] insert-if-absent conflict clause
  [PASS] rowcount is correct
  [PASS] question marks inside data are not mangled
  [PASS] cleanup
  EVERY STEP PASSED.
```

## 6.4 — If it fails

The script prints the reason. The most common ones:

| Message | What it means | What to do |
|---|---|---|
| `password authentication failed` | The password is wrong | Copy the address again from Neon |
| `could not translate host name` | The address is misspelled | Copy it again; do not retype it |
| `no pg_hba.conf entry` | Neon is blocking this computer | Use the **pooler** address, not the direct one |
| `FUTO_POSTGRES_URL is not set` | The `set` line failed | Make sure you pasted the whole address on **one** line |

Run it again after fixing. **Do not continue until it says EVERY STEP PASSED.**

---

# Part 7 — Deploy to Streamlit Community Cloud

## 7.1 — Open the service

Go to **https://share.streamlit.io** and click **Continue with GitHub**.

Streamlit asks permission to see your repositories. Say yes.

## 7.2 — Create the app

Click **New app**. Streamlit may already have filled the boxes in from GitHub.
Fill in whatever is blank:

| Box | Fill in |
|---|---|
| **Repository** | Your `futo-feedback` repository |
| **Branch** | `main` |
| **Main file path** | `app.py` |
| **Python version** | **3.12** |

> **About the Python version.** Your computer has two environments. The one you
> run locally is version 3.11. That works, but Streamlit's own installers are
> built around 3.12 and newer, and 3.12 is what your project documents. Choose
> **3.12**.

Click **Deploy**.

## 7.3 — Wait for the first build

This takes **two to five minutes**. Streamlit is installing pandas, plotly,
scikit-learn, NLTK and psycopg — all the libraries your app needs.

You can watch it happen: click **Manage app** in the sidebar, then the **Logs**
tab. Normal-looking progress. Do not close the page.

**When it finishes, your app is live** at an address like:

```
https://your-name-futo-feedback.streamlit.app
```

## 7.4 — What to expect on first load

The first page after a fresh start is **slower** than usual. Your app downloads a
small vocabulary file the first time it runs. After that it is cached and pages
load normally. Wait a few seconds rather than assuming something is broken.

---

# Part 8 — Tell Streamlit where your database is

## 8.1 — Why this step is separate

Your database address is a **password**. It must never be part of your code, or it
is published to the world. Streamlit has a private box for such things, which is
where it goes.

## 8.2 — Open the secrets box

With your app open:

1. Click the **⚙ Settings** icon at the bottom of the **left sidebar**.
2. You may need to expand the sidebar first (there is a **»** arrow at the top).
3. Click **Secrets** in the left-hand menu.

## 8.3 — Add the database address

Delete any example text, then paste this:

```
FUTO_POSTGRES_URL="postgresql://neondb_owner:YOUR-NEW-PASSWORD@ep-xxxx-yyyy.pooler.c-7.us-east-2.aws.neon.tech/neondb?sslmode=require&channel_binding=require"
```

Paste **the whole address inside the quotes**, starting with `postgresql://` and
ending with `require`.

Click **Save**.

## 8.4 — Add email sending (only if you revoked the Gmail password)

If you replaced the Gmail app password in Part 3 and want password-reset emails
to work, add these as well:

```
SMTP_HOST="smtp.gmail.com"
SMTP_PORT="587"
SMTP_USERNAME="your-address@gmail.com"
SMTP_PASSWORD="your new 16-character app password"
```

**Check the spelling of that third line.** It must be `SMTP_USERNAME`.

An earlier version of this guide said `SMTP_USER`, which the app does not read.
The key was accepted by the secrets box, stored, and then ignored — so the app
carried on saying *"Email delivery is not configured on this deployment"* no
matter what you typed. If you already added `SMTP_USER`, either rename it to
`SMTP_USERNAME` or simply leave it: the app now accepts either spelling.

Check it worked by opening the app, choosing **Try a Different Email** on the
password-recovery screen, and entering a real registered address. You should get
*"A password reset code has been sent to …"*. If the warning about email not
being configured is still there, the key name or the app password is wrong.

If emails are sent but never arrive, the cause is almost always the network
rather than the password. `SMTP_PORT="465"` uses implicit TLS instead of
STARTTLS and is worth trying if 587 is blocked.

## 8.5 — Restart the app

1. Click **Deploy** in the left sidebar.
2. Click **Redeploy**.

Your app now reads the database address from the secrets box.

To confirm email works once the app has restarted, run this on your own machine
with the same values in `.streamlit/secrets.toml`:

```
.venv\Scripts\python.exe verify_email.py your-address@gmail.com
```

It tests the connection, the credentials and a real delivery, and tells you which
of the three to fix.

---

# Part 9 — Change the administrator password

## 9.1 — Why this is not optional online

When your app starts with an **empty** database, it creates an administrator
account called **`admin001`** with the password **`password123`**. This is written
in your project's code so nobody can be locked out.

On your laptop that is harmless. **Online, anyone in the world could log in with
it.**

## 9.2 — Do it

1. Sign in as **`admin001`** with the password **`password123`**.
2. Click **User Management** in the sidebar.
3. Find `admin001`.
4. Change its password to something only you know. Eight characters or more.
5. Type it again when asked to confirm.

## 9.3 — If you ever restart from empty again

Any time the database is empty, `admin001` / `password123` comes back. So:

> **If your app suddenly stops accepting your admin password, the database was
> reset.** Sign in with `admin001` / `password123` and change it again.

This will not happen now that your database is permanent — but it is worth
knowing.

---

# Part 10 — Check everything works

Do this once, after deploying. It takes ten minutes and it is the difference
between discovering a problem now and discovering it in front of an audience.

Work down the list, ticking as you go.

## Signing in and navigating

- [ ] The app opens and you can sign in
- [ ] The sidebar shows **buttons with text** on them, all the **same size**
- [ ] Click **every** sidebar button; each page loads

## As a student

- [ ] Click **Create an Account** on the login screen and register a test student
- [ ] Sign in as that student
- [ ] Submit feedback in **all four** categories
- [ ] Visit **My Statistics** — your submission should be listed
- [ ] **Refresh the browser** — you should stay signed in and stay on the page

## As an administrator

- [ ] Sign in as `admin001` with your new password
- [ ] **Full Dashboard** loads with charts
- [ ] **Decision Insights** loads
- [ ] **User Management** lists your test student
- [ ] Use the search box to find them
- [ ] Open the account panel and read the statistics

## The most important test of all

- [ ] Submit feedback as the test student
- [ ] Go to Streamlit, click **Deploy → Stop**
- [ ] Wait a minute, then click **Deploy → Redeploy**
- [ ] Sign in as the test student again
- [ ] **My Statistics still shows their feedback** ✅

> **That last box is the one that proves your database is working.** If the
> feedback is gone, the database address is not reaching the app. Go back to
> Step 8.

---

# Part 11 — Day-to-day behaviour

## The app will sleep

Free hosting switches the app off when nobody is using it. The next visitor waits
a few seconds while it wakes.

**This no longer loses anything.** Your data is in Neon, not on the sleeping
computer. This was the whole point of Part 0.

## The first request after waking is slower

The app re-downloads one small file. Normal.

## Each redeploy restarts the app

Also fine. Same reason.

---

# Part 12 — Troubleshooting

| What you see | Why | What to do |
|---|---|---|
| A red banner, deployment failed | Something went wrong during install | **Manage app → Logs**. Copy the last 20 lines |
| Blank white page | Usually the database is unreachable | Check Step 8.3 — is the address in the secrets box? |
| `relation "users" does not exist` | The database address is wrong, so it made a brand-new empty database | Step 8.3, then redeploy |
| `psycopg` not installed | Requirements did not install | Check the Python version is 3.12, then redeploy |
| Everything works, but no sign-in | The database was empty on first start | Create an account from the login screen |
| Feedback vanishes after a restart | The database is not connected | Repeat Step 8 |
| `Package not found` in the logs | Python version wrong | Settings → 3.12 → redeploy |
| Page loads but sidebar buttons are blank | Very unlikely, but if it happens | Hard-refresh with **Ctrl + Shift + R** |
| Cannot log in as admin | The database was reset | Sign in as `admin001` / `password123`, then change it (Step 9) |

---

# Part 13 — Three things never to do

These are not rules I invented. Each one is something that actually went wrong
during this build.

## 13.1 — Never put the database address in `.streamlit/secrets.toml`

**This is the most important warning in this guide.**

The setting that makes your deployed app durable also applies to **every local
test run**. Your test suite creates, changes and deletes records. If the address
sits in that file, running the tests writes to your **real** database.

It happened here. A test run inserted real rows into Neon and left four test
accounts behind.

**What to do instead:**

- Put the address in **Streamlit's secrets box** only (Step 8).
- For one-off local testing, use the `set` command in Step 6 — it lasts only for
  that terminal window.
- Your project now has a built-in guard: `tests/run_all.py` sets
  `FUTO_DISABLE_POSTGRES`, and the app checks it before anything else. So the
  test suite **cannot** reach PostgreSQL, whatever else is configured.

## 13.2 — Never publish a password

Passwords belong in Streamlit's secrets box, and nowhere else. That includes:

- `.streamlit/secrets.toml` — already hidden by your `.gitignore`
- any file in the project folder
- a chat message

A Gmail app password and a database password have both been shared in this
project's chat. Both have been rotated or cancelled. Treat anything typed into a
chat as public.

## 13.3 — Never zip the project folder to publish it

A zip ignores `.gitignore`, so it would contain your database, your backup copy
and your secrets file.

**Use Git.** It is the only method that reliably excludes them.

---

# What you have now, and what remains

## Working and tested

| | |
|---|---|
| Every page, both roles, on your exact Streamlit version | Tested, no errors |
| The sidebar buttons | Uniform, with text |
| PostgreSQL backend | All 7 tables, every read and write verified |
| Your Neon database | Clean — only the administrator account |
| The local test suite | 829 checks, 0 failures |
| Documentation PDF | 48 pages, all diagrams present |

## What remains — you only

1. Change the Neon password (Part 2)
2. Cancel the Gmail app password (Part 3)
3. Install Git (Part 4)
4. Push to GitHub (Part 5)
5. Deploy (Part 7)
6. Add the database address to Streamlit's secrets (Part 8)
7. Change the `admin001` password (Part 9)
8. Work through the checklist in Part 10