"""
Ontology loader — pushes the curated UPSC-CMS ontology into the
KnowledgeEntity + KnowledgeRelation tables, and registers whitelisted
KnowledgeSource rows for all legal ingestion sources.

Idempotent: safe to run multiple times.

Usage:
    from knowledge_base.ontology.loader import load_ontology
    load_ontology()  # creates entities + relations + sources
"""

import logging
from typing import Optional

from django.db import transaction

from knowledge_base.models import (
    KnowledgeEntity, KnowledgeRelation, KnowledgeSource,
    LICENSE_PUBLIC_DOMAIN, LICENSE_CC_BY, LICENSE_CC_BY_SA,
    LICENSE_CC_BY_NC_SA, LICENSE_GOVT_INDIA, LICENSE_OWN_INTERNAL,
)

from .data import ENTITIES, RELATIONS, PYQ_TOPICS_BY_SUBJECT, QUERY_SYNONYMS

logger = logging.getLogger(__name__)


# ─── Whitelisted sources ───────────────────────────────────────────────────
# Each entry becomes a KnowledgeSource row. The slug is referenced
# by connectors — anything not in this list is rejected by ingestion.
WHITELIST_SOURCES = [
    # Internal — CrackLabs-authored content
    {
        "slug": "internal-notes",
        "name": "CrackLabs Internal Study Notes",
        "description": "Notes authored by CrackLabs content team.",
        "source_url": "https://www.cracklabs.app/",
        "api_endpoint": "",
        "license": LICENSE_OWN_INTERNAL,
        "attribution": "CrackLabs Internal",
        "citation_template": "{title} — CrackLabs internal notes. cracklabs.app",
        "is_active": True,
    },
    {
        "slug": "internal-pyqs",
        "name": "CrackLabs Internal PYQ Corpus",
        "description": "UPSC CMS previous-year question corpus (compiled from publicly released papers).",
        "source_url": "https://www.cracklabs.app/cms/pyq",
        "api_endpoint": "",
        "license": LICENSE_OWN_INTERNAL,
        "attribution": "CrackLabs",
        "citation_template": "UPSC CMS PYQ {year} — Paper {paper}. cracklabs.app",
        "is_active": True,
    },
    # US Public Domain
    {
        "slug": "ncbi-bookshelf",
        "name": "NCBI Bookshelf / StatPearls",
        "description": "National Library of Medicine Bookshelf and StatPearls — US Federal Government public-domain medical reference.",
        "source_url": "https://www.ncbi.nlm.nih.gov/books/",
        "api_endpoint": "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/",
        "license": LICENSE_PUBLIC_DOMAIN,
        "attribution": "NCBI Bookshelf / StatPearls (US NLM, public domain)",
        "citation_template": "{title}. In: StatPearls [Internet]. Treasure Island (FL): StatPearls Publishing; {year}. Available from: {url}",
        "is_active": True,
    },
    {
        "slug": "pubmed-central-oa",
        "name": "PubMed Central Open Access",
        "description": "Open-access subset of PubMed Central — peer-reviewed biomedical articles available under CC licenses.",
        "source_url": "https://www.ncbi.nlm.nih.gov/pmc/",
        "api_endpoint": "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/",
        "license": LICENSE_CC_BY,
        "attribution": "PubMed Central Open Access (NCBI/NLM)",
        "citation_template": "{authors}. {title}. {journal} ({year}). PMC{pmcid}.",
        "is_active": True,
    },
    # OpenStax (CC BY)
    {
        "slug": "openstax-anatomy",
        "name": "OpenStax — Anatomy & Physiology",
        "description": "OpenStax Anatomy & Physiology textbook (CC BY 4.0).",
        "source_url": "https://openstax.org/details/books/anatomy-and-physiology",
        "api_endpoint": "https://openstax.org/apps/archive/",
        "license": LICENSE_CC_BY,
        "attribution": "OpenStax Anatomy & Physiology (CC BY 4.0)",
        "citation_template": "Betts, J.G., et al. Anatomy and Physiology. OpenStax (2021). CC BY 4.0.",
        "is_active": True,
    },
    {
        "slug": "openstax-microbiology",
        "name": "OpenStax — Microbiology",
        "description": "OpenStax Microbiology textbook (CC BY 4.0).",
        "source_url": "https://openstax.org/details/books/microbiology",
        "api_endpoint": "https://openstax.org/apps/archive/",
        "license": LICENSE_CC_BY,
        "attribution": "OpenStax Microbiology (CC BY 4.0)",
        "citation_template": "Parker, N., et al. Microbiology. OpenStax (2021). CC BY 4.0.",
        "is_active": True,
    },
    {
        "slug": "openstax-psychology",
        "name": "OpenStax — Psychology",
        "description": "OpenStax Psychology textbook (CC BY 4.0).",
        "source_url": "https://openstax.org/details/books/psychology-2e",
        "api_endpoint": "https://openstax.org/apps/archive/",
        "license": LICENSE_CC_BY,
        "attribution": "OpenStax Psychology (CC BY 4.0)",
        "citation_template": "Spielman, R.M., et al. Psychology 2e. OpenStax (2021). CC BY 4.0.",
        "is_active": True,
    },
    # WHO / ICMR / MoHFW / NMC / NHM — Indian and global public health
    {
        "slug": "who",
        "name": "World Health Organization",
        "description": "WHO guidelines, fact sheets, and IRIS publications (public domain).",
        "source_url": "https://www.who.int/publications",
        "api_endpoint": "https://ghoapi.azureedge.net/api/",
        "license": LICENSE_PUBLIC_DOMAIN,
        "attribution": "World Health Organization",
        "citation_template": "WHO. {title}. Geneva: World Health Organization; {year}.",
        "is_active": True,
    },
    {
        "slug": "mohfw-india",
        "name": "Ministry of Health and Family Welfare, India",
        "description": "MoHFW guidelines, scheme documents, annual reports (Government of India Open Data).",
        "source_url": "https://mohfw.gov.in/",
        "api_endpoint": "https://data.gov.in/",
        "license": LICENSE_GOVT_INDIA,
        "attribution": "Ministry of Health and Family Welfare, Government of India",
        "citation_template": "MoHFW. {title}. Government of India; {year}.",
        "is_active": True,
    },
    {
        "slug": "icmr",
        "name": "Indian Council of Medical Research",
        "description": "ICMR guidelines and research publications (Government of India).",
        "source_url": "https://www.icmr.gov.in/",
        "api_endpoint": "https://data.gov.in/",
        "license": LICENSE_GOVT_INDIA,
        "attribution": "Indian Council of Medical Research",
        "citation_template": "ICMR. {title}. New Delhi: ICMR; {year}.",
        "is_active": True,
    },
    {
        "slug": "nmc-india",
        "name": "National Medical Commission, India",
        "description": "NMC guidelines for MBBS curriculum and Competency-Based Medical Education.",
        "source_url": "https://www.nmc.org.in/",
        "api_endpoint": "",
        "license": LICENSE_GOVT_INDIA,
        "attribution": "National Medical Commission, India",
        "citation_template": "NMC. {title}. New Delhi: National Medical Commission; {year}.",
        "is_active": True,
    },
    {
        "slug": "nhm-india",
        "name": "National Health Mission",
        "description": "NHM operational guidelines, scheme documents.",
        "source_url": "https://nhm.gov.in/",
        "api_endpoint": "",
        "license": LICENSE_GOVT_INDIA,
        "attribution": "National Health Mission, Government of India",
        "citation_template": "NHM. {title}. Government of India; {year}.",
        "is_active": True,
    },
    {
        "slug": "upsc",
        "name": "Union Public Service Commission",
        "description": "UPSC CMS notifications, syllabus, PYQ papers.",
        "source_url": "https://upsc.gov.in/examinations/cms",
        "api_endpoint": "",
        "license": LICENSE_GOVT_INDIA,
        "attribution": "Union Public Service Commission",
        "citation_template": "UPSC. CMS Examination {year}. upsc.gov.in.",
        "is_active": True,
    },
    # NHS / NICE
    {
        "slug": "nhs-cks",
        "name": "NHS Clinical Knowledge Summaries",
        "description": "NHS CKS — evidence-based clinical summaries (open license).",
        "source_url": "https://cks.nice.org.uk/",
        "api_endpoint": "",
        "license": LICENSE_CC_BY_NC_SA,
        "attribution": "NHS Clinical Knowledge Summaries (CC BY-NC-SA)",
        "citation_template": "NHS CKS. {title}. cks.nice.org.uk.",
        "is_active": True,
    },
    # Radiopaedia
    {
        "slug": "radiopaedia",
        "name": "Radiopaedia.org",
        "description": "Radiopaedia peer-reviewed radiology reference (CC BY-NC-SA 3.0).",
        "source_url": "https://radiopaedia.org/",
        "api_endpoint": "https://radiopaedia.org/api/v1/",
        "license": LICENSE_CC_BY_NC_SA,
        "attribution": "Radiopaedia.org (CC BY-NC-SA 3.0)",
        "citation_template": "{authors}. {title}. Radiopaedia.org. {url}",
        "is_active": True,
    },
]


