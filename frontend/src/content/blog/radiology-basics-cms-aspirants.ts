import type { BlogPost } from '@/lib/blog';

const post: BlogPost = {
    slug: 'radiology-basics-cms-aspirants',
    title: 'Radiology Basics for CMS Aspirants: X-Ray, CT and MRI Signs You Must Recognize',
    description: 'Radiology basics for UPSC CMS and NEET PG aspirants — common X-ray signs, CT findings, MRI sequences, and the radiology appearances that appear as image-based questions.',
    excerpt: 'Radiology basics for UPSC CMS and NEET PG — X-ray signs, CT findings, MRI sequences, and the radiology appearances tested as image-based questions.',
    coverImage: '/blog/og/radiology-basics-cover.png',
    category: 'Subject Prep',
    subcategory: 'Radiology',
    tags: ['Radiology', 'X-Ray', 'CT', 'MRI', 'UPSC CMS', 'NEET PG'],
    difficulty: 'intermediate',
    authorId: 'dr-aarav-mehta',
    reviewedBy: 'dr-aarav-mehta',
    author: 'Dr. Aarav Mehta, MBBS, MD (Internal Medicine)',
    authorRole: 'Senior Editor — Medicine, CrackCMS',
    datePublished: '2026-09-19',
    dateModified: '2026-09-19',
    updatedAt: '2026-09-19',
    readingTime: '9 min',
    wordCount: 2600,
    primaryCta: { label: 'Practice Radiology PYQs (free)', href: '/questions?topic=radiology' },
    relatedExamPaths: ['/cms', '/neet-pg'],
    faqs: [
        { q: 'How is radiology tested in UPSC CMS?', a: 'As image-based questions showing X-rays, CT or MRI images. Questions ask you to identify the modality, the finding, or the diagnosis. Chest X-rays are the most common.' },
        { q: 'What are the most common X-ray signs to know?', a: 'Air bronchogram, silhouette sign, Kerley B lines, eggshell calcification, tram track appearance, honeycombing, bat wing appearance, reverse pulmonary vascularity.' },
        { q: 'Do I need to know MRI sequences?', a: 'Know the basics: T1 (fat bright), T2 (water bright), FLAIR (suppresses CSF), DWI (acute stroke). These appear in questions about CNS imaging.' },
    ],
    toc: [
        { id: 'chest-xray', label: 'Chest X-Ray Signs' },
        { id: 'abdominal-radiology', label: 'Abdominal Radiology' },
        { id: 'mri-sequences', label: 'MRI Sequences' },
        { id: 'ct-findings', label: 'Key CT Findings' },
    ],
    references: [
        { label: 'Grainger and Allisons Diagnostic Radiology', url: 'https://www.amazon.com' },
    ],
    revisionLog: [{ date: '2026-09-19', note: 'Initial publication' }],
    body: `## Chest X-Ray Signs

**Air bronchogram:** Air-filled bronchus visible through consolidated lung. Sign of consolidation (pneumonia).

**Silhouette sign:** Loss of normal border between two structures of similar density. Right heart border lost = right middle lobe collapse.

**Bat wing appearance:** Bilateral perihilar infiltrates. Classic for pulmonary edema.

**Kerley B lines:** Horizontal lines at lung bases. Sign of interstitial pulmonary edema.

## Abdominal Radiology

- **Riglers sign**: Both sides of bowel wall visible = pneumoperitoneum
- **Coffee bean sign**: Sigmoid volvulus
- **Hausser sign**: Multiple air-fluid levels = small bowel obstruction

## MRI Sequences

T1-weighted: Fat = bright, water = dark. Good for anatomy.
T2-weighted: Water = bright, fat = bright. Good for pathology.
DWI: Restricted diffusion = bright (acute stroke, abscess).

## Key CT Findings

Hyperdense = acute hemorrhage. Hypodense = infarct, cyst, edema.`,
    prelude: undefined,
    outro: undefined,
    pinned: false,
    trending: false,
};

export default post;
