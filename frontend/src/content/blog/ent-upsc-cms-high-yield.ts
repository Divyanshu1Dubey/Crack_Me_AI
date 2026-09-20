import type { BlogPost } from '@/lib/blog';

const post: BlogPost = {
    slug: 'ent-upsc-cms-high-yield',
    title: 'ENT High-Yield for UPSC CMS: Ear, Nose and Throat Conditions That Are Exam Favourites',
    description: 'ENT high-yield topics for UPSC CMS and NEET PG — common ear conditions, nasal disorders, throat pathologies, and the ENT facts tested every year.',
    excerpt: 'ENT high-yield for UPSC CMS — common ear, nose and throat conditions, their diagnosis and management, and the facts that appear in every year\'s paper.',
    coverImage: '/blog/og/ent-high-yield-cover.png',
    category: 'Subject Prep',
    subcategory: 'ENT',
    tags: ['ENT', 'Ear', 'Nose', 'Throat', 'UPSC CMS', 'NEET PG'],
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
    primaryCta: { label: 'Practice ENT PYQs (free)', href: '/questions?topic=ent' },
    relatedExamPaths: ['/cms', '/neet-pg'],
    faqs: [
        { q: 'How many ENT questions in UPSC CMS?', a: '2-4 questions from ENT in Paper I. Focus on: hearing loss types, sinusitis, epistaxis management, tonsillitis, and laryngeal conditions.' },
        { q: 'What is the most common cause of conductive hearing loss?', a: 'Otitis media with effusion (OME) is the most common cause in children. In adults: otosclerosis. Remember: Conductive = problem in outer/middle ear. Sensorineural = problem in inner ear/nerve.' },
        { q: 'What is the management of epistaxis?', a: 'First: anterior nasal pack (Ribbon gauze with Vaseline). If fails: posterior nasal pack. If still fails: endoscopic cauterization or arterial ligation.' },
    ],
    toc: [
        { id: 'ear', label: 'Ear' },
        { id: 'nose', label: 'Nose and Paranasal Sinuses' },
        { id: 'throat', label: 'Throat' },
        { id: 'hearing-loss', label: 'Hearing Loss Classification' },
    ],
    references: [
        { label: 'Cummings Otolaryngology', url: 'https://www.elsevier.com' },
    ],
    revisionLog: [{ date: '2026-09-19', note: 'Initial publication' }],
    body: `## Ear

**Otitis externa**: "Swimmers ear". Treatment: topical antibiotics + steroids. Avoid in TM perforation.

**Otitis media**: Acute (AOM) vs chronic with effusion (OME). Treatment: amoxicillin first-line for AOM.

**Otosclerosis**: Conductive hearing loss. Abnormal bone remodeling at stapes footplate. Treatment: stapedectomy.

## Nose and Paranasal Sinuses

**Rhinosinusitis**: Acute (viral then bacterial), Chronic (polyp/surgical). Treatment: antibiotics for bacterial, surgery for refractory.

**Epistaxis**: Little area (Kiesselbach plexus) = 90% of nosebleeds. Anterior packing first-line.

## Throat

**Acute tonsillitis**: Viral vs bacterial (Group A strep). Centor criteria for strep throat. Tonsillectomy indications: recurrent infections, OSA, peritonsillar abscess.

## Hearing Loss Classification

Conductive (outer/middle ear), Sensorineural (inner ear/cochlear nerve), Mixed.`,
    prelude: undefined,
    outro: undefined,
    pinned: false,
    trending: false,
};

export default post;
