import type { BlogPost } from '@/lib/blog';

const post: BlogPost = {
    slug: 'anaesthesia-mcqs-upsc-cms',
    title: 'Anaesthesia MCQs for UPSC CMS: The Topics and Drug Doses That Appear Every Year',
    description: 'Anaesthesia MCQs for UPSC CMS — drug doses, equipment, monitoring, complications and the anaesthesia topics tested consistently across years.',
    excerpt: 'Anaesthesia MCQs for UPSC CMS — drug doses, equipment basics, monitoring, complications, and the anaesthesia topics tested every year.',
    coverImage: '/blog/og/anaesthesia-mcqs-cover.png',
    category: 'Subject Prep',
    subcategory: 'Anaesthesia',
    tags: ['Anaesthesia', 'Drug Doses', 'UPSC CMS', 'NEET PG'],
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
    primaryCta: { label: 'Practice Anaesthesia PYQs (free)', href: '/questions?topic=anaesthesia' },
    relatedExamPaths: ['/cms', '/neet-pg'],
    faqs: [
        { q: 'How many anaesthesia questions in UPSC CMS?', a: '3-5 questions from Anaesthesia in Paper I. Most are drug-dose based or complication-related. A smaller number test equipment and monitoring.' },
        { q: 'What anaesthesia drug doses must I memorize?', a: 'Common ones: Atropine (0.6 mg IV), Adrenaline (1 mg IV in cardiac arrest), Lidocaine (1.5 mg/kg plain, 3 mg/kg with adrenaline), Propofol (2-2.5 mg/kg), Succinylcholine (1-1.5 mg/kg), Rocuronium (0.6 mg/kg).' },
        { q: 'Is pre-anaesthetic checkup important for exams?', a: 'Yes — know the components: history, examination (CVS, RS, airway), investigations (Hb, BT, CT, ECG, chest X-ray for specific cases), and risk stratification (ASA classification).' },
    ],
    toc: [
        { id: 'drug-doses', label: 'Essential Drug Doses' },
        { id: 'inhalational-agents', label: 'Inhalational Agents' },
        { id: 'complications', label: 'Complications' },
        { id: 'monitoring', label: 'Monitoring' },
    ],
    references: [
        { label: 'Morgan and Mikhail Clinical Anesthesiology', url: 'https://www.mheducation.com' },
    ],
    revisionLog: [{ date: '2026-09-19', note: 'Initial publication' }],
    body: `## Essential Drug Doses

- **Thiopentone**: 3-5 mg/kg IV (induction)
- **Propofol**: 2-2.5 mg/kg IV (induction)
- **Succinylcholine**: 1-1.5 mg/kg IV (depolarizing)
- **Rocuronium**: 0.6 mg/kg IV (non-depolarizing)
- **Atracurium**: 0.5 mg/kg IV (non-depolarizing, organ-independent)

## Inhalational Agents

| Agent | MAC | Blood:Gas | Key Feature |
|-------|-----|-----------|-------------|
| Halothane | 0.75 | 2.5 | Hepatitis risk |
| Isoflurane | 1.2 | 1.4 | Tachycardia |
| Sevoflurane | 2.0 | 0.65 | Smooth induction |
| Desflurane | 6.0 | 0.42 | Rapid emergence |

## Complications

Laryngospasm (most common), bronchospasm, aspiration, malignant hyperthermia, awareness under GA, post-op nausea.

## Monitoring

ECG, SpO2, EtCO2, BP, Temperature, Etagent concentration.`,
    prelude: undefined,
    outro: undefined,
    pinned: false,
    trending: false,
};

export default post;
