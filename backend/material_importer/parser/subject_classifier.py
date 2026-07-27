"""Heuristic subject/topic classifier — used as a fast first pass
before AI classification is enqueued. The AI pass (via the existing
RoundRobin service) refines / overrides this if confidence was low.
"""
from __future__ import annotations

import re
from typing import Tuple

# Ordered: more specific tokens first to avoid "medicine" swallowing everything.
_RULES: list[tuple[str, str]] = [
    (r"\b(neuro(?:logy)?|stroke|epilepsy|meningitis|encephalitis|parkinson|hemipleg)",
     "Medicine"),
    (r"\b(nephro(?:logy)?|ckd|glomerulonephritis|dialysis|kidney|renal)\b",
     "Medicine"),
    (r"\b(cardio|cardiology|ecg|angina|hypertension|heart failure|valve)\b",
     "Medicine"),
    (r"\b(endocr|diabetes|thyroid|cushing|addison)\b",
     "Medicine"),
    (r"\b(gastro|hepatitis|cirrhosi|pancreatitis|ulcer)\b",
     "Medicine"),
    (r"\b(hemat|anemia|leukemia|lymphoma|sickle|thalass)\b",
     "Medicine"),
    (r"\b(respiratory|pneumonia|asthma|copd|tuberculosis|tb |tb-|t.b.|bronchitis|bronchiectasis)\b",
     "Medicine"),
    (r"\b(rheumat|arthritis|lupus|vasculitis|sle)\b",
     "Medicine"),
    (r"\b(derma|skin|rash|eczema|psoriasis|vitiligo|leprosy|fungal infection)\b",
     "Dermatology"),
    (r"\b(psych|depression|schizophrenia|bipolar|mania|anxiety)\b",
     "Psychiatry"),
    (r"\b(anesthesia|anaesthesia|airway|intubation|mallampati|thiopentone|propofol|halothane|epidural|spinal anesthesia)\b",
     "Anesthesia"),
    (r"\b(ortho|orthopae|fracture|dislocation|plaster|knee|shoulder|tennis elbow|carpal|tunnel|hip joint|spine|pott's)\b",
     "Orthopaedics"),
    (r"\b(pediatrics|paediatric|paediatric|neonate|newborn|milestone|immunization|immunisation|growth|kwashiorkor|marasmus|imnci|hbyc|breast feeding)\b",
     "Pediatrics"),
    (r"\b(obstetric|obstetrics|gynec|gynae|gyn|obgy|obgyn|pregnancy|labour|labor|delivery|caesarean|antepartum|postpartum|preeclampsia|eclampsia|amenorrhea|infertility|contraception)\b",
     "OBGY"),
    (r"\b(surgery|surgical|suture|hernia|appendix|intestinal obstruction|peritonitis|tumor|tumour|carcinoma|cancer|mastectomy|cholecystectomy|hemorrhoid|piles|fissure|fistula|burns|wound|goitre|thyroidectomy|varicose)\b",
     "Surgery"),
    (r"\b(psm|preventive|social medicine|community medicine|epidemiology|epidemiolog|communicable disease|ncd|rmch|chc|phc|subcentre|sub-center|asha|anm|anmw|immunisation)\b",
     "PSM"),
    (r"\b(ophthalm|eye|cataract|glaucoma|conjunctivi|red eye|refraction|retina)\b",
     "Ophthalmology"),
    (r"\b(ent|otorhino|ear|throat|nasal|sinusitis|tonsillitis|otitis|rhinitis|larynx|vertigo)\b",
     "ENT"),
]


def classify_subject(text: str) -> Tuple[str | None, float]:
    """Return (subject, confidence 0..1) using token count + matched rules.

    Confidence is `matched_tokens / total_tokens`, capped to [0.05, 0.95].
    Multi-match across the same subject boosts confidence.
    """
    if not text:
        return None, 0.0
    lower = text.lower()
    tokens = re.findall(r"\b\w+\b", lower)
    if not tokens:
        return None, 0.0
    scores: dict[str, float] = {}
    matched_tokens = 0
    for pattern, subject in _RULES:
        hits = re.findall(pattern, lower)
        if hits:
            scores[subject] = scores.get(subject, 0.0) + len(hits)
            matched_tokens += len(hits)
    if not scores:
        return None, 0.0
    best = max(scores.items(), key=lambda kv: kv[1])
    confidence = min(0.95, max(0.05, matched_tokens / max(20, len(tokens))))
    return best[0], round(confidence, 3)


def classify_difficulty(question_text: str) -> str:
    """Easy heuristic: long stems → hard; very short recall → easy."""
    if not question_text:
        return "medium"
    length = len(question_text)
    if length < 80:
        return "easy"
    if length > 240:
        return "hard"
    if any(k in question_text.lower() for k in (
        "not correct", "except", "incorrect", "false",
        "true", "select the correct", "assertion", "reason",
    )):
        return "hard"
    return "medium"
