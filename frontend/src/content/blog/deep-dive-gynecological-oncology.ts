import type { BlogPost } from '@/lib/blog';

const post: BlogPost = {
    slug: 'deep-dive-gynecological-oncology',
    title: 'Gynaecological Oncology: HPV, Cervical Cancer Screening and FIGO Staging (CMS/NEET PG)',
    description: 'Gynaecological oncology for UPSC CMS and NEET PG — HPV pathogenesis, cervical cancer screening protocols, FIGO staging, and management algorithms.',
    excerpt: 'Gynaecological oncology guide for UPSC CMS and NEET PG — HPV and cervical cancer, FIGO staging, screening protocols, and management algorithms.',
    coverImage: '/blog/og/gynae-oncology-deep-dive-cover.png',
    category: 'Clinical Concepts',
    subcategory: 'OBG',
    tags: ['Gynae Oncology', 'HPV', 'Cervical Cancer', 'FIGO', 'OBG', 'UPSC CMS', 'NEET PG'],
    difficulty: 'advanced',
    authorId: 'dr-aarav-mehta',
    reviewedBy: 'dr-aarav-mehta',
    author: 'Dr. Aarav Mehta, MBBS, MD (Internal Medicine)',
    authorRole: 'Senior Editor — Medicine, CrackCMS',
    datePublished: '2026-09-19',
    dateModified: '2026-09-19',
    updatedAt: '2026-09-19',
    readingTime: '11 min',
    wordCount: 3400,
    primaryCta: { label: 'Practice OBG PYQs (free)', href: '/questions?topic=obg' },
    relatedExamPaths: ['/cms', '/neet-pg'],
    faqs: [
        { q: 'What is the most common cause of cervical cancer?', a: 'HPV infection, particularly types 16 and 18, causes ~70% of cervical cancers. HPV 16 accounts for ~50% and HPV 18 for ~20% of cases.' },
        { q: 'What is the recommended cervical cancer screening age?', a: 'Start screening at age 25 (or within 3 years of sexual activity). Every 3 years with cytology alone, or every 5 years with co-testing (cytology + HPV).' },
        { q: 'What is FIGO stage IB2?', a: 'Clinically visible lesion >4cm but limited to cervix. Treatment: Chemoradiation (preferred) or radical hysterectomy if tumor <4cm.' },
    ],
    toc: [
        { id: 'hpv-pathogenesis', label: 'HPV Pathogenesis' },
        { id: 'screening', label: 'Screening Protocols' },
        { id: 'figo-staging', label: 'FIGO Staging System' },
        { id: 'management', label: 'Management by Stage' },
        { id: 'vaccination', label: 'HPV Vaccination' },
    ],
    references: [
        { label: 'WHO Cervical Cancer Screening Guidelines', url: 'https://www.who.int/publications' },
        { label: 'FIGO Staging for Gynaecological Cancers', url: 'https://www.figo.org' },
    ],
    revisionLog: [{ date: '2026-09-19', note: 'Initial publication' }],
    body: `## HPV Pathogenesis

HPV types 16 and 18 are responsible for ~70% of cervical cancers. The virus integrates into host DNA, producing E6 and E7 oncoproteins that inactivate p53 and Rb tumor suppressors.

## Screening Protocols

- Start: Age 25 (or 3 years after sexual debut)
- Method: HPV DNA testing (preferred), cytology, or co-testing
- Frequency: Every 5-10 years (HPV), every 3 years (cytology)

## FIGO Staging System

Stage I: Confined to cervix. Stage II: Beyond uterus but not to pelvic wall. Stage III: Pelvic wall or lower third vagina. Stage IV: Beyond true pelvis or involving bladder/rectum mucosa.

## Management by Stage

Stage IA1: Cone biopsy. Stage IA2-IB1: Radical hysterectomy or RT. Stage IB2-IVA: Chemoradiation (cisplatin-based).

## HPV Vaccination

Cervarix (bivalent) and Gardasil (quadrivalent/9-valent). Recommended at ages 9-14, catch-up up to age 26.`,
    prelude: undefined,
    outro: undefined,
    pinned: false,
    trending: false,
};

export default post;