@transaction.atomic
def load_ontology(reset: bool = False) -> dict:
    """
    Push curated ontology into the database. Idempotent.
    Returns counts.
    """
    if reset:
        KnowledgeRelation.objects.all().delete()
        KnowledgeEntity.objects.all().delete()

    entity_count = 0
    for (name, etype, subject, canonical_id, synonyms, definition) in ENTITIES:
        obj, created = KnowledgeEntity.objects.update_or_create(
            name=name,
            entity_type=etype,
            defaults={
                "canonical_id": canonical_id,
                "synonyms": synonyms or [],
                "definition": definition,
                "subject": subject,
                "curated": True,
            },
        )
        if created:
            entity_count += 1

    # Build a name+type -> entity lookup for relations
    entities_by_key = {
        (e.name, e.entity_type): e for e in KnowledgeEntity.objects.all()
    }

    relation_count = 0
    for (src, rel, tgt) in RELATIONS:
        src_e = entities_by_key.get((src, "disease")) or entities_by_key.get((src, "drug")) or entities_by_key.get((src, "symptom")) or entities_by_key.get((src, "investigation")) or entities_by_key.get((src, "anatomy")) or entities_by_key.get((src, "procedure")) or entities_by_key.get((src, "guideline")) or entities_by_key.get((src, "concept"))
        tgt_e = entities_by_key.get((tgt, "disease")) or entities_by_key.get((tgt, "drug")) or entities_by_key.get((tgt, "symptom")) or entities_by_key.get((tgt, "investigation")) or entities_by_key.get((tgt, "anatomy")) or entities_by_key.get((tgt, "procedure")) or entities_by_key.get((tgt, "guideline")) or entities_by_key.get((tgt, "concept"))
        if not src_e or not tgt_e:
            logger.debug(f"Skipping unresolved relation {src} -{rel}-> {tgt}")
            continue
        _, created = KnowledgeRelation.objects.get_or_create(
            source_entity=src_e,
            target_entity=tgt_e,
            relation=rel,
            defaults={"weight": 1.0, "curated": True},
        )
        if created:
            relation_count += 1

    source_count = 0
    for spec in WHITELIST_SOURCES:
        _, created = KnowledgeSource.objects.update_or_create(
            slug=spec["slug"],
            defaults=spec,
        )
        if created:
            source_count += 1

    logger.info(
        f"Ontology loaded: +{entity_count} entities, "
        f"+{relation_count} relations, +{source_count} sources"
    )
    return {
        "entities_added": entity_count,
        "relations_added": relation_count,
        "sources_added": source_count,
        "total_entities": KnowledgeEntity.objects.count(),
        "total_relations": KnowledgeRelation.objects.count(),
        "total_sources": KnowledgeSource.objects.count(),
    }


