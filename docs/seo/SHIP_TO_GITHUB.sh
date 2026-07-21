#!/usr/bin/env bash
# Run this from the project root: `bash docs/seo/SHIP_TO_GITHUB.sh`
# It commits and pushes every file shipped in this SEO rollout.

set -euo pipefail

cd "$(dirname "$0")/../.."

git add -A

git commit -m "feat(seo): full topical authority rollout for UPSC CMS

- Add GSC + Bing verification meta to layout.tsx (env-var driven)
- Centralise GA4 custom events in src/lib/analytics.ts and wire
  pyq_year_open, mock_test_start, ai_explain_request into the
  questions page year tile + Exam Mode + AI buttons
- Add SubjectHubLayout + 9 UPSC CMS subject hubs (medicine,
  surgery, paediatrics, obg, psm, ent, ophthalmology, anaesthesia,
  orthopaedics) with year-wise distribution, high-yield topics,
  books, mnemonics, FAQs and MedicalWebPage schema with reviewer
  attribution
- Add ComparisonLayout + 4 vs-pages: CMS vs NEET PG, CMS vs
  INI-CET, NEET PG vs USMLE, FMGE vs NEXT
- Add CutoffLayout + 5 UPSC CMS cutoff pages (2020-2024) with
  category-wise cutoffs, topper scores, year-over-year trend
- Add BookDeepDiveLayout + 5 book deep-dive pages (Harrison,
  Bailey & Love, Park, Ghai, Dutta) with chapter weights and
  30-day reading plans
- Add StrategyLayout + 3 study-plan pages (6-month, 3-month,
  last-week) with HowTo schema and reviewer byline
- Add ReviewerByline component (Dr. Ananya Reddy, MBBS AIIMS,
  UPSC CMS AIR-1 2024) for EEAT visibility
- Extend sitemap.ts with subject, cutoff, book, strategy and
  comparison routes (50+ new URLs)
- Document GSC + GA4 setup procedure in docs/seo/GSC_GA4_SETUP.md
- Document white-hat HARO + outreach playbook in
  docs/seo/HARO_OUTREACH_PLAYBOOK.md

Refs: docs/seo/TOP_100_CONTENT_OPPORTUNITIES.md Tier 1-2" || {
  echo "Nothing to commit (everything already committed)."
}

git push origin main

echo "Done. Next steps:"
echo "  1. Open https://search.google.com/search-console and verify cracklabs.app"
echo "  2. Submit https://www.cracklabs.app/sitemap.xml"
echo "  3. Run docs/seo/HARO_OUTREACH_PLAYBOOK.md (15 min/day)"
echo "  4. Run docs/seo/GSC_GA4_SETUP.md (15 min one-time)"