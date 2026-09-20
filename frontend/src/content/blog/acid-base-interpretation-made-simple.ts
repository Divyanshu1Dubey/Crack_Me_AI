import type { BlogPost } from '@/lib/blog';

const post: BlogPost = {
    slug: 'acid-base-interpretation-made-simple',
    title: 'Acid-Base Interpretation Made Simple: The Step-by-Step Method for CMS Aspirants',
    description: 'Learn acid-base interpretation with our step-by-step method for UPSC CMS and NEET PG — pH, PaCO2, HCO3-, anion gap, Winter\'s formula and clinical cases.',
    excerpt: 'Acid-base interpretation step-by-step for UPSC CMS and NEET PG — pH, PaCO2, HCO3-, anion gap, Winter\'s formula and clinical case walkthroughs.',
    coverImage: '/blog/og/acid-base-interpretation-cover.png',
    category: 'Clinical Concepts',
    subcategory: 'General Medicine',
    tags: ['Acid-Base', 'ABG', 'Internal Medicine', 'UPSC CMS', 'NEET PG', 'Clinical Skills'],
    difficulty: 'intermediate',
    authorId: 'dr-aarav-mehta',
    reviewedBy: 'dr-aarav-mehta',
    author: 'Dr. Aarav Mehta, MBBS, MD (Internal Medicine)',
    authorRole: 'Senior Editor — Medicine, CrackCMS',
    datePublished: '2026-09-19',
    dateModified: '2026-09-19',
    updatedAt: '2026-09-19',
    readingTime: '11 min',
    wordCount: 3300,
    primaryCta: { label: 'Practice Medicine PYQs (free)', href: '/questions?topic=general-medicine' },
    relatedExamPaths: ['/cms', '/neet-pg'],
    faqs: [
        { q: 'What is the first step in acid-base interpretation?', a: 'Always start with pH. If pH < 7.35 = acidosis. If pH > 7.45 = alkalosis. Then look at PaCO2 (respiratory component) and HCO3- (metabolic component).' },
        { q: 'What is the anion gap and how is it calculated?', a: 'Anion Gap = Na+ - (Cl- + HCO3-). Normal range is 8-12 mEq/L. High anion gap metabolic acidosis has causes: MUDPILES (Methanol, Uremia, DKA, Propylene glycol, Iron/Isoniazid, Lactic acidosis, Ethylene glycol, Salicylates).' },
        { q: 'What is Winter\'s formula?', a: "Winter's formula: Expected PaCO2 = (1.5 x HCO3-) + 8 +/- 2. Used to check if respiratory compensation is appropriate in metabolic acidosis. If measured PaCO2 is higher than expected = concurrent respiratory acidosis." },
    ],
    toc: [
        { id: 'step-1-ph', label: 'Step 1: Check pH' },
        { id: 'step-2-primary-disorder', label: 'Step 2: Identify Primary Disorder' },
        { id: 'step-3-compensation', label: 'Step 3: Check Compensation' },
        { id: 'step-4-anion-gap', label: 'Step 4: Calculate Anion Gap' },
        { id: 'step-5-delta-gap', label: 'Step 5: Delta Gap / Delta Ratio' },
        { id: 'clinical-cases', label: 'Clinical Case Walkthroughs' },
    ],
    references: [
        { label: 'Kraut JA, Madias NE. Metabolic Acidosis: Pathophysiology, Diagnosis and Management.', url: 'https://www.ncbi.nlm.nih.gov' },
    ],
    revisionLog: [{ date: '2026-09-19', note: 'Initial publication' }],
    body: `## Step 1: Check pH

Always start with pH. If pH < 7.35 = acidosis. If pH > 7.45 = alkalosis.

## Step 2: Identify Primary Disorder

Compare pH with PaCO2 (respiratory) and HCO3- (metabolic). The component that moves in the same direction as pH is the primary disorder.

## Step 3: Check Compensation

Check if the compensation is appropriate. Winter's formula is key for metabolic acidosis compensation.

## Step 4: Calculate Anion Gap

Anion Gap = Na+ - (Cl- + HCO3-). Normal: 8-12 mEq/L.

## Step 5: Delta Gap / Delta Ratio

Delta gap = AG - 12. Delta HCO3 = 24 - measured HCO3-. Delta ratio = delta gap / delta HCO3.

## Clinical Case Walkthroughs

Practice with real ABG cases from UPSC CMS previous year papers to master this framework.`,
    prelude: undefined,
    outro: undefined,
    pinned: false,
    trending: false,
};

export default post;
