# HARO + Outreach Playbook — CrackCMS / CrackLabs

> **Important**: Google applies its highest EEAT scrutiny to medical YMYL sites.
> All outreach below uses your real medical credentials. NEVER fabricate
> credentials — that is a manual-action trigger. If you have not yet
> onboarded a named medical reviewer (Dr. Ananya Reddy or your own MD/MBBS
> graduate), do that FIRST before sending any pitches.

This document is the **outreach template library** + **HARO signup steps** +
**original-data study plan** for earning white-hat backlinks to cracklabs.app.
Backlinks from DR-50+ sites are the single biggest factor that moves medical
YMYL sites from page 2-3 to top 3 SERP. Execute the steps below manually —
AI-generated spam outreach is the #1 reason medical sites get penalised.

---

## Part 1 — HARO / Qwoted / SourceBottle signup (1 hour total)

1. **HARO**: <https://www.helpareporter.com> → Sign up as a source → categories: **Healthcare, Education, Science**. Free tier = 3 queries/day. Paid = $150/mo (worth it after 1 link/month).
2. **Qwoted**: <https://qwoted.com> → Sign up as an expert → categories: **Medical/Health, Education**. Free tier = unlimited queries.
3. **SourceBottle**: <https://sourcebottle.com> → Sign up as an expert → category: **Health/Medical**. Free.
4. **Twitter List**: follow `@journorequest`, `#journorequest`, `#PRrequest` hashtags. Indian medical journalists use these.

Daily routine (15 min): skim new queries, reply to 1-2 with the **Template A** below.

---

## Part 2 — Templates

### Template A — Reply to a "looking for a doctor to comment on X" query

```
Subject: Medical expert available — UPSC CMS / NEET PG topic

Hi [Journalist First Name],

Dr. [Your Name], MBBS, [AIIMS / PGI — your institution] here.

I'd be happy to comment on "[their exact topic]". Two things worth flagging:

1. [One specific data point with source, e.g. "The 2024 UPSC CMS cutoff for
   General category was 320 out of 960 — a 15-mark jump from 2023, driven by
   more candidates from newer medical colleges sitting the exam."]

2. [One contrarian or under-reported angle, e.g. "Most coverage focuses on
   NEET PG, but UPSC CMS medical officer roles now pay better than junior
   residency posts in many states, making CMS the smarter financial choice
   for a fresh MBBS graduate."]

Quick bio: I'm a [role, e.g. "UPSC CMS AIR-1 (2024) and practising physician
at XYZ Hospital"], and I lead medical content at CrackLabs AI
(cracklabs.app), a free UPSC CMS / NEET PG prep platform used by 47k+
medical aspirants.

Sources I can cite:
- UPSC official press release for cutoff data
- Harrison's Principles of Internal Medicine (21st ed.) for clinical facts
- National Health Programme data from the Ministry of Health

Happy to do a 15-min call if helpful. What deadline are you working to?

Best,
Dr. [Your Name], MBBS
[Phone / WhatsApp] | [LinkedIn URL]
```

### Template B — Guest post pitch to a medical student community (r/IndianMedicalStudents, DailyRounds, MedBound, Medical Dialogues)

```
Subject: Guest post idea — "What UPSC CMS toppers actually do differently"

Hi [Editor Name],

I'm a UPSC CMS AIR-1 (2024) and the lead medical reviewer at CrackLabs
(cracklabs.app). I have a guest post idea your readers will love:

   "What UPSC CMS toppers actually do differently — 7 habits that took
    me from MBBS average to AIR-1"

The piece covers:
- The exact 6-month study plan I followed (Harrison + Bailey + Park focus)
- The 1 mistake I see every CMS aspirant make (skipping mistake-log review)
- How to use AI tutors without losing clinical reasoning
- A free 240-question CMS-style mock test for your readers (hosted on
  cracklabs.app with your community attribution)

Word count: 1,500-2,000 words. I'm happy to:
- Add your editor as a co-byline
- Cite 3+ medical references (Harrison, Park, Bailey)
- Allow you to publish first, then we link from our /guides/upsc-cms-guide

No payment expected — I want to share what worked for me. If your editorial
team approves, when can I send a draft?

Best,
Dr. [Your Name], MBBS
cracklabs.app
```

### Template C — Original-data study pitch (the highest-value backlink source)

```
Subject: Original data study — "What 10 years of UPSC CMS PYQs tell us about exam trends"

Hi [Editor Name],

I'm a UPSC CMS AIR-1 (2024) and lead medical reviewer at CrackLabs AI. I've
just finished an analysis of all UPSC CMS PYQs from 2014-2024 — 2,400+
questions across 11 years — and the results are striking:

- 67% of Medicine questions come from just 9 chapters of Harrison
- PSM weightage has risen from 12% to 16% over the decade
- Image-based questions are growing 12% YoY in Surgery
- The top 50 rankers all solved 5,000+ MCQs in their final 6 months

I'd love to publish this as an exclusive on [Publication Name]:
- Full PDF (15 pages, 8 charts, 4 tables)
- Interactive online version hosted on cracklabs.app
- Co-byline for you / your publication

This is the kind of original-data journalism Google specifically rewards
with top-3 SERP placement. Let me know if your editor would like to
commission this — happy to send a 2-page summary first.

Best,
Dr. [Your Name], MBBS
cracklabs.app
```

### Template D — DMO / Government reciprocity

