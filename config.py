"""
config.py
---------
Static, non-secret configuration: page categories, dropdown/checklist option
lists, and the shared Plotly theme. Nothing here touches the database or
Streamlit widgets, so it can be imported anywhere without side effects.
"""

from __future__ import annotations

# ==================== FEEDBACK CATEGORIES ====================
CATEGORIES = ["Course Content", "Lecturer Teaching Style", "Facilities", "Curriculum"]

CAT_META = {
    "Course Content": {
        "icon": "course",
        "desc": "Rate your course materials and flag what needs more attention — you'll only see courses from your own level and semester.",
    },
    "Lecturer Teaching Style": {
        "icon": "teaching",
        "desc": "Tell us how your lecturers are teaching — what's working, and what isn't.",
    },
    "Facilities": {
        "icon": "facilities",
        "desc": "Broken equipment, power issues, cramped labs — let us know what's affecting your learning.",
    },
    "Curriculum": {
        "icon": "curriculum",
        "desc": "Does the curriculum still match what's actually happening in the industry? Tell us where it's falling behind.",
    },
}

# ==================== IFT Dept (FUTO) COURSE LIST — BY LEVEL & SEMESTER ====================
# Source: FUTO Department of Information Technology Student Handbook &
# Information Guide, §17.0 "Undergraduate Syllabus Courses and Credit
# Units" — core ("C" status) courses only, kept split by Harmattan and
# Rain semester exactly as the Handbook lists them (a student picks
# their semester on the Course Content form, then only sees that
# semester's courses — Harmattan and Rain courses are genuinely
# different courses, so showing them merged was misleading). General-
# education electives (IGB/FRN language courses) are intentionally left
# out since they aren't department-specific and wouldn't be meaningful
# to rate here.
#
# NOTE ON A SOURCE DOCUMENT INCONSISTENCY: the Handbook's own syllabus
# table lists "IFT 403" twice at 400 Level (Harmattan) — once as
# "Mobile and Pervasive Computing" and once as "Information and Network
# Security." Both are reproduced below exactly as printed rather than
# silently guessing which one is a typo; if this is a Departmental
# documentation error, correct the code for one of the two lines below
# once the Department confirms the right code.
_OTHER = "Other / General"
_PICK = "Select a course…"
SEMESTERS = ["Harmattan", "Rain"]

# The semester a session is assumed to be running until an administrator says
# otherwise. It is the first entry of SEMESTERS rather than a second literal,
# so the two can never drift apart, and it is a valid value everywhere a
# `SEMESTERS` membership test happens.
DEFAULT_SEMESTER = SEMESTERS[0]

