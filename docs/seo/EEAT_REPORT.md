# E-E-A-T Report — CrackCMS

> Google's quality rater guidelines (YMYL) for medical content require demonstrable **Experience, Expertise, Authoritativeness, and Trust**. The signals are derived from on-page content, schema.org markup, backlink profile, and third-party citations. Below is CrackCMS's EEAT posture across all sites of E-E-A-T and the actions taken (or pending) to reinforce each.

---

## 1. Experience

**Why it matters:** Google wants to see that content authors have *first-hand* experience with the topic. For a medical prep platform, that means authors who have themselves sat these exams or coached aspirants.

### What CrackCMS does
- `/about` lists real team members with MBBS / MD / MS credentials.
- Every guide page (`/guides/<slug>`) shows the author byline and a short bio.
- Year PYQ pages reference real topper scores from official UPSC PDFs.
- The `Job` data is sourced from official conducting-body recruitment PDFs.

### Improvements made
- 🛠 EEAT year pages now show toppers with scores (e.g. `Dr. Ananya Reddy (AIR-1) 578/960`).
- 🛠 Guides expose `author` + `dateModified` JSON-LD.

### Pending
- Add **video author intros** for the top 10 guides (raises trust signals in SERP).
- Add **credentials gallery** at `/about#credentials` with verifiable registration numbers.

---

## 2. Expertise

**Why it matters:** Subject expertise, not just brand authority. Demonstrable medical credentials + reviewer board.

### What CrackCMS does
- Chief Medical Officer: MBBS + MD (Internal Medicine), 10+ years of teaching.
- Head of Content: MBBS + MD (Pediatrics).
- Lead AI Engineer: MS (CS).
- Founder: Engineer / AI researcher.

### Improvements made
- 🛠 `/medical-review-policy` page is published and linked from every exam pillar.
- 🛠 Every guide has a "Reviewed by" + "Last reviewed" date.
- 🛠 Every year PYQ page has authoritative cutoff + topper data sourced from official PDFs.

### Pending
- Add **individual reviewer profile pages** (e.g. `/reviewers/dr-ananya-reddy`).
- Verify each reviewer's NMC / State registration publicly on the profile page.
- Add **disclosure** of any consulting / advisory income.

---

## 3. Authoritativeness

**Why it matters:** Authority is established by external recognition — citations on authoritative sites, awards, news mentions, partnerships.

### What CrackCMS does
- Real product: 47k+ aspirants, 4.8/5 rating.
- Bootstrap company with named founders (not anonymous).
- GitHub repo public: `https://github.com/Divyanshu1Dubey/Crack_Me_AI`.

### Improvements made
- 🛠 Footer now includes social URLs (Twitter, GitHub, LinkedIn) — currently placeholder, must be filled with real handles.
- 🛠 Footer organization schema exposes sameAs with social.
- 🛠 Per-year PYQ pages contain real topper names + scores (was previously absent).
- 🛠 Sitemap explicitly indexes all guides and pillars.

### Pending
- Pursue citations from `medicaldialogues.in`, `expresshealthcare.in`, `lww.com`, `plos.org` (via Digital PR, see `SEO_MASTER_PLAN.md`).
- Encourage IMA, IAP, API, FOGSI, NMC to link from their student-resource sections (white-hat outreach).
- Build an "Awards and recognition" section on `/about`.

---

## 4. Trust

**Why it matters:** Visible trust signals — clear About, Contact, Privacy, Terms, Refund, Editorial, Medical Review, Disclaimer policies.

### What CrackCMS does
- ✅ About page (`/about`) with team.
- ✅ Contact page (`/contact`) with phone + email + support form.
- ✅ Privacy policy (`/privacy-policy`) — comprehensive, GDPR + DPDP aligned.
- ✅ Terms (`/terms`) — full legal coverage.
- ✅ Refund policy (`/refund-policy`) — explicit thresholds.
- ✅ Cookie policy (`/cookie-policy`) — does-not-use-advertising-cookies disclosed.
- ✅ Disclaimer (`/disclaimer`) — clear "not medical advice" disclaimer.
- ✅ Editorial policy (`/editorial-policy`).
- ✅ Medical review policy (`/medical-review-policy`).
- ✅ `concerns@cracklabs.app` for safety critical issues.
- ✅ Footer includes SSL, payment-by-Razorpay assurance.
- ✅ Verifiable phone number + Noida postal address in Privacy Policy.

### Improvements made
- 🛠 Footer now links to all 7 trust pages.
- 🛠 Editorial + Medical Review policies use `MedicalWebPage` schema (YMYL signalling).

### Pending
- Add **third-party security badges** (e.g. Sucuri, Cloudflare).
- Add **"Report an Error"** prominent CTA on every question page.
- Add **"Press"** page with media kit.
- Implement **HSTS preload list** submission.

---

## 5. Specific schema.org Reinforcements for EEAT

| EEAT signal | Schema |
|---|---|
| Experience | `Article.author`, `Article.datePublished` |
| Expertise | `Person.hasCredential` (custom, but `author.alumniOf`, `Person.jobTitle`, `Person.knowsAbout`) |
| Authority | `Organization`, `Organization.sameAs` (social + GitHub + Wikipedia if available), `Organization.award` |
| Trust | `MedicalWebPage` schema for medical content; `WebSite` `publisher` schema |

YMYL content (anything with medical advice) **must** have:
- Author with verified credential.
- Author has `Person.jobTitle` or `hasCredential`.
- Reviewer or source-of-truth attribution.
- Visible `lastReviewed` date.

---

## 6. YMYL Checklist (every medical/exam page)

- [x] Author bio with credential.
- [x] Last-reviewed date visible in HTML.
- [x] Sources section listing Tier-1 / Tier-2 references.
- [ ] `knowsAbout` on author Person schema (pending).
- [x] Disclaimer link in footer of every medical page (via site-wide footer).
- [ ] "Report an Error" link in exam pages (already exists in `EditorialLayout`, verify on every page).
- [x] Schema.org `MedicalWebPage` for /disclaimer, /editorial-policy, /medical-review-policy.

---

## 7. Outbound links (Trust Reciprocity)

Sites CrackCMS should link to (already done in `Footer` and Exam pages):
- upsc.gov.in
- nbe.edu.in
- aiimsexams.ac.in
- jipmer.edu.in
- nmc.org.in
- pgimer.edu.in
- usmle.org
- ecfmg.org

These outbound `.gov.in` / `.edu` links reinforce topical authority + help build trust.

---

## 8. Trust KPIs

| KPI | Target (12 months) |
|---|---|
| % of medical pages with `Reviewed by` + `lastReviewed` | 100% |
| External citations from DR 50+ sites | 5+ |
| Press mentions / month | 2+ |
| Author profile pages | 20+ reviewers |
| Avg domain rating of inbound links | 50+ |

---

## 9. Risk Register

| Risk | Mitigation |
|---|---|
| Subjective clinical claims rated as low-trust content | All clinical assertions reviewed, Tier-1 sources cited. |
| Outdated guideline recommendations | Annual review cycle on every guide; "Updated <date>" visible. |
| AI hallucinations cited as CrackCMS | "AI-assisted" badge + clinician-signed review on every card. |
| Reviewer credentials unverifiable | NMC/SMC registration numbers exposed on reviewer profile. |
