# CrackCMS Growth OS
**Last updated:** 2026-09-17
**Purpose:** Persistent growth memory for autonomous execution across weekly/monthly cycles.

---

## BASELINE
- **GSC (Sep 2026):** 52,816 impressions · 598 clicks · 1,200+ queries
- **Traffic peak:** 311 clicks (Aug 2026)
- **Zero pages in positions 1-3** — biggest ranking gap
- **42 pages in positions 4-10** — revenue/traffic engine
- **CTR weakness:** High-impression pages underperforming (e.g., `/cms/vs-neet-pg` 15,735 imp, 0.3% CTR)
- **Mobile-heavy:** 75% mobile, 20% desktop, 5% tablet

---

## PROVEN WINNERS (protect & strengthen)
| Page | Clicks | Impressions | Position | CTR |
|------|--------|-------------|----------|-----|
| `/` (homepage) | 117 | 968 | 5.99 | 12.1% |
| `/cms/cutoff/2026` | 75 | 2,918 | 9.28 | 2.6% |
| `/cms` | 63 | 2,046 | 8.33 | 3.1% |
| `/cms/vs-neet-pg` | 52 | 15,735 | 4.40 | 0.3% |
| `/guides/upsc-cms-complete-guide` | 41 | 9,992 | 8.22 | 0.4% |
| `/medical-officer` | 28 | 1,035 | 5.76 | 2.7% |
| `/cms/subject/obg` | 26 | 362 | 3.82 | 7.2% |
| `/cms/subject/psm` | 17 | 298 | 5.14 | 5.7% |

**Action:** Keep these pages updated, strengthen internal links, add FAQ/structured data.

---

## DECLINING / UNDERPERFORMING PAGES (fix priority)
| Page | Issue | Action |
|------|-------|--------|
| `/cms/vs-neet-pg` | 15,735 imp, 0.3% CTR | ✅ Fixed: added hero + breadcrumbs + FAQ schema (Sep 2026) |
| `/guides/upsc-cms-complete-guide` | 9,992 imp, 0.4% CTR | ⏳ Next: add structured data + refresh content |
| `/neet-pg/vs-usmle` | 2,495 imp, 0% CTR | ✅ Fixed: added hero + breadcrumbs + FAQ schema (Sep 2026) |
| `/cms/cutoff/2024` | 2,685 imp, 0.5% CTR | ⏳ Add FAQ schema + internal links |
| `/guides/medical-officer-jobs` | 1,511 imp, 0.2% CTR | ⏳ Add year + "Free" to title |

---

## NEW PAGES CREATED (Sep 2026)
| Page | Target Keywords | Impressions |
|------|----------------|-------------|
| `/cms/salary` | `upsc cms salary`, `admo salary`, `medical officer salary` | 150+ |
| `/cms/exam-pattern` | `upsc cms exam pattern`, `upsc cms marking`, `cms exam pattern` | 139+ |
| `/neet-pg/vs-upsc-cms` | `neet pg vs upsc cms`, `which is tough` | 141+ |

All added to sitemap.ts with priority 0.85.

---

## INTERNAL LINK GRAPH (current state)
**Hubs with cross-links:**
- `/cms` → `/cms/cutoff/2026`, `/cms/exam-pattern`, `/cms/salary`, `/cms/vs-neet-pg`
- `/neet-pg` → `/neet-pg/vs-usmle`, `/neet-pg/vs-upsc-cms`, `/guides/neet-pg-complete-guide`, `/guides/study-plan-builder`
- `/usmle` → `/neet-pg/vs-usmle`, `/neet-pg`, `/guides/usmle-step-1-guide`
- `/medical-officer` → `/cms/salary`, `/cms`, `/government-doctor-jobs`

**Still needs cross-links:**
- `/cms/vs-neet-pg` → link to `/neet-pg/vs-upsc-cms` (reverse perspective)
- `/guides/upsc-cms-complete-guide` → link to `/cms/salary`, `/cms/exam-pattern`
- `/guides/neet-pg-complete-guide` → link to `/neet-pg/vs-upsc-cms`
- `/government-doctor-jobs` → link to `/cms/salary`, `/medical-officer`

