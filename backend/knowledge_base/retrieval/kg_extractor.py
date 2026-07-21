"""
Lightweight pattern-based entity + relation extractor.

Goal: enlarge the curated ontology with co-occurrence and pattern
edges derived from approved chunks. No LLM dependency so this is
fast, deterministic, and runs in any environment.

What it does:
  1. For each approved chunk, find entity mentions (exact match on
     `KnowledgeEntity.name` + synonyms).
  2. If a chunk mentions >=2 entities, infer "related_to" edges
     weighted by co-occurrence.
  3. Detect drug mentions with their disease context for "treated_by"
     patterns.
  4. Detect investigation mentions with disease context for
     "investigated_by" patterns.

This adds breadth beyond the curated ontology without inventing
medical facts — edges are inferred only from observed co-mention.
"""

import logging
import re
from collections import Counter, defaultdict
from typing import Optional

from knowledge_base.models import (
    KnowledgeChunk, KnowledgeEntity, KnowledgeRelation,
)

logger = logging.getLogger(__name__)


class KGExtractor:
    def __init__(self, min_cooccurrence: int = 2,
                 max_new_entities: int = 200,
                 max_new_relations: int = 1000):
        self.min_cooccurrence = min_cooccurrence
        self.max_new_entities = max_new_entities
        self.max_new_relations = max_new_relations

    def extract_all(self, subject: Optional[str] = None) -> dict:
        qs = KnowledgeChunk.objects.filter(
            is_active=True,
            approval_state__in=[
                KnowledgeChunk.APPROVAL_AUTO,
                KnowledgeChunk.APPROVAL_ADMIN,
            ],
        )
        if subject:
            qs = qs.filter(subject=subject)
        entities = list(KnowledgeEntity.objects.all())
        # Pre-index name tokens for fast scan
        name_index = []
        for e in entities:
            for term in [e.name, *(e.synonyms or [])]:
                if term and len(term) > 2:
                    name_index.append((term.lower(), e))
        name_index.sort(key=lambda x: -len(x[0]))

        co_counts: Counter = Counter()
        drug_in_disease: defaultdict = defaultdict(Counter)
        inv_in_disease: defaultdict = defaultdict(Counter)

        for chunk in qs.iterator(chunk_size=200):
            text_lower = chunk.text.lower()
            present = []
            seen_entity_ids = set()
            for term, ent in name_index:
                if ent.id in seen_entity_ids:
                    continue
                if term in text_lower:
                    present.append(ent)
                    seen_entity_ids.add(ent.id)
            if len(present) < 2:
                continue
            for a in present:
                for b in present:
                    if a.id == b.id:
                        continue
                    key = tuple(sorted((a.id, b.id)))
                    co_counts[key] += 1
            # Drug-disease co-occurrence
            diseases = [e for e in present if e.entity_type == "disease"]
            drugs = [e for e in present if e.entity_type == "drug"]
            invs = [e for e in present if e.entity_type == "investigation"]
            for d in diseases:
                for dr in drugs:
                    drug_in_disease[d.id][dr.id] += 1
            for d in diseases:
                for inv in invs:
                    inv_in_disease[d.id][inv.id] += 1

        new_entities = 0
        new_relations = 0

        # Persist "treated_by" edges
        for d_id, drugs in drug_in_disease.items():
            for dr_id, count in drugs.items():
                if count < self.min_cooccurrence:
                    continue
                _, created = KnowledgeRelation.objects.get_or_create(
                    source_entity_id=d_id,
                    target_entity_id=dr_id,
                    relation="treated_by",
                    defaults={"weight": min(2.0, 0.5 + 0.1 * count),
                              "curated": False},
                )
                if created:
                    new_relations += 1
                    if new_relations >= self.max_new_relations:
                        break

        for d_id, invs in inv_in_disease.items():
            for inv_id, count in invs.items():
                if count < self.min_cooccurrence:
                    continue
                _, created = KnowledgeRelation.objects.get_or_create(
                    source_entity_id=d_id,
                    target_entity_id=inv_id,
                    relation="investigated_by",
                    defaults={"weight": min(2.0, 0.5 + 0.1 * count),
                              "curated": False},
                )
                if created:
                    new_relations += 1
                    if new_relations >= self.max_new_relations:
                        break

        # Persist "related_to" edges from co-occurrence
        for (a_id, b_id), count in co_counts.items():
            if count < self.min_cooccurrence:
                continue
            # Choose direction by entity_type priority
            a = next((e for e in entities if e.id == a_id), None)
            b = next((e for e in entities if e.id == b_id), None)
            if not a or not b:
                continue
            priority = {"disease": 0, "drug": 1, "investigation": 2,
                         "procedure": 2, "anatomy": 3, "symptom": 3,
                         "guideline": 4, "concept": 5}
            if priority.get(a.entity_type, 9) <= priority.get(b.entity_type, 9):
                src, tgt = a, b
            else:
                src, tgt = b, a
            _, created = KnowledgeRelation.objects.get_or_create(
                source_entity=src,
                target_entity=tgt,
                relation="related_to",
                defaults={"weight": min(1.5, 0.3 + 0.05 * count),
                          "curated": False},
            )
            if created:
                new_relations += 1
                if new_relations >= self.max_new_relations:
                    break

        return {
            "new_entities": new_entities,
            "new_relations": new_relations,
            "total_entities": KnowledgeEntity.objects.count(),
            "total_relations": KnowledgeRelation.objects.count(),
        }