COURSES_BY_LEVEL_SEMESTER: dict[str, dict[str, list[str]]] = {
    "100": {
        "Harmattan": [
            _PICK,
            "GST 111 – Communication in English",
            "MTH 101 – Elementary Mathematics I",
            "PHY 101 – General Physics I",
            "PHY 107 – General Practical Physics I",
            "STA 111 – Descriptive Statistics",
            "COS 101 – Introduction to Computing Sciences",
            "CHM 101 – General Chemistry I (Theory)",
            "CHM 107 – General Chemistry I (Practical)",
            "GST 103 – Humanities",
            _OTHER,
        ],
        "Rain": [
            _PICK,
            "GST 112 – Nigerian Peoples and Culture",
            "MTH 102 – Elementary Mathematics II",
            "PHY 102 – General Physics II",
            "PHY 108 – General Practical Physics II",
            "COS 102 – Problem Solving",
            "CHM 102 – General Chemistry II (Theory)",
            "CHM 108 – General Chemistry II (Practical)",
            "GET 102 – Engineering Graphics & Solid Modeling I",
            "STA 112 – Probability I",
            _OTHER,
        ],
    },
    "200": {
        "Harmattan": [
            _PICK,
            "ENT 211 – Entrepreneurship and Innovation",
            "COS 201 – Computer Programming I",
            "IFT 203 – Introduction to Web Technologies",
            "IFT 205 – Introduction to Information Technology",
            "IFT 211 – Digital Logic Design",
            "IFT 299 – SIWES I",
            "MTH 201 – Mathematical Methods I",
            "CSC 201 – Computer and Application I",
            _OTHER,
        ],
        "Rain": [
            _PICK,
            "GST 212 – Philosophy, Logic, and Human Existence",
            "COS 202 – Computer Programming II",
            "IFT 212 – Computer Architecture and Organization",
            "INS 202 – Human-Computer Interface",
            "GET 204 – Student Workshop Practice",
            "IFT 206 – Discrete Structures",
            "MTH 202 – Mathematical Methods II",
            "ENG 226 – Introduction to Electrical / Electronic Engineering",
            "MGT 206 – Industrial Psychology",
            _OTHER,
        ],
    },
    "300": {
        "Harmattan": [
            _PICK,
            "ICT 305 – Data Communications Systems and Network",
            "IFT 309 – Data Structure and Algorithm",
            "IFT 301 – Principles and Practice of Telecommunication Technology",
            "IFT 305 – Multimedia Application Systems and Development",
            "IFT 307 – Operations Research",
            "COS 303 – System Analysis and Design",
            "COS 305 – Introduction to Software Engineering",
            _OTHER,
        ],
        "Rain": [
            _PICK,
            "IFT 310 – Mobile Application Development",
            "GST 312 – Peace and Conflict Resolution",
            "ENT 312 – Venture Creation",
            "IFT 302 – Web Application Development",
            "IFT 304 – Web Development using Content Management Systems",
            "IFT 308 – Ethics and Legal Issues in IFT",
            "IFT 322 – Innovation and Entrepreneurship",
            "IFT 342 – Network Servers and Infrastructures",
            "CSC 308 – Operating Systems",
            "DTS 304 – Database Management Systems I",
            _OTHER,
        ],
    },
    "400": {
        "Harmattan": [
            _PICK,
            "COS 409 – Research Methodology and Technical Report Writing",
            "IFT 403 – Mobile and Pervasive Computing",
            "IFT 410 – System Integration and Architecture",
            "IFT 442 – Wireless Communication and Networking",
            "INS 401 – Project Management",
            "IFT 403 – Information and Network Security",  # see note above
            "IFT 405 – Computer Graphics",
            "IFT 407 – Management Information Systems",
            "IFT 409 – Data Science I",
            _OTHER,
        ],
        "Rain": [
            _PICK,
            "IFT 399 – SIWES II",
            _OTHER,
        ],
    },
    "500": {
        "Harmattan": [
            _PICK,
            "IFT 501 – Internet of Things (IoT)",
            "IFT 503 – Intelligent Systems I",
            "IFT 505 – Web Server Technology and Administration",
            "IFT 507 – Software Development",
            "IFT 511 – Cloud Computing Technology",
            "IFT 513 – Special Topics in Information Technology (Seminar)",
            "IFT 497 / 597 – Final Year Student's Project I",
            "IFT 515 – Remote Sensing Technology (Elective)",
            "COS 401 / IFT 519 – Database Management Systems II (Elective)",
            "IFT 517 – Embedded Systems and Pervasive Computing (Elective)",
            _OTHER,
        ],
        "Rain": [
            _PICK,
            "IFT 502 – Computer Modelling and Simulation",
            "IFT 508 – Enterprise Networking, Security, and Automation",
            "IFT 510 – Information Assurance and Security",
            "IFT 514 – Cyber Security and Networks",
            "IFT 518 – Blockchain Technology",
            "IFT 498 / 598 – Final Year Student's Project II",
            "IFT 512 – Intelligent Systems II (Elective)",
            "IFT 516 – Data Science II (Elective)",
            _OTHER,
        ],
    },
}

