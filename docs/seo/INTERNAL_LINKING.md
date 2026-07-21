# Internal Linking Strategy — CrackCMS

**Date:** July 21, 2026

---

## Goal

Build a tight internal link graph that:
1. Distributes page authority from high-traffic landing pages to deep guides.
2. Helps search engines discover all 30+ public URLs.
3. Guides users from awareness (landing pages) → consideration (guides) → conversion (signup/premium).

---

## Hub-and-Spoke Model

```
                    Home (/)
                       |
       +---------------+---------------+
       |               |               |
    Exams           Guides         Company
       |               |               |
   +---+---+           |            +--+--+
   |   |   |           |            |     |
  CMS NEET INI       [8 guides]  About  Contact
   |   PG  CET
   |   |   |
   +---+---+
       |
   Guides for each
       |
   FAQs / Premium / Register
```

---

## Footer Link Map

The site-wide footer renders 5 link columns with 42 total links:

### Column 1: Exams
- /cms, /neet-pg, /ini-cet, /fmge, /usmle, /medical-officer, /government-doctor-jobs

### Column 2: Prepare
- /questions, /tests, /simulator, /ai-tutor, /generate, /roadmap, /flashcards, /textbooks, /resources, /trends

### Column 3: Guides
- /guides + 8 guide pages

### Column 4: Company
- /about, /contact, /subscription, /tokens, /jobs, /leaderboard, /bookmarks, /analytics

### Column 5: Legal
- /privacy-policy, /terms, /refund-policy, /cookie-policy, /disclaimer, /editorial-policy, /medical-review-policy, /feedback

---

## Contextual Links

### Landing pages → Guides
Each exam landing page includes a "Related resources" footer linking to:
- The corresponding guide
- 2-3 other related guides
- The other exam landing pages

### Guides → Landing pages + Guides
Each guide ends with:
- CTA back to /register
- Link to /questions (practice PYQs)
- Links to 2-3 other related guides
- Links to the relevant exam landing page

### About → Conversion
The /about page ends with a CTA section linking to /register + /subscription.

### Legal pages → Conversion
Each legal page ends with a "Related resources" box linking to /about, /contact, /register, /subscription.

---

## Link Attributes

| Type | Attribute | Why |
|---|---|---|
| Footer global links | `dofollow` | pass authority |
| Guide → landing page | `dofollow` | pass authority |
| Guide → guide | `dofollow` | distribute authority |
| Sidebar / nav links | `dofollow` | pass authority |
| "Apply for X" external | `dofollow` (when relevant) | referral |
| Social icons (footer) | `noreferrer` | privacy |

---

## Anchor Text Diversity

Avoid over-optimised anchor text. Mix:
- Exact match: "UPSC CMS"
- Partial match: "the CMS exam"
- Branded: "CrackCMS"
- Generic: "Read more", "Learn more"
- Long-tail: "How to prepare for UPSC CMS in 6 months"

---

## Orphan Page Audit

After this initiative, every public page has at least:
- 1 link from the footer
- 1 link from another public page
- 1 link from the sitemap

No orphan pages.

---

## Future Improvements

1. **Breadcrumbs** on every guide + landing page (rendered with BreadcrumbList schema).
2. **Related guides widget** at the end of each article — auto-suggest by topic similarity.
3. **Topic clusters** — for each subject (Cardiology, Respiratory, etc.) create a hub page that links to all related guides + PYQ filters.
4. **"Next article" pagination** — chain guides in a series.
5. **Sticky in-article CTAs** — every 1500 words insert a contextual CTA linking to a related product page.
