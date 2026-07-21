# Internal Linking Report — CrackCMS

> Internal linking has two jobs: distribute PageRank from hubs (pillars) to spokes (long-tail pages), and signal **topical relationships** to Google + AI retrieval engines. This report audits the current state, lists the patterns that must be applied, and proposes a check-list to verify before merging any new page.

---

## 1. Current State

### Strong
- ✅ The site-wide `<Footer>` (`frontend/src/components/Footer.tsx`) emits a `<SiteNavigationElement>` JSON-LD graph covering all exam pillars, guides, prepare-tools, company, legal links.
- ✅ Every exam pillar emits a `<BreadcrumbList>` JSON-LD: `Home -> ExamName`.
- ✅ Every guide emits a 3-level breadcrumb JSON-LD: `Home -> Guides -> GuideName`.
- ✅ Programmatic year pages (`/cms/pyq/[year]`) emit 4-level breadcrumb: `Home -> CMS -> PYQs -> Year`.
- ✅ Exam pillar pages have a "Related exams" pill section at the bottom with cross-links to other exam pillars.
- ✅ Guide pages have a related-guide section.

### Gaps
- ❌ Per-page *contextual* in-content links: from within text blocks to related guides / subjects / year pages.
- ❌ Topical-clusters: subjects should be linked from within pillars and from guides.
- ❌ The landing (`/`) has minimal cross-linking to exam pillars inside the body copy (most are buttons).
- ❌ The guides hub has no per-cluster grouping.
- ❌ Year PYQ pages link to `/questions?exam=...&year=...` but the question bank is gated.
- ❌ No "Topical mini-hubs" for individual subjects (Cardiology, OBG, etc.) — Phase 2.

---

## 2. Hub-and-Spoke Architecture

```
                     ROOT (/)
                        │
   ┌───────┬────────────┼───────────┬────────────┐
   │       │            │           │            │
  /cms  /neet-pg   /ini-cet    /fmge /usmle       /guides
   │       │            │           │           │
 /cms    /neet-pg     /ini-cet   /fmge /usmle   /guides/upsc-cms...
 /pyq    /pyq         /pyq       /pyq           /guides/neet-pg...
   │       │            │           │
 /cms    /neet-pg     /ini-cet   /fmge /usmle
 /pyq    /pyq         /pyq       /pyq
 /[year] /[year]      /[year]    /[year]
```

Every spoke links back to its hub + at least 2 sibling pillars via related/explore links.

---

## 3. Required Internal Links Per Page Type

| Page type | Inbound links | Outbound contextual links |
|---|---|---|
| Root `/` | All external backlinks | Every exam pillar, every guide, registration, contact |
| Exam pillar `/<exam>` | Footer, sitemap, root | PYQ hub, year hub (link to first year), books → guides, comparable exams |
| Year PYQ `/<exam>/pyq/[year]` | Exam pillar, PYQ hub | Topper names → About, related year-pages (prev/next), AI tutor → /register |
| Guide `/guides/[slug]` | Guides hub, relevant exam pillar, related guides | Cited textbooks → publisher, exam pillar, related guides |
| `/about` | Footer, root | Contact, editorial policy, medical review policy |
| `/contact` | Footer, root | Privacy policy, refund policy |
| `/resources` | Root, footer | Exam pillars, official notifications (UPSC, NBE) |

---

## 4. Contextual In-Content Link Patterns

These patterns should be applied in a 1-pass review of every page:

### "What is" or definitional reference
> "**UPSC CMS** is one of the **most-sought medical officer exams in India** [→ `/cms`], alongside **INI-CET** [→ `/ini-cet`] and **NEET PG** [→ `/neet-pg`]."

### "How to prepare" reference
> "For a 6-month study plan, see our [comprehensive UPSC CMS guide](/guides/upsc-cms-complete-guide). For subject-wise weak-topic analytics, see [analytics](/analytics)."

### Book reference
> "The single-most-recommended text is **Harrison's Principles of Internal Medicine** [→ `/textbooks`] — paired with **Robbins** for pathology."

### Textbook chapter reference
> "Covered in Harrison's Chapter 273, page 1453-1460. See [textbooks/harrisons](/textbooks)."

### Topper reference
> "**Dr. Ananya Reddy (AIR-1, 578/960)** [→ `/about#team`]. See [year `/cms/pyq/2024`](/cms/pyq/2024) for full topper list."

### Subject reference
> "High-yield cardiology MCQs are aggregated in [CMS subject hub `/cms/subject/cardiology`](/cms/subject/cardiology) (Phase 2)."

### Cutoff reference
> "The 2024 cutoff for General category was **320/960**. See [cutoff page `/cms/cutoff/2024`](/cms/cutoff/2024)."

---

## 5. Anchor Text Policy

- **First mention of an entity**: use exact-match anchor (e.g. "UPSC CMS Cutoff").
- **Subsequent mentions**: branded or generic (e.g. "the exam", "this exam").
- **Avoid naked URLs** in copy.
- **Avoid keyword-stuffed** anchors ("UPSC CMS UPSC CMS UPSC CMS").

---

## 6. Orphan Page Audit

Run `grep` to detect pages that have no inbound links.

```
# Pages with no internal links pointing to them (manual audit):
frontend/src/app/about
frontend/src/app/contact
frontend/src/app/editorial-policy
frontend/src/app/medical-review-policy
frontend/src/app/disclaimer
frontend/src/app/cookies-policy (legacy)
```

Mitigation:
- ✅ All are linked from the global `<Footer>`.
- ❌ Add explicit cross-links from `/about` to editorial + medical-review policies.

---

## 7. Internal Linking Automation Checklist

Add a CI step that:
1. Builds the route graph from `frontend/src/app/`.
2. Computes PageRank-inspired internal weights.
3. Flags pages with **0 inbound** (orphans) or **PageRank < threshold** (weak hubs).
4. Fails the build if a new orphan appears.

This is a 1-day task using a small `tsx` script + `glob`.

---

## 8. Sitemap / `<Footer>` / Breadcrumbs Triangulation

Always check 3 sources confirm a page is "linked":
1. `<Footer>` site navigation list.
2. `sitemap.ts`.
3. Breadcrumb JSON-LD (every page).

If a new public page is added and not in any of these three, it's an orphan.

---

## 9. Priority Action Items

| Priority | Action | Owner |
|---|---|---|
| P0 | Verify every public page is in the `<Footer>` + sitemap. | (already done) |
| P1 | Add contextual "related" links to every exam pillar (pattern above). | Phase 2 |
| P1 | Phase 2: subject-hub pages (`/<exam>/subject/[slug]`) for top 12 subjects. | Phase 2 |
| P2 | Per-state MO pages. | Phase 2 |
| P2 | CI step: orphan detector. | Phase 3 |
