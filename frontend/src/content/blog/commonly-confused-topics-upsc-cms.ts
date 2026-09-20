import type { BlogPost } from '@/lib/blog';

const post: BlogPost = {
    slug: 'commonly-confused-topics-upsc-cms',
    title: '50 Commonly Confused Topics in UPSC CMS: The Pairs That Always Appear as Options',
    description: '50 commonly confused topic pairs in UPSC CMS — the distractors that appear together as options, how to tell them apart, and the mnemonics that stick.',
    excerpt: '50 commonly confused topic pairs in UPSC CMS — the distractors that always appear together as options. Learn the exact differences that separate right from wrong.',
    coverImage: '/blog/og/commonly-confused-topics-cover.png',
    category: 'Exam Strategy',
    subcategory: 'Quick Revision',
    tags: ['Confused Topics', 'Pairs', 'UPSC CMS', 'NEET PG', 'Differential Diagnosis'],
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
    primaryCta: { label: 'Practice Confusing Topic PYQs', href: '/questions?topic=confused-topics' },
    relatedExamPaths: ['/cms', '/neet-pg'],
    faqs: [
        { q: 'Why do confused topics appear in pairs?', a: 'Exam setters deliberately place similar-sounding conditions or drugs together to test depth of knowledge. This is the most common exam technique across all medical PG exams.' },
        { q: 'How do I tell similar conditions apart?', a: 'Focus on the ONE key differentiating feature. Examples: MI vs pericarditis (ST elevation: convex vs concave, PR depression), SLE vs RA (ANA pattern, joint involvement pattern).' },
        { q: 'Are these topic pairs the same for NEET PG?', a: 'Yes — 70-80% of these pairs are identical for NEET PG. The distinguishing features are the same. Learning these pairs helps both exams simultaneously.' },
    ],
    toc: [
        { id: 'cardiology-pairs', label: 'Cardiology Pairs' },
        { id: 'medicine-pairs', label: 'General Medicine Pairs' },
        { id: 'microbiology-pairs', label: 'Microbiology Pairs' },
        { id: 'surgery-pairs', label: 'Surgery Pairs' },
    ],
    references: [],
    revisionLog: [{ date: '2026-09-19', note: 'Initial publication' }],
    body: `## Cardiology Pairs

**STEMI vs Pericarditis:** STEMI = convex ST elevation, reciprocal changes, no PR depression. Pericarditis = concave ST elevation, PR depression, no reciprocal changes.

**Stable Angina vs MI:** Stable angina = exertional, relieved by rest/NTG, no enzyme rise. MI = rest pain, prolonged, enzyme rise.

**Atrial Fibrillation vs Atrial Flutter:** AF = irregularly irregular, no P waves, variable ventricular response. AFlutter = regular/sawtooth, flutter waves, usually 2:1 or 3:1 block.

## Medicine Pairs

**RA vs SLE:** RA = symmetric small joint, morning stiffness, rheumatoid factor, CCP. SLE = malar rash, ANA positive, dsDNA specific, multi-system.

**Addisons vs Cushings:** Addison = hypocortisolism, hyperpigmentation, hypotension. Cushing = hypercortisolism, central obesity, moon face, buffalo hump.

## Microbiology Pairs

**Typhoid vs Paratyphoid:** S. typhi = Widal positive, rose spots, ileal ulcers. S. paratyphi = milder disease, similar presentation.

## Surgery Pairs

**Appendicitis vs Mesenteric Adenitis:** Appendicitis = McBurney point tenderness, Rovsing sign, leucocytosis. Mesenteric adenitis = children, recent viral illness, diffuse pain.`,
    prelude: undefined,
    outro: undefined,
    pinned: false,
    trending: false,
};

export default post;
