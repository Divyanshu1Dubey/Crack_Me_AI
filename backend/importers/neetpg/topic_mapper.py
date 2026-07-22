"""Subject + topic + subtopic mapping for NEET PG / INI-CET / AIIMS PG.

Keyword-based mapper with a 19-subject taxonomy. The mapper also takes
the bundle's primary subject (from filename) as a fallback when no
keyword matches.

Replace with a sentence-transformer zero-shot classifier when ready.
"""
from __future__ import annotations

import re
from typing import Optional

# 19 NEET PG subjects + light topic keywords.
SUBJECT_KEYWORDS: dict[str, list[str]] = {
    "Anatomy": ["anatomy", "muscle", "nerve", "ligament", "artery supply", "vein", "embryology", "histology of"],
    "Physiology": ["physiology", "action potential", "renal physiology", "cardiac output", "hormone", "respiratory", "gastric secretion"],
    "Biochemistry": ["enzyme", "tca cycle", "glycolysis", "vitamin", "amino acid", "purine", "pyrimidine", "ketone body"],
    "Pathology": ["histology", "biopsy", "neoplasm", "carcinoma", "inflammation", "metaplasia", "dysplasia", "infarction"],
    "Microbiology": ["bacteria", "virus", "fungal", "parasite", "stain", "culture", "gram", "mycobacterium"],
    "Pharmacology": ["drug", "dose", "mechanism", "side effect", "moa", "receptor", "antagonist", "agonist"],
    "Forensic Medicine": ["forensic", "postmortem", "wound", "injury", "poisoning", "rigor mortis", "autopsy"],
    "PSM": ["epidemiology", "vaccine", "screening", "public health", "biostatistics", "endemic", "prevalence"],
    "Ophthalmology": ["eye", "retina", "lens", "glaucoma", "cataract", "fundus", "visual acuity", "blindness"],
    "ENT": ["ear", "nose", "throat", "tonsil", "sinus", "auditory", "cochlea", "vestibular"],
    "General Medicine": ["diabetes", "hypertension", "cardiac failure", "renal failure", "liver", "lung", "asthma", "copd"],
    "General Surgery": ["hernia", "appendicitis", "trauma", "fracture", "abdomen", "laparotomy", "sutures"],
    "OBG": ["pregnancy", "labour", "ovary", "uterus", "menstrual", "gestation", "preeclampsia"],
    "Paediatrics": ["neonate", "infant", "vaccination", "milestone", "kwashiorkor", "neonatal jaundice"],
    "Dermatology": ["skin", "rash", "lesion", "pigmentation", "psoriasis", "eczema", "vitiligo"],
    "Orthopaedics": ["bone", "joint", "fracture", "spine", "tendon", "arthroplasty", "osteoporosis"],
    "Anaesthesia": ["anaesthesia", "intubation", "nerve block", "spinal", "epidural", "halothane"],
    "Radiodiagnosis": ["ct", "mri", "x-ray", "usg", "radiograph", "imaging", "contrast"],
    "Psychiatry": ["psychiatric", "depression", "schizophrenia", "anxiety", "bipolar", "delirium"],
}


# Map "Anaesthesia pyqs.pdf" → "Anaesthesia" etc.
FILENAME_SUBJECT_HINTS = {
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
    "pharm": "Pharmacology",
    "physiology": "Physiology",
    "psychiatry": "Psychiatry",
    "radiology": "Radiodiagnosis",
    "surgery": "General Surgery",
}


def fallback_subject_from_filename(pdf_filename: str) -> Optional[str]:
    base = pdf_filename.lower().split(".pdf")[0]
    for key, subject in FILENAME_SUBJECT_HINTS.items():
        if key in base:
            return subject
    return None


def map_subject(stem: str, fallback: Optional[str] = None) -> Optional[str]:
    text = (stem or "").lower()
    best: tuple[int, Optional[str]] = (0, None)
    for subject, kws in SUBJECT_KEYWORDS.items():
        score = sum(1 for kw in kws if kw in text)
        if score > best[0]:
            best = (score, subject)
    if best[1]:
        return best[1]
    return fallback


def map_topic_subject(stem: str, subject: str) -> Optional[str]:
    """Refine topic inside the chosen subject — single-tier keyword match.

    `table` is keyed by subject name; each value is a list of topic
    keywords (flat strings, NOT (topic, [kws]) tuples — that was the
    Patho/Pharm bug fixed here).
    """
    table = {
        "General Medicine": ["cardiology", "respiratory", "gastroenterology", "nephrology", "endocrinology", "neurology", "hematology"],
        "General Surgery": ["gastrointestinal", "trauma", "vascular", "urology", "oncology", "endocrine surgery"],
        "OBG": ["obstetrics", "gynaecology", "reproductive endocrinology"],
        "Pathology": ["general pathology", "systemic pathology", "hematopathology"],
        "Microbiology": ["bacteriology", "virology", "mycology", "parasitology", "immunology"],
        "Pharmacology": ["general pharmacology", "autonomic", "cns", "chemotherapy", "endocrine"],
    }
    text = (stem or "").lower()
    for kw in table.get(subject, []):
        if kw in text:
            return kw
    return None


__all__ = [
    "SUBJECT_KEYWORDS",
    "FILENAME_SUBJECT_HINTS",
    "fallback_subject_from_filename",
    "map_subject",
    "map_topic_subject",
]