---

## COMPARISON PAGES (high commercial intent)
| Page | Status | Impressions | CTR |
|------|--------|-------------|-----|
| `/cms/vs-neet-pg` | ✅ Live + enhanced | 15,735 | 0.3% |
| `/cms/vs-ini-cet` | ✅ Live | — | — |
| `/neet-pg/vs-usmle` | ✅ Live + enhanced | 2,495 | 0% |
| `/neet-pg/vs-upsc-cms` | ✅ New (Sep 2026) | 0 (new) | — |
| `/fmge/vs-next` | ✅ Live | 229 | 0% |

**Next:** Add `/neet-pg/vs-ini-cet` (141 imp at pos 7.21, no dedicated page).

---

## MISSING HIGH-VALUE PAGES (rank #1 priority)
| Page | Keywords | Impressions | Effort |
|------|----------|-------------|--------|
| `/cms/salary` | `upsc cms salary`, `admo salary` | 150+ | ✅ Built (Sep 2026) |
| `/cms/exam-pattern` | `upsc cms exam pattern`, `cms marking` | 139+ | ✅ Built (Sep 2026) |
| `/neet-pg/vs-upsc-cms` | `neet pg vs upsc cms` | 141+ | ✅ Built (Sep 2026) |
| `/neet-pg/vs-ini-cet` | `neet pg vs ini cet` | 141+ | ⏳ Next |
| `/cms/result-2026` | `upsc cms result 2026`, `upsc cms result date` | 155+ | ⏳ When results approach |
| `/cms/syllabus` | `upsc cms syllabus`, `upsc cms subjects` | 170+ | ⏳ Medium priority |

---

## TOOLS OPPORTUNITIES (rank by repeat use + search intent)
| Tool | Target Query | Impressions | Effort | Priority |
|------|-------------|-------------|--------|----------|
| UPSC CMS Salary Calculator | `upsc cms salary calculator` | ~50 | Medium | HIGH |
| NEET PG Rank Predictor | `neet pg rank predictor` | ~30 | High | MEDIUM |
| UPSC CMS Eligibility Checker | `upsc cms eligibility` | ~200 | Low | HIGH |
| Exam Countdown Widget | `upsc cms exam date 2026` | ~100 | Low | HIGH |
| Study Time Calculator | `upsc cms preparation time` | ~40 | Low | MEDIUM |

**Decision:** Build eligibility checker + countdown widget first (low effort, high intent match).

---

## MONETIZATION (current state + opportunities)
**Active:**
- Razorpay subscription (₹49/month, ₹99/6 months)
- Subscription page at `/subscription`

**Opportunities (not yet implemented):**
1. **AdSense** — Add to high-traffic pages (homepage, CMS landing, comparison pages). Requires AdSense approval.
2. **Affiliate books** — Amazon Associates links on book pages (`/cms/books/*`, guide pages). Commission ~4%.
3. **Premium tools** — Salary calculator with personalised report (₹29 one-time).
4. **Lead gen** — "Download UPSC CMS 2026 Notification PDF" in exchange for email.
5. **B2B** — Offer question bank licensing to coaching institutes.

**Decision:** Do NOT force monetization. Add affiliate book links to guide pages first (low friction, high intent).

---

## SEASONAL / EXAM-CYCLE CALENDAR
| Exam | Typical Months | Content Priority |
|------|---------------|------------------|
| UPSC CMS | Notification: Mar · Exam: Jul-Aug · Result: Oct-Nov | Cutoff, pattern, result pages |
| NEET PG | Notification: Feb · Exam: Jun · Result: Aug | Rank predictor, cutoff, result |
| INI-CET | Jan + Jul sessions | Comparison, guide updates |
| FMGE | Jun + Dec | FMGE vs NEXT page refresh |
| USMLE Step 1 | Year-round (but peak: Dec-Mar) | Guide + First Aid updates |

**Next cycle (Q4 2026):** UPSC CMS result → create `/cms/result-2026` page in October.

---

