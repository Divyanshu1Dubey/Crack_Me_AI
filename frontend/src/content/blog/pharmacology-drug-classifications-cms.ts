import type { BlogPost } from '@/lib/blog';

const post: BlogPost = {
    slug: 'pharmacology-drug-classifications-cms',
    title: 'Pharmacology Drug Classifications for UPSC CMS: The Chart Every Candidate Needs',
    description: 'Complete pharmacology drug classification chart for UPSC CMS and NEET PG — every drug class, examples, mechanism, clinical use and side effects in one reference.',
    excerpt: 'Pharmacology drug classifications for UPSC CMS and NEET PG — a complete chart covering every drug class, mechanism, use, and adverse effects.',
    coverImage: '/blog/og/pharmacology-classifications-cover.png',
    category: 'Subject Prep',
    subcategory: 'Pharmacology',
    tags: ['Pharmacology', 'Drug Classification', 'UPSC CMS', 'NEET PG', 'KD Tripathi'],
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
    primaryCta: { label: 'Practice Pharmacology PYQs (free)', href: '/questions?topic=pharmacology' },
    relatedExamPaths: ['/cms', '/neet-pg'],
    faqs: [
        { q: 'Which pharmacology textbook is best for UPSC CMS?', a: 'KD Tripathi Essentials of Medical Pharmacology is the standard for Indian exams. Katzung Basic and Clinical Pharmacology is more comprehensive. For quick reference: Rang and Dales Pharmacology.' },
        { q: 'How are drug classifications tested in UPSC CMS?', a: 'Direct drug-class matching questions, mechanism of action identification, choosing the right drug for a clinical scenario, and adverse effect identification.' },
        { q: 'What drug doses are asked in UPSC CMS?', a: 'Specific drug doses appear occasionally — particularly for emergency drugs (atropine, adrenaline, adenosine), antibiotics, and chemotherapy agents. Focus on commonly used drugs.' },
    ],
    toc: [
        { id: 'ans-cns', label: 'ANS and CNS Drugs' },
        { id: 'cardiovascular', label: 'Cardiovascular Drugs' },
        { id: 'diuretics', label: 'Diuretics' },
        { id: 'antibiotics', label: 'Antibiotics' },
        { id: 'anticancer', label: 'Anticancer Drugs' },
    ],
    references: [
        { label: 'KD Tripathi Essentials of Medical Pharmacology', url: 'https://www.jaypeedigital.com' },
    ],
    revisionLog: [{ date: '2026-09-19', note: 'Initial publication' }],
    body: `## ANS and CNS Drugs

**ANS:** Receptors (alpha1, alpha2, beta1, beta2, M1-M5). Drugs: Atropine (M blocker), Propranolol (non-selective beta blocker), Prazosin (alpha1 blocker).

**CNS:** Local anaesthetics (Lignocaine, Bupivacaine), General anaesthetics, Sedative-hypnotics (Benzodiazepines), Antiepileptics (Phenytoin, Carbamazepine, Valproate, Levetiracetam).

## Cardiovascular Drugs

Antiarrhythmics (Classes I-IV), Antihypertensives (ACE-I, ARB, CCB, Beta-blockers, Diuretics), Anti-anginals (Nitrates, Beta-blockers, CCB), Anticoagulants (Heparin, Warfarin, DOACs).

## Diuretics

Loop (Furosemide), Thiazide (Hydrochlorothiazide), Potassium-sparing (Spironolactone, Amiloride), Osmotic (Mannitol), Carbonic anhydrase inhibitors (Acetazolamide).

## Antibiotics

Beta-lactams (Penicillins, Cephalosporins, Carbapenems), Aminoglycosides, Tetracyclines, Macrolides, Fluoroquinolones, Sulfonamides, Antitubercular.

## Anticancer Drugs

Alkylating agents, Antimetabolites, Plant alkaloids, Antibiotics (doxorubicin), Targeted therapy. Know mechanisms and major adverse effects.`,
    prelude: undefined,
    outro: undefined,
    pinned: false,
    trending: false,
};

export default post;