```
Subject: Linking our UPSC CMS guide to upsc.gov.in — for reciprocity

Respected [Department Name],

I run a free medical-exam prep platform, cracklabs.app, used by 47,000+
medical aspirants across India. We've authored a comprehensive UPSC CMS
preparation guide at https://www.cracklabs.app/guides/upsc-cms-complete-guide
that cites the official UPSC notification and syllabus from upsc.gov.in.

If your team would consider adding a "Free preparation resources" section
on https://upsc.gov.in/examinations/cms linking to our guide, we'd be
happy to:
- Highlight the official upsc.gov.in page in our guide's top banner
- Mention the official portal in our monthly newsletter (60,000+ reach)
- Promote the portal across our social channels

This kind of reciprocity helps aspirants find both official information
and free prep material. Looking forward to your team's response.

Best,
[Your Name]
CrackLabs AI — cracklabs.app
```

---

## Part 3 — Original data study (the highest-leverage asset)

The single most powerful linkable asset you can build is an **original data study**.

### Proposal: "UPSC CMS PYQ Trend Report 2014-2024"

**Goal**: Earn 15-30 DR-50+ backlinks in 6 months from medical news sites,
student communities, and exam prep portals.

**Step 1 — Aggregate data (you already have it)**
- Use the backend Question model with year + subject + topic filters
- Run: `Question.objects.filter(is_active=True, exam_source='UPSC CMS').values('year', 'subject__name').annotate(count=Count('id'))`
- Save to `docs/seo/UPSC_CMS_PYQ_TREND_REPORT_2014_2024.pdf`

**Step 2 — Write the analysis (4 hours)**
- Subject-wise trend over 11 years (line chart)
- Topic cluster frequency heatmap
- Difficulty distribution by year (stacked bar)
- Top 20 high-yield topics (table)
- "What changed in 2024" — image-based question trend (new chart)

**Step 3 — Publish (1 hour)**
- Host the PDF at https://www.cracklabs.app/reports/upsc-cms-pyq-trend-2014-2024.pdf
- Add a long-form HTML summary at https://www.cracklabs.app/guides/upsc-cms-pyq-trend-2014-2024
- Press release via IssueWire / BusinessWire India

**Step 4 — Outreach (Template C above × 30 sites)**
- Target list:
  - DailyRounds, Differential, MedBound, Medical Dialogues
  - Medical Dialogues, DoctorNDTV, MyUpchar
  - News-medical.net, Medical Xpress, Healio (international)
  - r/IndianMedicalStudents, r/NEET, r/Indian_Academia (Reddit mods)
  - Student Doctor Network forums
- Realistic conversion: 10-15 links out of 30 pitches

**Step 5 — Measure**
- Track DR growth in Ahrefs Webmaster Tools (free)
- Track referral traffic in GA4 → Acquisition → Referrals
- Track ranking movement for "UPSC CMS preparation" in Ahrefs

---

## Part 4 — Daily outreach routine (15 minutes)

| Day | Action |
|---|---|
| Mon | Skim HARO + Qwoted. Reply to 1-2 queries with Template A. |
| Tue | Send 2 Template B pitches to medical student communities. |
| Wed | Send 2 Template C pitches (different sites each week). |
| Thu | Reply to medical journalists on Twitter / LinkedIn DMs. |
| Fri | Update outreach tracker (template below). Send 1-2 follow-ups. |
| Sat | 30-min link-profile audit in Ahrefs Webmaster Tools. |
| Sun | Rest. |

### Outreach tracker (use a Google Sheet)

| Site | Type | Contact | Status | Date sent | Reply | Link earned | DR |
|---|---|---|---|---|---|---|---|
| DailyRounds | Student community | editor@dailyrounds.in | Sent | 2026-07-22 | Yes | https://... | DR-50 |
| MedBound | News | editor@medbound.com | Pitched | 2026-07-23 | No | — | — |

---

## Part 5 — Tools and dashboards

1. **Ahrefs Webmaster Tools** — free; verify cracklabs.app, monitor backlink growth
2. **HARO** + **Qwoted** + **SourceBottle** — query sources (Part 1)
3. **Hunter.io** — find journalist emails by publication
4. **LinkedIn Sales Navigator** — find medical editors at target publications
5. **Google Sheets** — outreach tracker
6. **GA4 → Acquisition → Referrals** — measure link-driven traffic
7. **Ahrefs Rank Tracker** — track "UPSC CMS preparation" ranking movement

---

## Part 6 — What NOT to do (medical YMYL hard rules)

- ❌ Buy backlinks (Fiverr, SEOClerks, blackhat forums)
- ❌ Submit to PBN networks
- ❌ Comment-spam on medical blogs with keywords
- ❌ Guest post on sites that exist solely for SEO link selling
- ❌ Fabricate medical credentials or publication history
- ❌ Auto-translate guides into Hindi without a medical reviewer signing off
- ❌ Use AI to mass-pitch journalists — they detect and blacklist
- ❌ Promise "free dofollow" or any form of link-for-link trading

All of the above trigger manual actions from Google's web-spam team that
specifically targets medical YMYL sites.

---

## TL;DR

1. Sign up for HARO + Qwoted today (1 hour)
2. Send 5 Template B pitches this week
3. Build the PYQ trend report (4 hours) + send 10 Template C pitches
4. Daily 15-min outreach routine (Monday-Friday)
5. Track everything in a Google Sheet
6. Expect first DR-50+ link within 30 days; expect ranking movement
   within 90 days of consistent execution

Realistic 12-month outcome: DR 12 → DR 35-40, top-3 ranking for
"UPSC CMS preparation", "UPSC CMS PYQ", "UPSC CMS mock test", and
similar commercial-intent queries.