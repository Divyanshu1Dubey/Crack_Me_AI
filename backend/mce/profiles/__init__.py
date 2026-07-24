"""Exam profiles for the Medical Content Engine.

Each exam type (NEET PG, INI-CET, FMGE, USMLE, PLAB, future) gets its own
`ExamProfile` so per-exam rules (subject taxonomy, year-source,
option-count, PUA decoding, etc.) live in one place. The pipeline reads
the profile via `--exam-profile auto|<name>` and never hardcodes exam-
specific behaviour.

Phase 2.1 of the Medical Content Engine rollout. See
`docs/neetpg2021/PHASE1_6_PLATFORM_REFINEMENTS.md` §7.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field


# ----------------------------------------------------------------- subject taxonomies

# 19 NEET PG subjects (from the existing backend/importers/neetpg/topic_mapper.py).
NEET_PG_SUBJECTS: list[str] = [
    "Anatomy", "Physiology", "Biochemistry",
    "Pathology", "Microbiology", "Pharmacology",
    "Forensic Medicine", "PSM",
    "Ophthalmology", "ENT",
    "General Medicine", "General Surgery",
    "OBG", "Paediatrics", "Dermatology", "Orthopaedics",
    "Anaesthesia", "Radiodiagnosis", "Psychiatry",
]

# INI-CET subject list (AIIMS / PGIMER / JIPMER / NIMHANS / SCTIMST).
# Slightly different from NEET PG: e.g. "Community Medicine" instead of "PSM",
# "Lab Medicine" present, "Nuclear Medicine" present.
INI_CET_SUBJECTS: list[str] = [
    "Anatomy", "Physiology", "Biochemistry",
    "Pathology", "Microbiology", "Pharmacology",
    "Forensic Medicine", "Community Medicine",
    "Ophthalmology", "ENT",
    "General Medicine", "General Surgery",
    "OBG", "Paediatrics", "Dermatology", "Orthopaedics",
    "Anaesthesia", "Radiodiagnosis", "Psychiatry",
    "Lab Medicine", "Nuclear Medicine",
]

# FMGE is a screening test for foreign medical graduates.
FMGE_SUBJECTS: list[str] = NEET_PG_SUBJECTS + ["Dentistry"]

# USMLE Step 1 organ-system + discipline blend.
USMLE_SUBJECTS: list[str] = [
    "Anatomy", "Physiology", "Biochemistry",
    "Pathology", "Microbiology", "Pharmacology",
    "Behavioural Science", "Biostatistics",
    "Cardiovascular", "Respiratory", "Renal",
    "Gastrointestinal", "Endocrine", "Reproductive",
    "Musculoskeletal", "Nervous System",
    "Hematology / Oncology", "Immunology",
    "Dermatology", "Psychiatry", "Infectious Disease",
]

# PLAB (UK) — partly organ-system, partly discipline.
PLAB_SUBJECTS: list[str] = USMLE_SUBJECTS + ["General Practice", "Ethics"]


# ----------------------------------------------------------------- filename → exam auto-detection


_FILENAME_PATTERNS: list[tuple[re.Pattern, str]] = [
    (re.compile(r"neet[-_ ]?pg", re.IGNORECASE), "neet_pg"),
    (re.compile(r"ini[-_ ]?cet|aiims", re.IGNORECASE), "ini_cet"),
    (re.compile(r"fmge|mci[-_ ]?screen", re.IGNORECASE), "fmge"),
    (re.compile(r"usmle|step[-_ ]?1", re.IGNORECASE), "usmle"),
    (re.compile(r"plab", re.IGNORECASE), "plab"),
]


def detect_exam_from_filename(pdf_filename: str) -> str | None:
    """Return the exam name guessed from filename, or None."""
    base = (pdf_filename or "").lower()
    for pat, name in _FILENAME_PATTERNS:
        if pat.search(base):
            return name
    return None


# ----------------------------------------------------------------- profile


@dataclass(frozen=True)
class ExamProfile:
    """All per-exam knobs in one place.

    Frozen so a profile never mutates mid-run; the pipeline reads it
    once and snapshots it.
    """

    name: str                              # "neet_pg"
    exam_type: str                         # DB column value
    exam_source: str                       # DB column value
    subjects: tuple[str, ...]
    option_count_min: int = 4
    option_count_max: int = 5
    require_explanation: bool = True
    prefer_pua_decode: bool = False        # Marrow-style PUA fonts
    default_year_source: str = "filename"  # filename | pdf_metadata | manual

    # Year regex — used to extract a 4-digit year from the filename when
    # default_year_source = "filename".
    year_regex: re.Pattern = field(default_factory=lambda: re.compile(r"\b(20\d{2})\b"))

    # Filename hints for subject fallback when stem-based mapping fails.
    filename_subject_hints: dict[str, str] = field(default_factory=dict)

    # Display metadata for the UI.
    display_name: str = ""
    color_accent: str = "#10b981"         # emerald default — NEET PG identity
    icon: str = "stethoscope"

    # Subject keyword map — keeps the existing topic_mapper logic usable.
    subject_keywords: dict[str, tuple[str, ...]] = field(default_factory=dict)


# ----------------------------------------------------------------- keyword tables

# Mirror of backend/importers/neetpg/topic_mapper.py — kept verbatim so
# the new pipeline is a drop-in replacement for the legacy keyword
# classifier.
_NEET_PG_KEYWORDS: dict[str, tuple[str, ...]] = {
    "Anatomy": ("anatomy", "muscle", "nerve", "ligament", "artery supply", "vein", "embryology", "histology of"),
    "Physiology": ("physiology", "action potential", "renal physiology", "cardiac output", "hormone", "respiratory", "gastric secretion"),
    "Biochemistry": ("enzyme", "tca cycle", "glycolysis", "vitamin", "amino acid", "purine", "pyrimidine", "ketone body"),
    "Pathology": ("histology", "biopsy", "neoplasm", "carcinoma", "inflammation", "metaplasia", "dysplasia", "infarction"),
    "Microbiology": ("bacteria", "virus", "fungal", "parasite", "stain", "culture", "gram", "mycobacterium"),
    "Pharmacology": ("drug", "dose", "mechanism", "side effect", "moa", "receptor", "antagonist", "agonist"),
    "Forensic Medicine": ("forensic", "postmortem", "wound", "injury", "poisoning", "rigor mortis", "autopsy"),
    "PSM": ("epidemiology", "vaccine", "screening", "public health", "biostatistics", "endemic", "prevalence"),
    "Ophthalmology": ("eye", "retina", "lens", "glaucoma", "cataract", "fundus", "visual acuity", "blindness"),
    "ENT": ("ear", "nose", "throat", "tonsil", "sinus", "auditory", "cochlea", "vestibular"),
    "General Medicine": ("diabetes", "hypertension", "cardiac failure", "renal failure", "liver", "lung", "asthma", "copd"),
    "General Surgery": ("hernia", "appendicitis", "trauma", "fracture", "abdomen", "laparotomy", "sutures"),
    "OBG": ("pregnancy", "labour", "ovary", "uterus", "menstrual", "gestation", "preeclampsia"),
    "Paediatrics": ("neonate", "infant", "vaccination", "milestone", "kwashiorkor", "neonatal jaundice"),
    "Dermatology": ("skin", "rash", "lesion", "pigmentation", "psoriasis", "eczema", "vitiligo"),
    "Orthopaedics": ("bone", "joint", "fracture", "spine", "tendon", "arthroplasty", "osteoporosis"),
    "Anaesthesia": ("anaesthesia", "intubation", "nerve block", "spinal", "epidural", "halothane"),
    "Radiodiagnosis": ("ct", "mri", "x-ray", "usg", "radiograph", "imaging", "contrast"),
    "Psychiatry": ("psychiatric", "depression", "schizophrenia", "anxiety", "bipolar", "delirium"),
}

# Filename hints for NEET PG subject PDFs.
NEET_PG_FILENAME_HINTS: dict[str, str] = {
    "anaesthesia": "Anaesthesia",
    "anatomy": "Anatomy",
    "biochem": "Biochemistry",
    "derma": "Dermatology",
    "ent": "ENT",
    "fmt": "Forensic Medicine",
    "medicine": "General Medicine",
    "micro": "Microbiology",
    "obg": "OBG",
    "ophthal": "Ophthalmology",
    "ortho": "Orthopaedics",
    "psm": "PSM",
    "patho": "Pathology",
    "pediatrics": "Paediatrics",
    "pediatric": "Paediatrics",
    "pharm": "Pharmacology",
    "physiology": "Physiology",
    "psychiatry": "Psychiatry",
    "radiology": "Radiodiagnosis",
    "surgery": "General Surgery",
}


def _make_neet_pg() -> ExamProfile:
    return ExamProfile(
        name="neet_pg",
        exam_type="neet_pg",
        exam_source="NEET PG (recall)",
        subjects=tuple(NEET_PG_SUBJECTS),
        option_count_min=4,
        option_count_max=5,
        require_explanation=True,
        prefer_pua_decode=True,            # Marrow-style PDFs use PUA
        default_year_source="filename",
        filename_subject_hints=NEET_PG_FILENAME_HINTS,
        display_name="NEET PG",
        color_accent="#10b981",             # emerald-500 — NEET PG identity
        icon="stethoscope",
        subject_keywords=_NEET_PG_KEYWORDS,
    )


def _make_ini_cet() -> ExamProfile:
    return ExamProfile(
        name="ini_cet",
        exam_type="ini_cet",
        exam_source="INI-CET (recall)",
        subjects=tuple(INI_CET_SUBJECTS),
        option_count_min=4,
        option_count_max=4,                # INI-CET is strictly 4-option
        require_explanation=True,
        prefer_pua_decode=False,
        default_year_source="filename",
        filename_subject_hints=dict(NEET_PG_FILENAME_HINTS, **{"community": "Community Medicine"}),
        display_name="INI-CET",
        color_accent="#6366f1",             # indigo-500 — INI-CET identity
        icon="heart-pulse",
        subject_keywords=_NEET_PG_KEYWORDS,
    )


def _make_fmge() -> ExamProfile:
    return ExamProfile(
        name="fmge",
        exam_type="fmge",
        exam_source="FMGE (recall)",
        subjects=tuple(FMGE_SUBJECTS),
        option_count_min=4,
        option_count_max=5,
        require_explanation=True,
        prefer_pua_decode=True,
        default_year_source="filename",
        filename_subject_hints=NEET_PG_FILENAME_HINTS,
        display_name="FMGE",
        color_accent="#0ea5e9",             # sky-500
        icon="shield-check",
        subject_keywords=_NEET_PG_KEYWORDS,
    )


def _make_usmle() -> ExamProfile:
    return ExamProfile(
        name="usmle",
        exam_type="usmle",
        exam_source="USMLE (recall)",
        subjects=tuple(USMLE_SUBJECTS),
        option_count_min=4,
        option_count_max=10,               # USMLE questions can have up to 10 options
        require_explanation=True,
        prefer_pua_decode=False,
        default_year_source="filename",
        filename_subject_hints={},
        display_name="USMLE",
        color_accent="#f59e0b",             # amber-500
        icon="book-open",
        subject_keywords={},
    )


def _make_plab() -> ExamProfile:
    return ExamProfile(
        name="plab",
        exam_type="plab",
        exam_source="PLAB (recall)",
        subjects=tuple(PLAB_SUBJECTS),
        option_count_min=4,
        option_count_max=5,
        require_explanation=True,
        prefer_pua_decode=False,
        default_year_source="filename",
        filename_subject_hints={},
        display_name="PLAB",
        color_accent="#ef4444",             # red-500
        icon="globe-2",
        subject_keywords={},
    )


# ----------------------------------------------------------------- registry


_PROFILES: dict[str, ExamProfile] = {
    "neet_pg": _make_neet_pg(),
    "ini_cet": _make_ini_cet(),
    "fmge": _make_fmge(),
    "usmle": _make_usmle(),
    "plab": _make_plab(),
}


def get_profile(name: str) -> ExamProfile:
    """Return the ExamProfile for the given name; raise KeyError on miss."""
    return _PROFILES[name]


def get_profile_for_filename(pdf_filename: str) -> ExamProfile:
    """Auto-detect the profile from the filename; fall back to NEET PG."""
    detected = detect_exam_from_filename(pdf_filename)
    if detected and detected in _PROFILES:
        return _PROFILES[detected]
    return _PROFILES["neet_pg"]


def list_profiles() -> list[str]:
    return list(_PROFILES.keys())


__all__ = [
    "ExamProfile",
    "NEET_PG_SUBJECTS",
    "INI_CET_SUBJECTS",
    "FMGE_SUBJECTS",
    "USMLE_SUBJECTS",
    "PLAB_SUBJECTS",
    "detect_exam_from_filename",
    "get_profile",
    "get_profile_for_filename",
    "list_profiles",
]