def expand_query(query: str) -> dict:
    """
    Expand a medical query with synonyms + abbreviations.

    Returns:
        {
            "original": str,
            "normalized": str,
            "expanded": str,         # original + synonyms joined
            "tokens": list[str],     # tokens for retrieval
            "subject_hints": list[str],
        }
    """
    import re

    q = (query or "").strip()
    if not q:
        return {"original": "", "normalized": "", "expanded": "",
                "tokens": [], "subject_hints": []}

    q_lower = q.lower()

    # Expand abbreviations found in the query
    expanded_terms = []
    subject_hints = []
    for token in re.findall(r"[a-zA-Z][a-zA-Z0-9\-]*", q_lower):
        # Try direct lookup
        if token in QUERY_SYNONYMS:
            canon = QUERY_SYNONYMS[token]
            if canon != token:
                expanded_terms.append(canon)
            # subject hint: if canonical token matches an entity name
            for e in KnowledgeEntity.objects.filter(name__iexact=canon).only("subject"):
                if e.subject and e.subject not in subject_hints:
                    subject_hints.append(e.subject)
                break
        else:
            expanded_terms.append(token)

    # Also match by entity name (case-insensitive) for subject hints
    for e in KnowledgeEntity.objects.filter(name__iexact=q_lower).only("subject"):
        if e.subject and e.subject not in subject_hints:
            subject_hints.append(e.subject)

    expanded = " ".join([q] + expanded_terms)
    tokens = re.findall(r"[a-zA-Z][a-zA-Z0-9\-]*", expanded.lower())

    return {
        "original": q,
        "normalized": q_lower,
        "expanded": expanded,
        "tokens": list(dict.fromkeys(tokens)),  # dedup, preserve order
        "subject_hints": subject_hints,
    }


def get_kg_neighbors(entity_name: str, hops: int = 1) -> list[dict]:
    """
    Walk the curated KG from an entity name. Returns a flat list of
    {from, relation, to, weight} dicts. Used by retrieval as an
    additional context source.
    """
    try:
        seed = KnowledgeEntity.objects.get(name__iexact=entity_name)
    except KnowledgeEntity.DoesNotExist:
        try:
            seed = KnowledgeEntity.objects.get(synonyms__contains=entity_name.lower())
        except KnowledgeEntity.DoesNotExist:
            return []

    visited = {seed.id}
    frontier = [(seed, 0)]
    results = []
    while frontier:
        current, depth = frontier.pop(0)
        if depth >= hops:
            continue
        for rel in current.outgoing.select_related("target_entity").all():
            results.append({
                "from": current.name,
                "relation": rel.relation,
                "to": rel.target_entity.name,
                "weight": rel.weight,
                "type": rel.target_entity.entity_type,
            })
            if rel.target_entity.id not in visited:
                visited.add(rel.target_entity.id)
                frontier.append((rel.target_entity, depth + 1))
        for rel in current.incoming.select_related("source_entity").all():
            results.append({
                "from": rel.source_entity.name,
                "relation": rel.relation,
                "to": current.name,
                "weight": rel.weight,
                "type": rel.source_entity.entity_type,
            })
            if rel.source_entity.id not in visited:
                visited.add(rel.source_entity.id)
                frontier.append((rel.source_entity, depth + 1))

    return results[:50]
