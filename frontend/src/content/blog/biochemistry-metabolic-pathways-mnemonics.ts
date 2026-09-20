import type { BlogPost } from '@/lib/blog';

const post: BlogPost = {
    slug: 'biochemistry-metabolic-pathways-mnemonics',
    title: 'Biochemistry Metabolic Pathways: Mnemonics That Stick (CMS + NEET PG)',
    description: 'Metabolic pathways mnemonics for UPSC CMS and NEET PG — glycolysis, TCA cycle, ETC, fatty acid metabolism, amino acids, and the tricks to memorize them.',
    excerpt: 'Biochemistry metabolic pathways mnemonics for UPSC CMS and NEET PG — glycolysis, TCA, ETC, fatty acids and amino acids made memorable.',
    coverImage: '/blog/og/biochem-mnemonics-cover.png',
    category: 'Subject Prep',
    subcategory: 'Biochemistry',
    tags: ['Biochemistry', 'Metabolism', 'Mnemonics', 'UPSC CMS', 'NEET PG'],
    difficulty: 'intermediate',
    authorId: 'dr-aarav-mehta',
    reviewedBy: 'dr-aarav-mehta',
    author: 'Dr. Aarav Mehta, MBBS, MD (Internal Medicine)',
    authorRole: 'Senior Editor — Medicine, CrackCMS',
    datePublished: '2026-09-19',
    dateModified: '2026-09-19',
    updatedAt: '2026-09-19',
    readingTime: '8 min',
    wordCount: 2400,
    primaryCta: { label: 'Practice Biochemistry PYQs (free)', href: '/questions?topic=biochemistry' },
    relatedExamPaths: ['/cms', '/neet-pg'],
    faqs: [
        { q: 'Which biochemistry textbook is best for exams?', a: 'Harper Illustrated Biochemistry is excellent with good diagrams. Lippincott is more student-friendly. Satyanarayana is popular in India for its simplified approach and exam-oriented presentation.' },
        { q: 'What are the most important metabolic pathways?', a: 'Glycolysis, gluconeogenesis, glycogen metabolism, TCA cycle, ETC/oxidative phosphorylation, fatty acid synthesis and oxidation, urea cycle, and heme synthesis.' },
        { q: 'How do I memorize the TCA cycle enzymes?', a: 'Use mnemonics. For the TCA cycle substrates: "Can I Keep Selling Sex For Money, Officer?" = Citrate, Isocitrate, alpha-Ketoglutarate, Succinyl-CoA, Succinate, Fumarate, Malate, Oxaloacetate.' },
    ],
    toc: [
        { id: 'glycolysis', label: 'Glycolysis Mnemonics' },
        { id: 'tca-cycle', label: 'TCA Cycle' },
        { id: 'etc', label: 'Electron Transport Chain' },
        { id: 'fatty-acids', label: 'Fatty Acid Metabolism' },
        { id: 'amino-acids', label: 'Amino Acid Metabolism' },
    ],
    references: [
        { label: 'Harper Illustrated Biochemistry', url: 'https://www.mheducation.com' },
    ],
    revisionLog: [{ date: '2026-09-19', note: 'Initial publication' }],
    body: `## Glycolysis Mnemonics

**Enzymes:** "Gregory Pecker Prefers Pimpin Pretty Fools" = GK, GPI, PFK-1, Aldolase, G3PDH, PGK, PGM, Enolase, PK.

**Irreversible steps:** Glucose -> G6P -> F6P -> F1,6BP. These are the regulatory steps.

## TCA Cycle

8 substrates. 8 enzymes. Focus on the three regulatory enzymes: Citrate synthase, Isocitrate dehydrogenase, alpha-KG dehydrogenase.

## Electron Transport Chain

Complex I (NADH dehydrogenase) -> CoQ -> Complex III -> Cyt c -> Complex IV -> O2. Complex II (succinate dehydrogenase) feeds electrons separately.

## Fatty Acid Metabolism

Beta-oxidation: Activation -> Transport (carnitine shuttle) -> 4-step cycle repeated. Unsaturated FA need additional enzymes (enoyl-CoA isomerase, reductase).

## Amino Acid Metabolism

Know the essential amino acids, ketogenic vs glucogenic classification, urea cycle enzymes, and key pathways (transamination, deamination, gluconeogenesis from AA).`,
    prelude: undefined,
    outro: undefined,
    pinned: false,
    trending: false,
};

export default post;
