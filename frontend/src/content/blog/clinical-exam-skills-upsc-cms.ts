import type { BlogPost } from '@/lib/blog';

const post: BlogPost = {
    slug: 'clinical-exam-skills-upsc-cms',
    title: 'Clinical Examination Skills for UPSC CMS: CVS, RS, CNS and Abdominal Exam Checklists',
    description: 'Clinical examination checklists for UPSC CMS — CVS, RS, CNS and abdominal examination steps, what to look for, and the clinical signs tested in exams.',
    excerpt: 'Clinical examination checklists for UPSC CMS — CVS, RS, CNS and abdominal exam steps, key signs to identify, and how they appear in exam questions.',
    coverImage: '/blog/og/clinical-exam-skills-cover.png',
    category: 'Clinical Skills',
    subcategory: 'Clinical Examination',
    tags: ['Clinical Examination', 'CVS', 'RS', 'CNS', 'UPSC CMS', 'NEET PG', 'Medical Officers'],
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
    primaryCta: { label: 'Practice Clinical Exam PYQs (free)', href: '/questions?topic=clinical-examination' },
    relatedExamPaths: ['/cms', '/neet-pg'],
    faqs: [
        { q: 'Are clinical examination skills tested in UPSC CMS?', a: 'Yes — through clinical vignettes that describe physical findings and ask for diagnosis or next management step. Image-based questions may show clinical signs or examination findings.' },
        { q: 'What are the most important CVS examination findings?', a: 'JVP elevation (JVP > 3cm above sternal angle = elevated), apex beat displacement, murmurs (systolic vs diastolic, grading, radiation), S3 vs S4, pericardial rub.' },
        { q: 'What CNS examination steps are critical?', a: 'Higher functions (GCS, orientation), cranial nerves (all 12), motor system (tone, power, reflexes, Babinski), sensory (all modalities), cerebellar (finger-nose, heel-shin, Romberg).' },
    ],
    toc: [
        { id: 'cvs-exam', label: 'Cardiovascular Examination' },
        { id: 'rs-exam', label: 'Respiratory Examination' },
        { id: 'cns-exam', label: 'Central Nervous System Examination' },
        { id: 'abdomen-exam', label: 'Abdominal Examination' },
    ],
    references: [
        { label: 'Hutchisons Clinical Methods', url: 'https://www.amazon.com' },
    ],
    revisionLog: [{ date: '2026-09-19', note: 'Initial publication' }],
    body: `## Cardiovascular Examination

**Inspection:** Scars, precordial bulge, apex beat.
**Palpation:** Apex (location, character), thrills, heaves.
**Auscultation:** S1, S2, S3/S4, murmurs (systolic/diastolic, grading I-VI).

Key signs: Mitral stenosis (opening snap, diastolic rumble), Aortic regurgitation (blowing diastolic murmur, water-hammer pulse), Mitral regurgitation (pan-systolic murmur, apex radiation to axilla).

## Respiratory Examination

Inspection: chest shape, respiratory rate, use of accessory muscles.
Palpation: tracheal position, expansion.
Percussion: note resonance/dullness.
Auscultation: bronchial vs vesicular breath sounds, crackles, wheeze, pleural rub.

## Central Nervous System Examination

Higher functions -> Cranial nerves -> Motor (tone, power, reflexes) -> Sensory (all modalities) -> Cerebellar -> Gait.

## Abdominal Examination

Inspection: shape, scars, peristalsis, pulsations.
Palpation: superficial -> deep. Look for organomegaly, masses, tenderness.
Percussion: shifting dullness, fluid thrill, liver span.
Auscultation: bowel sounds, renal bruits, hepatic bruits.`,
    prelude: undefined,
    outro: undefined,
    pinned: false,
    trending: false,
};

export default post;
