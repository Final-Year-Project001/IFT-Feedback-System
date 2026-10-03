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
# Minimum number of admin-corrected labels required before train_model.py
# will train (and the app will load) a local supervised classifier.
# Below this threshold, the deterministic NLTK VADER lexicon analyzer is
# used on its own — see sentiment.py for the full explanation.
from pathlib import Path
BASE_DIR = Path(__file__).resolve().parent
MIN_TRAINING_SAMPLES = 40
MODEL_PATH = str(BASE_DIR / "model" / "sentiment_classifier.pkl")

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

