"""Stage 9 — Knowledge graph.

For every structured question (Stage 7 output), emit typed concept
nodes + edges that link the question to the platform knowledge graph.

Concept node types (from Phase 1.6 §6):
    Subject, Topic, Subtopic, Disease, Drug, Investigation,
    Anatomy, Physiology, Biochemistry, Pathology, Radiology, Surgery

Edges (typed, weighted):
    question -> subject (w=1.0)
    question -> topic (w=1.0)
    question -> disease / drug / investigation / anatomy / etc.
        (w=confidence, derived from the deterministic extractor)

This stage does NOT call an LLM — concept extraction is deterministic,
operating on:
    1. The profile's subject + topic keyword tables
    2. Lightweight medical vocabulary lookups (curated per-subject)
    3. The question's already-extracted `subject` field from Stage 7

Outputs (JSONL; Phase 3 migrates these into Concept / QuestionConcept
/ ConceptEdge rows):
    09_graph/nodes.jsonl        # one row per concept node
    09_graph/edges.jsonl        # one row per concept edge
    09_graph/related_questions.jsonl
    09_graph/_index.json
"""
from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any, Optional

from mce.stages import MceContext, StageResult


LOG = logging.getLogger("mce.stage_9_graph")


# Minimal curated vocabulary for deterministic concept mapping.
# This is a starter set — Phase 7+ will grow it via LLM-assisted mapping
# behind the same interface, plus user-curated additions.
VOCAB: dict[str, dict[str, tuple[str, ...]]] = {
    "General Medicine": {
        "disease": (
            "diabetes", "hypertension", "asthma", "copd", "tuberculosis",
            "anemia", "iron deficiency", "vitamin b12", "folic acid",
            "rheumatoid arthritis", "osteoarthritis", "gout", "lupus",
            "hepatitis", "cirrhosis", "pancreatitis", "ibs", "ibd",
            "crohn", "ulcerative colitis", "gerd", "peptic ulcer",
            "myocardial infarction", "angina", "heart failure",
            "atrial fibrillation", "stroke", "epilepsy", "parkinson",
            "alzheimer", "migraine", "depression", "anxiety", "thyroid",
            "hypothyroidism", "hyperthyroidism", "diabetes mellitus",
            "renal failure", "ckd", "aki", "nephrotic", "nephritic",
            "urinary tract infection", "pneumonia", "bronchitis",
            "meningitis", "encephalitis", "sepsis", "dengue", "malaria",
            "typhoid", "hiv", "aids", "leprosy", "leishmania",
        ),
        "drug": (
            "aspirin", "paracetamol", "ibuprofen", "metformin",
            "insulin", "atorvastatin", "warfarin", "heparin",
            "amlodipine", "losartan", "enalapril", "propranolol",
            "furosemide", "spironolactone", "digoxin", "amiodarone",
            "isoniazid", "rifampicin", "pyrazinamide", "ethambutol",
            "ceftriaxone", "azithromycin", "ciprofloxacin", "doxycycline",
            "penicillin", "amoxicillin", "metronidazole", "acyclovir",
            "omeprazole", "pantoprazole", "ondansetron", "lorazepam",
            "diazepam", "phenytoin", "valproate", "levetiracetam",
            "haloperidol", "risperidone", "fluoxetine", "sertraline",
            "amitriptyline", "lithium", "prednisolone", "hydrocortisone",
            "methotrexate", "azathioprine", "cyclophosphamide",
        ),
        "investigation": (
            "ecg", "echo", "chest x-ray", "cxr", "ct scan", "mri",
            "ultrasound", "usg", "endoscopy", "colonoscopy", "biopsy",
            "blood culture", "urine culture", "sputum culture",
            "complete blood count", "cbc", "lft", "liver function",
            "kft", "renal function", "thyroid function", "tft",
            "lipid profile", "hba1c", "fasting glucose", "pp glucose",
            "troponin", "d-dimer", "bnp", "procalcitonin", "crp",
            "esr", "ana", "anti-ccp", "psa",
        ),
    },
    "General Surgery": {
        "disease": (
            "hernia", "appendicitis", "cholecystitis", "pancreatitis",
            "intestinal obstruction", "perforation", "abscess",
            "fistula", "hemorrhoids", "fissure", "fistula in ano",
            "varicose veins", "trauma", "burns", "fracture", "shock",
            "hemorrhage", "peritonitis",
        ),
        "drug": ("morphine", "tramadol", "fentanyl", "ketamine",
                 "propofol", "ondansetron", "metronidazole",
                 "ceftriaxone", "amoxicillin-clavulanate"),
        "investigation": ("x-ray", "ct", "mri", "ultrasound",
                          "contrast study", "barium", "endoscopy",
                          "ercp", "mrcp", "colonoscopy"),
    },
    "Microbiology": {
        "disease": ("tuberculosis", "hiv", "hepatitis b", "hepatitis c",
                    "malaria", "dengue", "typhoid", "cholera",
                    "leprosy", "leishmaniasis", "filariasis",
                    "brucellosis", "syphilis", "gonorrhea", "candidiasis"),
        "drug": ("isoniazid", "rifampicin", "ethambutol",
                 "pyrazinamide", "penicillin", "amoxicillin",
                 "azithromycin", "ciprofloxacin", "doxycycline",
                 "metronidazole", "fluconazole", "amphotericin",
                 "acyclovir", "artemisinin", "chloroquine"),
        "investigation": ("gram stain", "acid-fast", "zn stain",
                          "culture", "sensitivity", "serology",
                          "elisa", "pcr", "western blot", "viral load"),
    },
    "Pathology": {
        "disease": ("neoplasm", "carcinoma", "sarcoma", "lymphoma",
                    "leukemia", "adenoma", "metastasis", "infarction",
                    "inflammation", "necrosis", "apoptosis", "fibrosis",
                    "cirrhosis", "atherosclerosis", "thrombosis",
                    "embolism"),
        "investigation": ("biopsy", "fnab", "histopathology",
                          "immunohistochemistry", "ihc", "frozen section"),
    },
    "Pharmacology": {
        "drug": ("agonist", "antagonist", "inhibitor", "stimulator",
                 "blocker", "receptor", "enzyme", "channel",
                 "aspirin", "morphine", "metformin", "warfarin"),
        "investigation": ("dose-response curve", "therapeutic index",
                          "ld50", "ec50"),
    },
    "Anatomy": {
        "anatomy": ("brachial plexus", "lumbar plexus", "sacral plexus",
                    "circle of willis", "portal vein", "vena cava",
                    "aorta", "femoral nerve", "sciatic nerve",
                    "median nerve", "ulnar nerve", "radial nerve",
                    "heart", "lung", "liver", "kidney", "spleen",
                    "pancreas", "stomach", "duodenum", "jejunum",
                    "ileum", "colon", "rectum"),
    },
}


