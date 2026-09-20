import type { BlogPost } from '@/lib/blog';

const post: BlogPost = {
    slug: 'emergency-medicine-upsc-cms-quick-reference',
    title: 'Emergency Medicine Quick Reference: ACLS, ATLS and Common Emergencies for CMS Aspirants',
    description: 'Emergency medicine quick reference for UPSC CMS — ACLS protocols, ATLS principles, common emergency presentations, drug doses, and management algorithms.',
    excerpt: 'Emergency medicine quick reference for UPSC CMS — ACLS protocols, ATLS principles, drug doses, and step-by-step management of common emergencies.',
    coverImage: '/blog/og/emergency-medicine-cover.png',
    category: 'Clinical Skills',
    subcategory: 'Emergency Medicine',
    tags: ['Emergency Medicine', 'ACLS', 'ATLS', 'UPSC CMS', 'Medical Officers'],
    difficulty: 'advanced',
    authorId: 'dr-aarav-mehta',
    reviewedBy: 'dr-aarav-mehta',
    author: 'Dr. Aarav Mehta, MBBS, MD (Internal Medicine)',
    authorRole: 'Senior Editor — Medicine, CrackCMS',
    datePublished: '2026-09-19',
    dateModified: '2026-09-19',
    updatedAt: '2026-09-19',
    readingTime: '12 min',
    wordCount: 3500,
    primaryCta: { label: 'Practice Emergency Medicine PYQs', href: '/questions?topic=emergency-medicine' },
    relatedExamPaths: ['/cms', '/medical-officer'],
    faqs: [
        { q: 'What is the cardiac arrest algorithm?', a: 'Check responsiveness, call for help, check pulse. If no pulse: start CPR (30:2), attach defibrillator. Shockable (VF/pVT): defibrillate then CPR. Non-shockable (asystole/PEA): CPR + epinephrine every 3-5 min. Post-ROSC: optimize perfusion, treat reversible causes (Hs and Ts).' },
        { q: 'What are the Hs and Ts?', a: 'Hs: Hypoxia, Hypovolemia, Hypo/Hyperkalemia, Hypo/Hyperthermia, Hypoglycemia, Hydrogen ion (acidosis). Ts: Toxins, Tamponade, Tension pneumothorax, Thrombosis (PE, coronary), Trauma.' },
        { q: 'What is ATLS primary survey?', a: 'ABCDE: Airway with C-spine protection, Breathing, Circulation, Disability (neurological), Exposure/Environment. Life threats addressed in order of priority.' },
    ],
    toc: [
        { id: 'acls', label: 'ACLS Algorithm' },
        { id: 'atls', label: 'ATLS Primary Survey' },
        { id: 'cardiac-emergencies', label: 'Cardiac Emergencies' },
        { id: 'respiratory-emergencies', label: 'Respiratory Emergencies' },
        { id: 'hs-ts', label: 'Hs and Ts (Reversible Causes)' },
    ],
    references: [
        { label: 'AHA ACLS Guidelines 2025', url: 'https://cpr.heart.org' },
        { label: 'ATLS 10th Edition', url: 'https://www.facs.org' },
    ],
    revisionLog: [{ date: '2026-09-19', note: 'Initial publication' }],
    body: `## ACLS Algorithm

**Cardiac arrest**: CPR 30:2 -> Defibrillate if shockable -> CPR 2 min -> Epinephrine 1mg IV -> Amiodarone for VF/VT -> Continue cycle.

**Bradycardia**: Atropine 0.5mg IV -> Dopamine/epinephrine infusion -> Pacing.

**Tachycardia**: Unstable = synchronized cardioversion. Stable = amiodarone, sotalol, beta-blockers.

## ATLS Primary Survey

A = Airway with C-spine protection
B = Breathing (chest expansion, auscultation)
C = Circulation (hemorrhage control, IV access)
D = Disability (GCS, pupils)
E = Exposure/Environment

## Cardiac Emergencies

ACS (MONA), Aortic dissection (tearing pain, BP difference), PE (Wells score), Cardiac tamponade (Beck triad).

## Respiratory Emergencies

Asthma exacerbation (O2, SABA, systemic steroids), COPD exacerbation, Tension pneumothorax (needle decompression), Pulmonary edema.`,
    prelude: undefined,
    outro: undefined,
    pinned: false,
    trending: false,
};

export default post;