# Fallback used only if a student's stored level doesn't match any key
# above (e.g. an admin's "Staff" level, or old data) — the full course
# catalogue across every level and semester, so a dropdown still has
# something sensible to show rather than being empty.
IT_COURSES = [_PICK] + sorted({
    c
    for level_data in COURSES_BY_LEVEL_SEMESTER.values()
    for semester_list in level_data.values()
    for c in semester_list
    if c not in (_PICK, _OTHER)
}) + [_OTHER]


def courses_for_level_semester(level: str, semester: str) -> list[str]:
    """Course dropdown options for one specific level + semester (e.g.
    "300", "Rain") — this is what the Course Content form uses, since
    Harmattan and Rain are genuinely different courses, not two halves
    of the same list."""
    level_data = COURSES_BY_LEVEL_SEMESTER.get(str(level))
    if not level_data:
        return IT_COURSES
    return level_data.get(semester, IT_COURSES)


def courses_for_level(level: str) -> list[str]:
    """Both semesters combined for one level (used where a full-year
    view makes more sense than picking one semester, e.g. the optional
    course field on Lecturer Teaching Style)."""
    level_data = COURSES_BY_LEVEL_SEMESTER.get(str(level))
    if not level_data:
        return IT_COURSES
    merged, seen = [_PICK], {_PICK}
    for semester in SEMESTERS:
        for course in level_data.get(semester, []):
            if course not in seen and course != _OTHER:
                merged.append(course)
                seen.add(course)
    merged.append(_OTHER)
    return merged

COURSE_CONTENT_EMPHASIS_AREAS = [
    "Practical coding exercises & lab sessions",
    "Real-world case studies & industry examples",
    "Theoretical foundations & core concepts",
    "Assessment & examination preparation",
    "Project-based learning components",
    "Up-to-date tools & modern technologies",
    "Group work & collaborative assignments",
    "Research and technical writing skills",
    "Video / multimedia learning resources",
    "Guest lectures & industry speakers",
]

TEACHING_STYLE_METHODS = [
    "Hands-on practicals & live demonstrations",
    "Use of infographics & visual aids",
    "Quiz-based & gamified assessments",
    "Flipped classroom / pre-recorded lectures",
    "Interactive class discussions & Q&A",
    "Problem-solving workshops",
    "Use of real-world projects & case studies",
    "Collaborative group work & peer learning",
    "Coding challenges & hackathons",
    "One-on-one mentoring & office hours",
]

TEACHING_STYLE_CHALLENGES = [
    "Pace of lecture delivery (too fast / slow)",
    "Insufficient student engagement",
    "Limited use of practical examples",
    "Inadequate feedback on assignments",
    "Poor slide/visual quality",
    "Over-reliance on reading from slides",
    "Inconsistent attendance / punctuality",
    "Unclear explanations of complex topics",
    "Limited use of modern teaching technology",
    "No issues – delivery is effective",
]

FACILITIES_ITEMS = [
    "Power supply & electricity stability",
    "Laboratory computers & workstations",
    "Internet connectivity & Wi-Fi coverage",
    "Socket outlets & power extensions in classrooms",
    "Projectors & display screens",
    "Air conditioning & ventilation",
    "Seating capacity & classroom furniture",
    "Printing & scanning facilities",
    "Library resources & IFT journals access",
    "Sanitation & restroom facilities",
    "Security & access control",
    "Backup power (generators / UPS)",
    "Software licences & development tools",
    "Video conferencing / seminar equipment",
]

CURRICULUM_ALIGNMENT_AREAS = [
    "Cloud computing & DevOps practices",
    "Cybersecurity & ethical hacking",
    "Machine learning & AI fundamentals",
    "Mobile & cross-platform development",
    "Data science & analytics",
    "Blockchain & distributed systems",
    "Agile / Scrum project management",
    "UI/UX design principles",
    "Internet of Things (IoT)",
    "Industry certifications (AWS, Cisco, etc.)",
    "Entrepreneurship & tech startup skills",
    "Open-source contribution & collaboration tools (Git)",
]

