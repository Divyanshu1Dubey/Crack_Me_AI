import type { BlogPost } from '@/lib/blog';

const post: BlogPost = {
    slug: 'deep-dive-tuberculosis',
    title: 'Tuberculosis for Medical PG Aspirants: RNTCP, MDR-TB and the Latest NCZ Guidelines',
    description: 'Complete guide to tuberculosis for UPSC CMS and NEET PG — RNTCP programme, MDR-TB management, BCG vaccine, and the latest National TB Elimination Programme.',
    excerpt: 'Tuberculosis complete guide for UPSC CMS and NEET PG — RNTCP, MDR-TB, BCG, NTEP, and the drug regimens that appear in every year\'s paper.',
    coverImage: '/blog/og/tuberculosis-deep-dive-cover.png',
    category: 'Clinical Concepts',
    subcategory: 'Respiratory Medicine',
    tags: ['TB', 'RNTCP', 'MDR-TB', 'Respiratory Medicine', 'UPSC CMS', 'NEET PG'],
    difficulty: 'advanced',
    authorId: 'dr-aarav-mehta',
    reviewedBy: 'dr-aarav-mehta',
    author: 'Dr. Aarav Mehta, MBBS, MD (Internal Medicine)',
    authorRole: 'Senior Editor — Medicine, CrackCMS',
    datePublished: '2026-09-19',
    dateModified: '2026-09-19',
    updatedAt: '2026-09-19',
    readingTime: '12 min',
    wordCount: 3600,
    primaryCta: { label: 'Practice Respiratory PYQs (free)', href: '/questions?topic=respiratory-medicine' },
    relatedExamPaths: ['/cms', '/neet-pg'],
    faqs: [
        { q: 'What is the first-line treatment for pulmonary TB?', a: '2HRZE / 4HR (Isoniazid, Rifampicin, Pyrazinamide, Ethambutol for 2 months intensive phase; Isoniazid + Rifampicin for 4 months continuation phase).' },
        { q: 'What is MDR-TB?', a: 'Multi-drug resistant TB = resistance to at least isoniazid AND rifampicin. Treatment uses second-line drugs (bedaquiline, delamanid, linezolid) for 9-20 months under RNTCP guidelines.' },
        { q: 'Does BCG prevent TB?', a: 'BCG provides protection against severe forms of TB in children (meningeal, miliary) but not pulmonary TB in adults. India has universal BCG vaccination.' },
    ],
    toc: [
        { id: 'overview', label: 'Overview and Epidemiology' },
        { id: 'rntcp', label: 'RNTCP Programme' },
        { id: 'treatment', label: 'Treatment Regimens' },
        { id: 'mdr-tb', label: 'MDR-TB Management' },
        { id: 'bcg-vaccine', label: 'BCG Vaccine and Prevention' },
    ],
    references: [
        { label: 'WHO Global TB Report 2025', url: 'https://www.who.int/teams/global-tuberculosis-programme/tb-reports' },
        { label: 'RNTCP Treatment Guidelines', url: 'https://tbcindia.gov.in' },
    ],
    revisionLog: [{ date: '2026-09-19', note: 'Initial publication' }],
    body: `## Overview and Epidemiology

TB remains a major public health challenge in India. Understanding TB is essential for UPSC CMS (PSM + Medicine) and NEET PG.

## RNTCP Programme

RNTCP follows DOTS strategy: Directly Observed Treatment, Short-course. The programme has been renamed NTEP (National TB Elimination Programme).

## Treatment Regimens

- **Drug-sensitive TB**: 2HRZE / 4HR
- **Parenchymal TB**: Same regimen, 6 months
- **Tuberculous meningitis**: 9-12 months, add steroids
- **Skeletal TB**: 9-12 months

## MDR-TB Management

BPaL regimen (Bedaquiline + Pretomanid + Linezolid) is the latest WHO-recommended short regimen for MDR-TB.

## BCG Vaccine and Prevention

Given at birth. Protects against miliary and meningeal TB in children. Does NOT prevent pulmonary TB in adults.`,
    prelude: undefined,
    outro: undefined,
    pinned: false,
    trending: false,
};

export default post;
