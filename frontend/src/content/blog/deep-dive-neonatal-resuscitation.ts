import type { BlogPost } from '@/lib/blog';

const post: BlogPost = {
    slug: 'deep-dive-neonatal-resuscitation',
    title: 'Neonatal Resuscitation Program (NRP) Explained: Steps Every Paediatrics Candidate Must Know',
    description: 'Neonatal Resuscitation Program (NRP) step-by-step guide for UPSC CMS and NEET PG Paediatrics — initial steps, PPV, chest compressions, medications and the Quick checklist.',
    excerpt: 'NRP step-by-step for UPSC CMS and NEET PG — initial steps, PPV, chest compressions, epinephrine, and the algorithm that saves newborns.',
    coverImage: '/blog/og/neonatal-resuscitation-cover.png',
    category: 'Clinical Concepts',
    subcategory: 'Paediatrics',
    tags: ['Neonatal Resuscitation', 'NRP', 'Paediatrics', 'UPSC CMS', 'NEET PG', 'Clinical Skills'],
    difficulty: 'advanced',
    authorId: 'dr-aarav-mehta',
    reviewedBy: 'dr-aarav-mehta',
    author: 'Dr. Aarav Mehta, MBBS, MD (Internal Medicine)',
    authorRole: 'Senior Editor — Medicine, CrackCMS',
    datePublished: '2026-09-19',
    dateModified: '2026-09-19',
    updatedAt: '2026-09-19',
    readingTime: '10 min',
    wordCount: 3000,
    primaryCta: { label: 'Practice Paediatrics PYQs (free)', href: '/questions?topic=paediatrics' },
    relatedExamPaths: ['/cms', '/neet-pg'],
    faqs: [
        { q: 'What is the initial step in neonatal resuscitation?', a: 'Provide warmth, clear airway if needed, dry and stimulate the baby. 90% of newborns breathe spontaneously after drying and stimulation.' },
        { q: 'When should PPV be started?', a: 'PPV (positive pressure ventilation) is indicated if the baby is apneic after initial steps, has heart rate <100 bpm, or has persistent central cyanosis despite free-flow oxygen.' },
        { q: 'What is the ventilation rate for neonatal PPV?', a: '40-60 breaths per minute. Use a pressure of 20-25 cm H2O. Reassess heart rate and color after 30 seconds of effective PPV.' },
    ],
    toc: [
        { id: 'initial-steps', label: 'Initial Steps (Golden 60 Seconds)' },
        { id: 'apgar', label: 'APGAR Score' },
        { id: 'ppv', label: 'Positive Pressure Ventilation' },
        { id: 'chest-compressions', label: 'Chest Compressions' },
        { id: 'medications', label: 'Medications' },
    ],
    references: [
        { label: 'NRP 8th Edition Guidelines', url: 'https://www.nrp.org' },
    ],
    revisionLog: [{ date: '2026-09-19', note: 'Initial publication' }],
    body: `## Initial Steps (Golden 60 Seconds)

1. Position and clear airway (sniffing position)
2. Dry and stimulate (tactile stimulation)
3. Evaluate breathing and HR
4. If apneic/bradycardic: start PPV within 60 seconds

## APGAR Score

Appearance, Pulse, Grimace, Activity, Respiration — scored at 1 and 5 minutes.

## Positive Pressure Ventilation

Rate: 40-60 breaths/min. Pressure: 20-25 cm H2O. Check chest rise.

## Chest Compressions

Indicated when HR <60 despite 30 seconds of effective PPV. Ratio: 3:1 (90 compressions + 30 breaths/min).

## Medications

Epinephrine (0.01-0.03 mg/kg) via ET tube or IV. Volume expanders (normal saline) for hypovolemia. Naloxone for opioid-induced depression.`,
    prelude: undefined,
    outro: undefined,
    pinned: false,
    trending: false,
};

export default post;