CURRICULUM_OUTDATED_AREAS = [
    "Programming languages / frameworks taught",
    "Course structure & credit allocation",
    "Balance between theory and practicals",
    "Internship & industrial attachment provisions",
    "Final-year project guidelines",
    "Assessment & grading methods",
    "Core subject selection for each level",
    "Elective / specialisation options offered",
]

# ==================== ACCOUNTS ====================
# Admin accounts can be seeded into the `users` table on first run (see
# db.seed_admins()). Further administrators and students can be managed
# directly through the User Management portal.
SEED_ADMINS_ON_STARTUP = True
ADMIN_SEED_ACCOUNTS = [
    {"username": "admin001", "password": "password123",
     "email": "admin001@futo.edu.ng", "full_name": "IFT Department Admin"},
]

USERNAME_MIN_LEN = 4
PASSWORD_MIN_LEN = 8

# ==================== EMAIL ====================
# SMTP settings are read at runtime from Streamlit secrets
# (.streamlit/secrets.toml) or environment variables — see
# email_service.py and SETUP_GUIDE.md § "Setting up email". EMAIL_ENABLED
# is computed automatically (True once SMTP settings are found); the app
# runs perfectly well with email disabled — OTP codes and confirmations
# are simply not sent, and this is surfaced clearly in the UI rather than
# failing silently.
EMAIL_FROM_NAME = "FUTO IFT Feedback System"
OTP_LENGTH = 6
OTP_EXPIRY_MINUTES = 15
OTP_MAX_ATTEMPTS = 5

# ==================== SENTIMENT ENGINE ====================
# `MIN_TRAINING_SAMPLES`, `MODEL_PATH` and `BASE_DIR` used to sit here.
# `MIN_TRAINING_SAMPLES` and `MODEL_PATH` named the local classifier that
# `train_model.py` trained from free-text comments and loaded beside VADER; with
# the comment box removed there is no training text, so a model trained on it
# would be a model of nothing. `BASE_DIR` existed only to build `MODEL_PATH`, and
# nothing else read it — confirmed by grep, including the suites.
#
# All three are removed rather than left at their old values, because a
# threshold nobody reads is a threshold that will eventually be read. If a
# supervised model is ever wanted again, `sentiment.analyze_sentiment` is the
# only seam that has to change — the label, score and confidence it returns are
# already the whole contract every caller depends on.

# ==================== ACADEMIC SESSION ====================
# Default academic session. Active default session is managed via
# the Academic Sessions Manager in Full Dashboard.
CURRENT_SESSION = "2025/2026"

# The one and only label for "no session filter" (C-06). It used to be typed
# out at four call sites under two spellings — "All Sessions (Aggregate)" in
# admin_overview, decision_insights and app.py, and a bare "All Sessions" as
# full_dashboard's default — so the same filter was labelled two different ways
# depending on which page the admin was standing on. `db._AGGREGATE_ALIASES`
# still accepts the old spellings on the READ path, so an existing browser
# session or bookmark keeps working, but nothing new is ever generated from one.
ALL_SESSIONS_LABEL = "All Sessions (Aggregate)"

