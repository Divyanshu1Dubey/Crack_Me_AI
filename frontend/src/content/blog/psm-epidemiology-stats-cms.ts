import type { BlogPost } from '@/lib/blog';

const post: BlogPost = {
    slug: 'psm-epidemiology-stats-cms',
    title: 'PSM Epidemiology and Biostatistics for UPSC CMS: Park + NHK Made Simple',
    description: 'PSM Epidemiology and Biostatistics for UPSC CMS — Park Textbook, National Health Programs, biostatistics formulas, and the PYQ patterns that appear consistently.',
    excerpt: 'PSM Epidemiology and Biostatistics for UPSC CMS — Park Textbook summaries, NHK facts, National Health Programs, and biostatistics formulas simplified.',
    coverImage: '/blog/og/psm-epidemiology-cover.png',
    category: 'Subject Prep',
    subcategory: 'PSM',
    tags: ['PSM', 'Epidemiology', 'Biostatistics', 'Park', 'NHK', 'UPSC CMS', 'NEET PG'],
    difficulty: 'intermediate',
    authorId: 'dr-aarav-mehta',
    reviewedBy: 'dr-aarav-mehta',
    author: 'Dr. Aarav Mehta, MBBS, MD (Internal Medicine)',
    authorRole: 'Senior Editor — Medicine, CrackCMS',
    datePublished: '2026-09-19',
    dateModified: '2026-09-19',
    updatedAt: '2026-09-19',
    readingTime: '10 min',
    wordCount: 3000,
    primaryCta: { label: 'Practice PSM PYQs (free)', href: '/questions?topic=psm' },
    relatedExamPaths: ['/cms', '/neet-pg'],
    faqs: [
        { q: 'Which PSM textbook is best for UPSC CMS?', a: 'Park Textbook of Preventive and Social Medicine is the standard. For National Health Programs: use the latest NHM guidelines from mohfw.gov.in. For statistics: refer to any biostatistics chapter in Park or Mahajan.' },
        { q: 'How are National Health Programs tested?', a: 'Direct questions about program targets (e.g., TB elimination target year, immunization coverage under UIP), components, implementing agencies, and recent updates (Mission Ayushman Bharat, PMJAY).' },
        { q: 'What biostatistics formulas must I know?', a: 'Measures of central tendency (mean, median, mode), standard deviation, standard error, Chi-square test, t-test, relative risk, odds ratio, sensitivity, specificity, PPV, NPV. Know the formulas and their clinical applications.' },
    ],
    toc: [
        { id: 'epidemiology-basics', label: 'Epidemiology Basics' },
        { id: 'study-designs', label: 'Study Designs' },
        { id: 'biostatistics', label: 'Biostatistics Formulas' },
        { id: 'national-health-programs', label: 'National Health Programs' },
    ],
    references: [
        { label: 'Park Textbook of Preventive and Social Medicine', url: 'https://www.cbsedigital.in' },
        { label: 'Ministry of Health and Family Welfare', url: 'https://mohfw.gov.in' },
    ],
    revisionLog: [{ date: '2026-09-19', note: 'Initial publication' }],
    body: `## Epidemiology Basics

Study of distribution and determinants of health-related states. Measures: incidence, prevalence, morbidity, mortality, DALY, QALY.

## Study Designs

- **Observational:** Descriptive (case reports, cross-sectional), Analytical (case-control, cohort)
- **Experimental:** RCT (gold standard), field trial, community trial

## Biostatistics Formulas

**Sensitivity** = TP / (TP + FN) — ability to detect disease when present
**Specificity** = TN / (TN + FP) — ability to exclude disease when absent
**PPV** = TP / (TP + FP) — probability of disease given positive test
**NPV** = TN / (TN + FN) — probability of no disease given negative test

## National Health Programs

| Program | Target | Year |
|---------|--------|------|
| TB Elimination | Zero deaths | 2025 |
| Kala-azar Elimination | Zero cases | 2024 |
| Maternal Mortality | <70/100K live births | 2030 |
| IMR | <25/1000 live births | 2030 |`,
    prelude: undefined,
    outro: undefined,
    pinned: false,
    trending: false,
};

export default post;
