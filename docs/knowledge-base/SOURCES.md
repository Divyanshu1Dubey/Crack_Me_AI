# Knowledge Base — Sources & Licensing

**This is the legally-defensible source whitelist.** Anything not on
this list must NOT enter the knowledge base. The connector layer and
`IngestionService` enforce this; the admin UI exposes a per-source
toggle.

## Whitelisted sources

| Slug | Name | License | Commercial OK | Source URL |
|---|---|---|---|---|
| `internal-notes` | CrackLabs Internal Notes | Internal | Yes (your content) | cracklabs.app |
| `internal-pyqs` | CrackLabs Internal PYQ Corpus | Internal | Yes (your content) | cracklabs.app |
| `ncbi-bookshelf` | NCBI Bookshelf / StatPearls | US Public Domain | Yes | ncbi.nlm.nih.gov/books |
| `pubmed-central-oa` | PubMed Central Open Access | CC BY / CC0 | Yes (with attribution) | ncbi.nlm.nih.gov/pmc |
| `openstax-anatomy` | OpenStax — Anatomy & Physiology | CC BY 4.0 | Yes (with attribution) | openstax.org |
| `openstax-microbiology` | OpenStax — Microbiology | CC BY 4.0 | Yes (with attribution) | openstax.org |
| `openstax-psychology` | OpenStax — Psychology 2e | CC BY 4.0 | Yes (with attribution) | openstax.org |
| `who` | World Health Organization | Public Domain | Yes | who.int |
| `mohfw-india` | MoHFW India | Government of India Open Data | Yes | mohfw.gov.in |
| `icmr` | Indian Council of Medical Research | Government of India Open Data | Yes | icmr.gov.in |
| `nmc-india` | National Medical Commission | Government of India Open Data | Yes | nmc.org.in |
| `nhm-india` | National Health Mission | Government of India Open Data | Yes | nhm.gov.in |
| `upsc` | Union Public Service Commission | Government of India Open Data | Yes | upsc.gov.in |
| `nhs-cks` | NHS Clinical Knowledge Summaries | CC BY-NC-SA 3.0 | Non-commercial only | cks.nice.org.uk |
| `radiopaedia` | Radiopaedia.org | CC BY-NC-SA 3.0 | Non-commercial only | radiopaedia.org |
| `user-attested` | User uploads with rights attestation | Per-user ToS | Per upload | user-uploaded |

## Sources we will NEVER ingest

Even with permission, ingesting these exposes CrackLabs to statutory
damages and platform bans. The loader has a hard guard against each
of these markers (case-insensitive, scanned on every chunk):

- **Textbooks** — Harrison's, Bailey & Love, Robbins, Park, Ghai,
  Nelson, Ganong, Guyton, KD Tripathi, Katzung, Harper, Goodman &
  Gilman, Williams, Davidson, Oxford Handbook, CMDT, Hutchison.
- **Competitor platforms** — Marrow, PrepLadder, DAMS, PrepCMS,
  GoMed.
- **Publisher brands** — Elsevier, McGraw-Hill, Wolters Kluwer, CBS
  Publishers, Oxford Medical, Lippincott.

These are owned by publishers; "permission from a friend" is not a
license grant. The legal fee to obtain a real license is in the
hundreds of thousands of dollars — and is rarely granted to B2C
edtech startups.

## Why StatPearls + OpenStax + WHO + Govt is enough

StatPearls (NCBI Bookshelf) is the same content USMLE prep tools
license for tens of thousands of dollars — except it's free, public
domain, and updated continuously.

OpenStax gives us ~5,000 pages of peer-reviewed anatomy, physiology,
microbiology, psychology, and sociology — half the MBBS syllabus —
with CC BY 4.0. Same content Amboss pays to license.

MoHFW + ICMR + NMC + NHM publish the actual Indian guidelines the
UPSC CMS exam tests on. These are Government of India works.

WHO + NHS CKS + Radiopaedia fill the rest with international,
peer-reviewed reference material.

**The retrieval + reasoning layer is the moat.** Whoever builds the
best citation engine + KG + medical ontology over free sources wins.
Stolen PDFs are not a moat — they're a liability.

## How the licence guard works

1. `KnowledgeSource.license` is the only license a chunk may carry.
2. `IngestionService` checks `PROHIBITED_LICENSE_MARKERS` against
   every chunk's text before writing.
3. `ConnectorBase._guard_text` does the same at the source layer.
4. `UserUploadsConnector` re-checks on every user upload.

Adding a new source requires:
1. Confirming the license is on the whitelist above.
2. Adding a `KnowledgeSource` row with correct `attribution` +
   `citation_template`.
3. Writing a connector that fetches from that source.
4. Documenting the source in this file.

If you cannot complete step 1, do not add the source.