# ==================== IFT TEACHING STAFF ====================
# Source: FUTO Department of Information Technology Student Handbook &
# Information Guide, §5.0 "List of Staff Members", §5.1 "Teaching Staff",
# items 1-25.
#
# TRANSCRIBED FROM THE HANDBOOK BY HAND.
#
# `Department Handbook.PDF` is a CamScanner scan with no text layer — the whole
# 27-page document yields 621 extractable characters, all of them the
# "Scanned with CamScanner" watermark. So these names were read off the rendered
# pages (4 and 5) at high resolution rather than parsed, and they are therefore
# a *transcription*: check them against the handbook before a defence or before
# the department is graded on them. The surname is the part that matters here,
# because it is what a student types and what the administrative breakdowns
# group on, so `name` carries the title and initials and `key` is the bare
# surname.
#
# One lecturer can teach across several levels and courses, which is why these
# names are deliberately NOT scoped to a level: a 200-level and a 400-level
# student may both be rating the same person, and the teaching-style breakdown
# aggregates them together deliberately (see `db.lecturer_teaching_summary`).
#
# `key` is the canonical form used for grouping. Normalised to lower case with
# the title and initials stripped, so "Dr. A. I. Otuonye", "Otuonye" and
# "DR. A.I. OTUONYE" all resolve to the same row no matter how a student picked
# it from the dropdown or what an older free-text submission recorded.
TEACHING_STAFF: list[dict] = [
    {"n": 1,  "name": "Prof. Mrs. U. F. Eze",        "key": "eze",        "rank": "Professor",        "field": "Database Technology"},
    {"n": 2,  "name": "Dr. A. I. Otuonye",           "key": "otuonye",     "rank": "Reader",           "field": "Software Engineering"},
    {"n": 3,  "name": "Engr. Dr. O. C. Nwokonkwo",   "key": "nwokonkwo",   "rank": "Senior Lecturer",  "field": "Project Management"},
    {"n": 4,  "name": "Dr. C. Etus",                  "key": "etus",        "rank": "Senior Lecturer",  "field": "Electrical / Computer Engineering"},
    {"n": 5,  "name": "Engr. Dr. E. C. Amadi",       "key": "amadi",       "rank": "Senior Lecturer",  "field": "Electrical Engineering"},
    {"n": 6,  "name": "Dr. N. Ekedebe",               "key": "ekedebe",     "rank": "Senior Lecturer",  "field": "Communication Engineering"},
    {"n": 7,  "name": "Mr. I. A. Udunwa",             "key": "udunwa",      "rank": "Lecturer I",       "field": "Project Management / Information Systems"},
    {"n": 8,  "name": "Engr. I. U. Ajere",            "key": "ajere",       "rank": "Lecturer I",       "field": "Telecoms Engineering (Network)"},
    {"n": 9,  "name": "Engr. Dr. (Mrs.) G. N. Eze",  "key": "eze",         "rank": "Lecturer I",       "field": "Electrical Engineering / IT"},
    {"n": 10, "name": "Dr. A. M. John-Otumu",         "key": "john-otumu",  "rank": "Lecturer I",       "field": "Computer Science"},
    {"n": 11, "name": "Engr. Dr. Emeka M. Nwanga",    "key": "nwanga",      "rank": "Lecturer I",       "field": "Electrical Engineering"},
    {"n": 12, "name": "Dr. (Mrs.) N. Esomonyu",       "key": "esomonyu",    "rank": "Lecturer II",      "field": "Mathematics / Applied Mathematics"},
    {"n": 13, "name": "Dr. O. T. Okonkwo",            "key": "okonkwo",     "rank": "Lecturer II",      "field": "Computer Science"},
    {"n": 14, "name": "Dr. (Mrs.) C. V. Mbamala",     "key": "mbamala",     "rank": "Lecturer II",      "field": "Computer Science"},
    {"n": 15, "name": "Dr. (Mrs.) Chika. N. John",   "key": "john",        "rank": "Lecturer II",      "field": "Mathematics / Information Management"},
    {"n": 16, "name": "Mr. C. S. Nwanjah",            "key": "nwanjah",     "rank": "Lecturer II",      "field": "Cyber Security / Software Engineering"},
    {"n": 17, "name": "Engr. I. H. Ajunwa",           "key": "ajunwa",      "rank": "Lecturer II",      "field": "Electrical Engineering / Information Management"},
    {"n": 18, "name": "Mr. N. D. Asimobi",            "key": "asimobi",     "rank": "Lecturer II",      "field": "Electrical Engineering / Information Management"},
    {"n": 19, "name": "Mrs. J. Jibiri",               "key": "jibiri",      "rank": "Lecturer II",      "field": "Computer Science / Information Management"},
    {"n": 20, "name": "Mr. V. C. Nwachukwu",          "key": "nwachukwu",   "rank": "Assistant Lecturer", "field": "Information Management Technology"},
    {"n": 21, "name": "Mr. C. Ohanuma",               "key": "ohanuma",     "rank": "Assistant Lecturer", "field": "Computer Science"},
    {"n": 22, "name": "Mr. E. C. Chukwu",             "key": "chukwu",      "rank": "Assistant Lecturer", "field": "Computer Science"},
    {"n": 23, "name": "Mr. C. Okpani",                "key": "okpani",      "rank": "Assistant Lecturer", "field": "Computer Engineering / IT"},
    {"n": 24, "name": "Mr. Emmanuel Ubalatu",        "key": "ubalatu",     "rank": "Assistant Lecturer", "field": "Communication Engineering"},
    {"n": 25, "name": "Mrs. Adaeobi Onwuachu",       "key": "onwuachu",    "rank": "Assistant Lecturer", "field": "Electrical / Computer Engineering"},
]

