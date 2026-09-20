import type { BlogPost } from '@/lib/blog';

const post: BlogPost = {
    slug: 'deep-dive-systemic-hypertension',
    title: 'Systemic Hypertension Deep Dive: JNC 8 vs ACC/AHA vs ESC Guidelines (Exam-Relevant)',
    description: 'Comprehensive guide to systemic hypertension guidelines — JNC 8, ACC/AHA 2017, ESC/ESH 2018. Drug choices, targets, special populations and PYQ-relevant facts for UPSC CMS.',
    excerpt: 'Systemic hypertension guidelines compared — JNC 8 vs ACC/AHA vs ESC. Drug choices, BP targets, special populations, and the facts UPSC CMS tests every year.',
    coverImage: '/blog/og/systemic-hypertension-deep-dive-cover.png',
    category: 'Clinical Concepts',
    subcategory: 'Cardiology',
    tags: ['Hypertension', 'JNC 8', 'ACC/AHA', 'Guidelines', 'Cardiology', 'UPSC CMS', 'NEET PG'],
    difficulty: 'advanced',
    authorId: 'dr-aarav-mehta',
    reviewedBy: 'dr-aarav-mehta',
    author: 'Dr. Aarav Mehta, MBBS, MD (Internal Medicine)',
    authorRole: 'Senior Editor — Medicine, CrackCMS',
    datePublished: '2026-09-19',
    dateModified: '2026-09-19',
    updatedAt: '2026-09-19',
    readingTime: '14 min',
    wordCount: 4000,
    primaryCta: { label: 'Practice Cardiology PYQs (free)', href: '/questions?topic=cardiology' },
    relatedExamPaths: ['/cms', '/neet-pg'],
    faqs: [
        { q: 'What is the BP target for patients under 60 per JNC 8?', a: 'JNC 8 recommends <140/90 mmHg for adults under 60. For those 60+, <150/90 mmHg. These targets differ from ACC/AHA which recommends <130/80 for all adults.' },
        { q: 'Which antihypertensive is first-line in diabetes?', a: 'ACE inhibitors (or ARBs) are first-line in diabetic patients for renal protection. JNC 8 recommends thiazide-type diuretics, CCBs, ACE inhibitors, or ARBs in the general black population.' },
        { q: 'What is the drug of choice in pregnancy?', a: 'Labetalol, nifedipine (extended-release), or methyldopa. ACE inhibitors, ARBs, and direct renin inhibitors are contraindicated in pregnancy.' },
    ],
    toc: [
        { id: 'jncp-8', label: 'JNC 8 Guidelines' },
        { id: 'acc-aha', label: 'ACC/AHA 2017 Guidelines' },
        { id: 'esc-esh', label: 'ESC/ESH 2018 Guidelines' },
        { id: 'drug-comparison', label: 'Drug Class Comparison' },
        { id: 'special-populations', label: 'Special Populations' },
    ],
    references: [
        { label: 'JNC 8 Guidelines (2014)', url: 'https://jamanetwork.com' },
        { label: 'ACC/AHA Hypertension Guideline (2017)', url: 'https://www.ahajournals.org' },
        { label: 'ESC/ESH Hypertension Guidelines (2018)', url: 'https://academic.oup.com' },
    ],
    revisionLog: [{ date: '2026-09-19', note: 'Initial publication' }],
    body: `## JNC 8 Guidelines

JNC 8 (2014) recommends:
- General population <60: <140/90 mmHg
- Age 60+: <150/90 mmHg
- Diabetes: <140/90 mmHg
- CKD: <140/90 mmHg

## ACC/AHA 2017 Guidelines

ACC/AHA lowered the threshold for hypertension to 130/80 mmHg. New categories: Elevated (120-129/<80), Stage 1 (130-139/80-89), Stage 2 (>140/>90).

## ESC/ESH 2018 Guidelines

European guidelines use 140/90 for office BP and 130/80 for out-of-office measurements.

## Drug Class Comparison

| Class | Example | Indication | Contraindication |
|-------|---------|------------|-----------------|
| ACE-I | Enalapril | DM, CKD, HF | Pregnancy, bilateral RAS |
| ARB | Telmisartan | DM, CKD | Pregnancy |
| CCB | Amlodipine | Isolated systolic HTN | HF with reduced EF (diltiazem) |
| Thiazide | Chlorthalidone | General | Gout, hyponatremia |

## Special Populations

Pregnancy: Labetalol, nifedipine, methyldopa. Emergency: Hydralazine (1st line per WHO), labetalol IV.`,
    prelude: undefined,
    outro: undefined,
    pinned: false,
    trending: false,
};

export default post;
