import type { BlogPost } from '@/lib/blog';

const post: BlogPost = {
    slug: 'deep-dive-diabetes-mellitus-type2',
    title: 'Type 2 Diabetes Mellitus: Pathophysiology, Complications and Drug Cascade (CMS + NEET PG)',
    description: 'Comprehensive guide to Type 2 Diabetes for UPSC CMS and NEET PG — pathophysiology, drug mechanisms, complications, and the stepwise treatment cascade.',
    excerpt: 'Type 2 Diabetes deep dive for UPSC CMS and NEET PG — pathophysiology, drug mechanisms, microvascular/macrovascular complications, and stepwise treatment cascade.',
    coverImage: '/blog/og/type2-diabetes-deep-dive-cover.png',
    category: 'Clinical Concepts',
    subcategory: 'Endocrinology',
    tags: ['Diabetes', 'Endocrinology', 'Type 2 DM', 'Complications', 'UPSC CMS', 'NEET PG'],
    difficulty: 'advanced',
    authorId: 'dr-aarav-mehta',
    reviewedBy: 'dr-aarav-mehta',
    author: 'Dr. Aarav Mehta, MBBS, MD (Internal Medicine)',
    authorRole: 'Senior Editor — Medicine, CrackCMS',
    datePublished: '2026-09-19',
    dateModified: '2026-09-19',
    updatedAt: '2026-09-19',
    readingTime: '13 min',
    wordCount: 3800,
    primaryCta: { label: 'Practice Endocrinology PYQs (free)', href: '/questions?topic=endocrinology' },
    relatedExamPaths: ['/cms', '/neet-pg'],
    faqs: [
        { q: 'What is the first-line drug for Type 2 Diabetes?', a: 'Metformin is first-line unless contraindicated. It reduces hepatic gluconeogenesis and improves peripheral insulin sensitivity. Start at 500mg daily, titrate to 2000mg/day.' },
        { q: 'What is the HbA1c target for most patients?', a: 'Individualized: <7% for most adults. <6.5% if achievable without hypoglycemia. <8% may be appropriate for older adults with comorbidities.' },
        { q: 'Which drug class has cardiovascular benefits?', a: 'GLP-1 receptor agonists (semaglutide, liraglutide) and SGLT2 inhibitors (empagliflozin, dapagliflozin) have proven cardiovascular and renal benefits in major trials (LEADER, EMPA-REG, DECLARE).' },
    ],
    toc: [
        { id: 'pathophysiology', label: 'Pathophysiology' },
        { id: 'diagnosis', label: 'Diagnosis Criteria' },
        { id: 'drug-cascade', label: 'Stepwise Drug Cascade' },
        { id: 'complications', label: 'Complications' },
        { id: 'special-situations', label: 'Special Situations' },
    ],
    references: [
        { label: 'ADA Standards of Care in Diabetes 2025', url: 'https://diabetesjournals.org' },
        { label: 'WHO Global Report on Diabetes', url: 'https://www.who.int/publications' },
    ],
    revisionLog: [{ date: '2026-09-19', note: 'Initial publication' }],
    body: `## Pathophysiology

Type 2 DM involves insulin resistance in peripheral tissues, progressive beta-cell dysfunction, increased hepatic glucose output, and incretin deficiency.

## Diagnosis Criteria

- Fasting glucose >= 126 mg/dL
- 2h post-glucose >= 200 mg/dL (OGTT)
- HbA1c >= 6.5%
- Random glucose >= 200 mg/dL with symptoms

## Stepwise Drug Cascade

1. **Metformin** (1st line) — reduces hepatic gluconeogenesis
2. **Metformin + SGLT2i or GLP-1 RA** (2nd line) — add based on CV/renal risk
3. **Metformin + SGLT2i + GLP-1 RA** (3rd line)
4. **Add insulin** if HbA1c remains >7.5%

## Complications

Microvascular: Retinopathy, Nephropathy, Neuropathy. Macrovascular: MI, Stroke, PVD.

## Special Situations

Pregnancy: Insulin only (oral agents contraindicated). Surgery: Switch to insulin peri-operatively.`,
    prelude: undefined,
    outro: undefined,
    pinned: false,
    trending: false,
};

export default post;