# The placeholder the student sees first. Kept out of the name list so it can
# never be stored as a lecturer by accident.
LECTURER_PLACEHOLDER = "Select a lecturer…"

# The dropdown options, in handbook order. Sorting alphabetically would hide the
# seniority order the handbook itself uses, and that order is the one an
# examiner checking the handbook against the screen will look for.
LECTURER_OPTIONS: list[str] = [LECTURER_PLACEHOLDER] + [s["name"] for s in TEACHING_STAFF]

# surname -> display name, for grouping the administrative breakdowns and for
# resolving what an older free-text submission typed in. Two staff share a
# surname ("Eze" appears at items 1 and 9); the entry keeps both names so the
# dashboard can show which one, and `TEACHING_STAFF_BY_KEY` is keyed by the
# ordinal as well so a bare surname is never silently attributed to the wrong
# person.
TEACHING_STAFF_BY_KEY: dict[str, list[dict]] = {}
for _s in TEACHING_STAFF:
    TEACHING_STAFF_BY_KEY.setdefault(_s["key"], []).append(_s)


def lecturer_display_for(key: str) -> str:
    """Human label for a grouping key.

    Understands the `surname|initials` form `lecturer_group_key` produces, so
    the two EzEs render as their own names rather than as one merged row. A key
    of `surname|?` is one nobody could be identified from, and says so rather
    than being quietly attributed to one of them.
    """
    raw = (key or "").strip().lower()
    if not raw:
        return "Unspecified"

    surname, _, initials = raw.partition("|")
    if not initials:
        people = TEACHING_STAFF_BY_KEY.get(surname, [])
        if not people:
            return raw
        if len(people) == 1:
            return people[0]["name"]
        return " / ".join(p["name"] for p in people)

    for person in TEACHING_STAFF_BY_KEY.get(surname, []):
        if _initials_of(person["name"]) == initials:
            return person["name"]
    if initials == "?":
        others = TEACHING_STAFF_BY_KEY.get(surname, [])
        if len(others) == 1:
            return others[0]["name"]
        return " or ".join(p["name"] for p in others) + " (not identified)"
    return raw


# Titles stripped before matching, so "Dr. A. I. Otuonye" and "Otuonye" are
# the same person. Ordered longest-first so "Dr." is removed before a bare "Dr"
# would be tried, and applied case-insensitively.
_LECTURER_TITLES = (
    "prof", "professor", "engr", "engnr", "engineer", "mr", "mrs", "ms", "miss",
    "dr", "rev", "sir", "mme", "madam",
)