## TECHNICAL SEO AUDIT (Sep 2026)
✅ Sitemap updated with new pages
✅ Structured data (FAQPage, Article, MedicalWebPage) on major pages
✅ HreflangAlternates component added
✅ llms.txt + robots.ai crawler whitelist
✅ Canonical URLs on all new pages
✅ Mobile-first responsive design
✅ Internal link graph overhauled

⏳ Pending:
- `/cms/cutoff` (generic) should 301 to `/cms/cutoff/2026` (41 impressions lost)
- Fix `/blog/cms-vs-neet-pg-vs-inicet` typo variant → canonical to `/blog/cms-vs-neet-pg-vs-ini-cet`
- Add breadcrumbs to remaining pages without them
- Image alt tags audit (many missing)
- Core Web Vitals: mobile LCP audit needed

---

## WEEKLY OPERATING MODE
1. Check GSC for new/queries + ranking movement
2. Identify pages that dropped in position
3. Fix CTR on high-impression pages (title/meta tweaks)
4. Add 1-2 internal links from high-authority pages to new/rising pages
5. Refresh 1-2 pages with stale content (add date, update numbers)
6. Build 1 tool OR 1 missing page if evidence supports it
7. Verify build passes + no console errors

---

## MONTHLY OPERATING MODE
1. Full GSC audit (impressions, clicks, CTR, position changes)
2. Revisit comparison pages — update stats/salary figures
3. Add 1-2 new missing pages from search query gap analysis
4. Internal link audit — ensure every hub links to new content
5. Sitemap refresh
6. Competitor gap analysis (what are they ranking for that we're not?)
7. Monetization review (AdSense, affiliate, tools)

---

## QUARTERLY STRATEGIC RESET
1. What produced the most traffic/clicks this quarter?
2. Which pages declined? Why?
3. Which tools got repeat use?
4. Which monetization channels showed promise?
5. What new exam cycle is approaching?
6. What should we STOP doing?
7. What should we SCALE?

---

## ACTIVE CLUSTERS
1. **UPSC CMS cluster** — strongest cluster. Landing → cutoff → salary → exam-pattern → comparison → subject pages → PYQs → guide.
2. **NEET PG cluster** — growing. Landing → vs-usmle → vs-upsc-cms → guide → study-plan → PYQs.
3. **Medical Officer cluster** — stable. Landing → salary → government-doctor-jobs → CMS.
4. **Comparison cluster** — high CTR potential. 5 comparison pages, all cross-linked.
5. **Salary/Career cluster** — new (Sep 2026). `/cms/salary` → `/medical-officer` → `/government-doctor-jobs`.

---

## NEXT PRIORITIES (ordered)
1. **Add `/neet-pg/vs-ini-cet`** comparison page (141 imp, pos 7.21, no page)
2. **Fix `/cms/cutoff` → 301 to `/cms/cutoff/2026`** (41 imp wasted)
3. **Add FAQ schema to `/guides/upsc-cms-complete-guide`** (9,992 imp, 0.4% CTR)
4. **Build eligibility checker tool** (200+ imp, low effort)
5. **Add breadcrumbs + internal links to remaining pages**
6. **Mobile Core Web Vitals audit** (75% mobile traffic)
7. **Add affiliate book links to guide pages** (monetization)
8. **Create `/cms/result-2026`** (when UPSC CMS results drop, ~Oct 2026)
9. **Add `/neet-pg/vs-ini-cet`** comparison (when INI-CET data available)
10. **Build UPSC CMS salary calculator** (premium tool, ₹29 one-time)

---

## REJECTED IDEAS (why)
- **Mass blog posting (1/week quota):** Not useful without search intent validation. Quality > quantity.
- **Generic tools (flashcards, timers):** Users already have these. No differentiation.
- **Hindi translations:** Low ROI — English queries dominate GSC (India traffic is English-speaking medical aspirants).
- **Course platform / LMS:** Too heavy. CrackCMS is a prep platform, not an edtech company.
- **Social media automation:** No evidence users come from social. Organic search is the engine.

---

*This document is updated after each execution cycle. It should help the next run understand the project without rereading the full history.*
