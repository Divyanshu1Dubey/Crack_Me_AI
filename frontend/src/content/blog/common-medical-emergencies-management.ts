import type { BlogPost } from '@/lib/blog';

const post: BlogPost = {
    slug: 'common-medical-emergencies-management',
    title: 'Common Medical Emergencies: Step-by-Step Management Protocols Every MBBS Doctor Must Know',
    description: 'Step-by-step management of common medical emergencies for UPSC CMS — acute coronary syndrome, stroke, diabetic ketoacidosis, asthma, sepsis, and more.',
    excerpt: 'Common medical emergencies management for UPSC CMS — step-by-step protocols for ACS, stroke, DKA, asthma, sepsis, poisoning, and anaphylaxis.',
    coverImage: '/blog/og/common-emergencies-management-cover.png',
    category: 'Clinical Skills',
    subcategory: 'Emergency Management',
    tags: ['Medical Emergencies', 'Management', 'Protocols', 'MBBS', 'Clinical Skills'],
    difficulty: 'intermediate',
    authorId: 'dr-aarav-mehta',
    reviewedBy: 'dr-aarav-mehta',
    author: 'Dr. Aarav Mehta, MBBS, MD (Internal Medicine)',
    authorRole: 'Senior Editor — Medicine, CrackCMS',
    datePublished: '2026-09-19',
    dateModified: '2026-09-19',
    updatedAt: '2026-09-19',
    readingTime: '11 min',
    wordCount: 3200,
    primaryCta: { label: 'Practice Emergency Management PYQs', href: '/questions?topic=emergency-medicine' },
    relatedExamPaths: ['/cms', '/medical-officer'],
    faqs: [
        { q: 'What is MONA for ACS?', a: 'MONA = Morphine, Oxygen, Nitrates, Aspirin. Updated protocol: Aspirin 300mg chewable + P2Y12 inhibitor (Ticagrelor/Clopidogrel) + Anticoagulant (Heparin) + PCI if STEMI.' },
        { q: 'What is the stroke protocol?', a: 'FAST: Face droop, Arm weakness, Speech difficulty, Time (call emergency). For ischemic stroke within 4.5 hours: IV thrombolysis (tPA). For hemorrhagic: BP control, neurosurgical consultation.' },
        { q: 'What is the DKA management protocol?', a: 'Fluids (Normal saline 1L/hr), Insulin (0.1 U/kg/hr IV), Potassium replacement (if K < 3.3: hold insulin, give K). Monitor glucose hourly, electrolytes every 2-4 hours. Target: glucose <200, anion gap <12.' },
    ],
    toc: [
        { id: 'acs', label: 'Acute Coronary Syndrome' },
        { id: 'stroke', label: 'Stroke' },
        { id: 'dka', label: 'Diabetic Ketoacidosis' },
        { id: 'asthma', label: 'Acute Asthma' },
        { id: 'sepsis', label: 'Sepsis' },
    ],
    references: [
        { label: 'WHO Emergency Care Guidelines', url: 'https://www.who.int/publications' },
    ],
    revisionLog: [{ date: '2026-09-19', note: 'Initial publication' }],
    body: `## Acute Coronary Syndrome

MONA-B: Morphine, Oxygen, Nitrates, Aspirin, Beta-blocker. STEMI: Primary PCI within 90 min (door-to-balloon). NSTEMI: Risk stratify (TIMI, GRACE), early invasive strategy if high risk.

## Stroke

FAST screening. CT brain: exclude hemorrhage. IV tPA within 4.5 hours if ischemic. BP target <180/105 before thrombolysis.

## Diabetic Ketoacidosis

1L NS/hr, Insulin 0.1 U/kg/hr, K+ replacement. Monitor glucose, electrolytes, venous blood gas. Bicarbonate only if pH < 6.9.

## Acute Asthma

O2, SABA (Salbutamol nebulizers q20min), Ipratropium, Systemic steroids (Hydrocortisone). Magnesium sulfate if severe. Intubation if impending respiratory failure.

## Sepsis

Sepsis-3 criteria: SOFA increase >= 2 + suspected infection. Surviving Sepsis 1-hour bundle: lactate, blood cultures, broad-spectrum antibiotics, 30mL/kg crystalloid for hypotension, vasopressors if MAP <65.`,
    prelude: undefined,
    outro: undefined,
    pinned: false,
    trending: false,
};

export default post;