def _map_to_concepts(stem: str, subject: str) -> list[dict[str, Any]]:
    """Return [{type, name, confidence}] deterministic from stem + subject."""
    if not stem or not subject:
        return []
    text = stem.lower()
    out: list[dict[str, Any]] = []
    vocab = VOCAB.get(subject, {})
    for ctype, names in vocab.items():
        for name in names:
            if name in text:
                out.append({"type": ctype, "name": name, "confidence": 0.85})
    # De-dupe.
    seen = set()
    uniq = []
    for c in out:
        k = (c["type"], c["name"])
        if k in seen:
            continue
        seen.add(k)
        uniq.append(c)
    return uniq


def run(ctx: MceContext, *, pages: Optional[list[int]] = None,
        force: bool = False) -> StageResult:
    res = StageResult(stage="stage_9_graph")
    out_dir: Path = ctx.stage_dir("09_graph")
    stage7_dir = ctx.stage_dir("07_structured")
    stage7_index = stage7_dir / "_index.json"

    if not stage7_index.exists():
        res.errors.append("Stage 7 index missing — run Stage 7 first")
        return res
    try:
        s7 = json.loads(stage7_index.read_text(encoding="utf-8"))
        questions = s7.get("questions", [])
    except Exception as e:
        res.errors.append(f"stage 7 index read failed: {e}")
        return res

    if pages:
        pages_set = set(pages)
        questions = [q for q in questions if int(q["page_number"]) in pages_set]

    nodes_path = out_dir / "nodes.jsonl"
    edges_path = out_dir / "edges.jsonl"
    related_path = out_dir / "related_questions.jsonl"

    nodes_path.parent.mkdir(parents=True, exist_ok=True)
    nodes_path.write_text("", encoding="utf-8") if force or not nodes_path.exists() else None
    edges_path.write_text("", encoding="utf-8") if force or not edges_path.exists() else None
    related_path.write_text("", encoding="utf-8") if force or not related_path.exists() else None

    node_count = 0
    edge_count = 0
    related_count = 0
    seen_node_keys: set[tuple[str, str]] = set()
    seen_edge_keys: set[tuple[str, str, str]] = set()

    with nodes_path.open("a", encoding="utf-8") as nf, \
         edges_path.open("a", encoding="utf-8") as ef, \
         related_path.open("a", encoding="utf-8") as rf:
        for q in questions:
            qid = q["id"]
            subject = q.get("subject")
            topic = q.get("topic")
            stem = q.get("stem", "")

            # Always emit subject + topic nodes (even if NULL).
            for ctype, name, conf in (
                ("subject", subject, 1.0) if subject else (None, None, None),
                ("topic", topic, 0.9) if topic else (None, None, None),
            ):
                if ctype and name:
                    key = (ctype, name)
                    if key not in seen_node_keys:
                        seen_node_keys.add(key)
                        nf.write(json.dumps({"type": ctype, "name": name,
                                             "confidence": conf,
                                             "source_trace_qid": qid}) + "\n")
                        node_count += 1
                    ek = (qid, "question", f"{ctype}:{name}")
                    if ek not in seen_edge_keys:
                        seen_edge_keys.add(ek)
                        ef.write(json.dumps({
                            "src": qid, "src_type": "question",
                            "dst": f"{ctype}:{name}", "dst_type": ctype,
                            "weight": conf,
                        }) + "\n")
                        edge_count += 1

            # Concept extraction.
            for c in _map_to_concepts(stem, subject or ""):
                key = (c["type"], c["name"])
                if key not in seen_node_keys:
                    seen_node_keys.add(key)
                    nf.write(json.dumps({"type": c["type"], "name": c["name"],
                                         "confidence": c["confidence"],
                                         "source_trace_qid": qid}) + "\n")
                    node_count += 1
                ek = (qid, "question", f"{c['type']}:{c['name']}")
                if ek not in seen_edge_keys:
                    seen_edge_keys.add(ek)
                    ef.write(json.dumps({
                        "src": qid, "src_type": "question",
                        "dst": f"{c['type']}:{c['name']}", "dst_type": c["type"],
                        "weight": c["confidence"],
                    }) + "\n")
                    edge_count += 1

    # Naive related-question linking: questions sharing >= 2 concepts.
    if len(questions) >= 2:
        from collections import defaultdict
        q_to_concepts: dict[str, set[str]] = defaultdict(set)
        # Rebuild concept map cheaply by re-extracting.
        for q in questions:
            for c in _map_to_concepts(q.get("stem", ""), q.get("subject") or ""):
                q_to_concepts[q["id"]].add(f"{c['type']}:{c['name']}")
        ids = list(q_to_concepts.keys())
        for i, a in enumerate(ids):
            for b in ids[i + 1:]:
                shared = q_to_concepts[a] & q_to_concepts[b]
                if len(shared) >= 2:
                    rf.write(json.dumps({
                        "q_a": a, "q_b": b,
                        "shared_concepts": sorted(shared),
                        "similarity": len(shared) / max(1, len(q_to_concepts[a] | q_to_concepts[b])),
                    }) + "\n")
                    related_count += 1

    (out_dir / "_index.json").write_text(json.dumps({
        "pdf_filename": ctx.pdf_filename,
        "pdf_sha256_short": ctx.pdf_sha256_short,
        "node_count": node_count,
        "edge_count": edge_count,
        "related_count": related_count,
    }, indent=2, ensure_ascii=False), encoding="utf-8")

    res.metrics = {
        "nodes": node_count,
        "edges": edge_count,
        "related_question_pairs": related_count,
    }
    LOG.info("stage_9_graph: %d nodes, %d edges, %d related pairs",
             node_count, edge_count, related_count)
    return res


__all__ = ["run", "VOCAB"]