def _surname_of(name: str) -> str:
    import re

    raw = str(name or "").strip().lower()
    if not raw:
        return ""
    # Drop any parenthetical, e.g. "Dr. (Mrs.) N. Esomonyu" -> "n. esomonyu".
    raw = re.sub(r"\([^)]*\)", " ", raw)
    # Drop trailing rank text some students append.
    raw = re.sub(r"\b(lecturer|senior|assistant|professor)\b", " ", raw)
    words = [w for w in re.split(r"[^a-z'-]+", raw) if w]
    words = [w for w in words if w not in _LECTURER_TITLES]
    if not words:
        return ""
    # A single-letter token is an initial, not a surname.
    words = [w for w in words if len(w) > 1 or w in ("n",)]
    return words[-1] if words else ""


def normalize_lecturer(name: str) -> str:
    """Reduce a lecturer name to its grouping key.

    Strips every title token, the initials, and any parenthetical, then keeps
    the last remaining word. That is the surname in every naming style in the
    handbook, including the hyphenated "John-Otumu" and "G. N. Eze" forms.

    Returns "" for anything that carries no usable name, so a caller can tell
    "no lecturer chosen" from "a lecturer called X".

    NOTE: this is the *surname* key and it is ambiguous by design for the one
    surname the handbook lists twice ("Eze", items 1 and 9). Anything that
    attributes feedback to a person must use `lecturer_group_key`, which
    resolves that collision.
    """
    return _surname_of(name)


def _initials_of(name: str) -> str:
    """The initials in a name, concatenated and lower case: "U. F. Eze" -> "ufe"."""
    import re

    raw = str(name or "").strip().lower()
    raw = re.sub(r"\([^)]*\)", " ", raw)
    tokens = [w for w in re.split(r"[^a-z]+", raw) if w]
    return "".join(t[0] for t in tokens if t and t not in _LECTURER_TITLES)


def lecturer_group_key(name: str) -> str:
    """The key feedback is grouped on when attributing it to a person.

    The surname alone is not enough: the handbook lists two EzEs (items 1 and 9),
    and merging their feedback would tell an administrator that one person was
    flagged for something the other was praised for. So where a surname is held
    by more than one member of staff, the initials are folded into the key and
    the two stay apart:

        "Prof. Mrs. U. F. Eze"       -> "eze|ufe"
        "Engr. Dr. (Mrs.) G. N. Eze" -> "eze|gne"
        "Eze"  (typed by hand)       -> "eze|?"  — grouped separately and
                                        labelled ambiguous, because nothing in
                                        the name says which one it was and
                                        guessing would misattribute it.
    """
    surname = _surname_of(name)
    if not surname:
        return ""
    candidates = TEACHING_STAFF_BY_KEY.get(surname, [])
    if len(candidates) <= 1:
        return surname
    initials = _initials_of(name)
    if initials:
        for person in candidates:
            if _initials_of(person["name"]) == initials:
                return f"{surname}|{initials}"
    # A bare surname for a name the handbook lists twice. Kept as its own key
    # rather than merged into either person.
    return f"{surname}|?"


def is_known_lecturer(name: str) -> bool:
    """True when the name matches someone on the handbook's teaching-staff list.

    Used to separate "flagged from the dropdown" from "typed in by hand", so an
    administrator can see which rows are keyed to a real person.
    """
    return normalize_lecturer(name) in TEACHING_STAFF_BY_KEY


# ==================== PLOTLY THEME ====================
PLOTLY_LAYOUT = dict(
    paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
    font=dict(family="Sora,sans-serif", color="#475569", size=12),
    title_font=dict(family="Sora,sans-serif", color="#0f172a", size=13),
    xaxis=dict(gridcolor="#e2e8f0", linecolor="#e2e8f0", tickcolor="#94a3b8", zeroline=False),
    yaxis=dict(gridcolor="#e2e8f0", linecolor="#e2e8f0", tickcolor="#94a3b8", zeroline=False),
    legend=dict(bgcolor="rgba(0,0,0,0)", bordercolor="#e2e8f0"),
    margin=dict(l=16, r=16, t=44, b=24),
    hoverlabel=dict(bgcolor="#0f172a", bordercolor="#e2e8f0", font=dict(color="#f8fafc", family="Sora")),
)

