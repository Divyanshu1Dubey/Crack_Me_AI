import type { BlogPost} from '@/lib/blog';

const post: BlogPost = {
    slug: 'psm-biostatistics-formulas-upsc-cms',
    title: 'PSM Biostatistics Formulas for UPSC CMS: The Complete Reference With Solved PYQs',
    description: 'PSM biostatistics formulas for UPSC CMS and NEET PG — sensitivity, specificity, PPV, NPV, relative risk, odds ratio, Chi-square, t-test with PYQ examples.',
    excerpt: 'PSM biostatistics formulas for UPSC CMS — sensitivity, specificity, RR, OR, Chi-square, t-test with solved PYQ examples and formula cheat sheet.',
    coverImage: '/blog/og/biostatistics-formulas-cover.png',
    category: 'Subject Prep',
    subcategory: 'PSM',
    tags: ['PSM', 'Biostatistics', 'Formulas', 'Sensitivity', 'Specificity', 'UPSC CMS'],
    difficulty: 'intermediate',
    authorId: 'dr-aarav-mehta',
    reviewedBy: 'dr-aarav-mehta',
    author: 'Dr. Aarav Mehta, MBBS, MD (Internal Medicine)',
    authorRole: 'Senior Editor - Medicine, CrackCMS',
    datePublished: '2026-09-20',
    dateModified: '2026-09-20',
    updatedAt: '2026-09-20',
    readingTime: '9 min',
    wordCount: 2700,
    primaryCta: { label: 'Practice PSM PYQs (free)', href: '/questions?topic=psm' },
    relatedExamPaths: ['/cms', '/neet-pg'],
    faqs: [],
    toc: [],
    references: [],
    revisionLog: [{ date: '2026-09-20', note: 'Initial publication' }],
    body: `## Key Formulas

**Sensitivity** = TP / (TP + FN)
**Specificity** = TN / (TN + FP)
**PPV** = TP / (TP + FP)
**NPV** = TN / (TN + FN)

**Relative Risk (RR)** = [a/(a+b)] / [c/(c+d)] — incidence in exposed vs unexposed
**Odds Ratio (OR)** = (a x d) / (b x c) — odds of exposure in cases vs controls

**Chi-square** = sum((O-E)2/E) — test of independence
**t-test** = (Mean1 - Mean2) / SE — compare two means`,
    prelude: undefined,
    outro: undefined,
    pinned: false,
    trending: false,
};

export default post;
