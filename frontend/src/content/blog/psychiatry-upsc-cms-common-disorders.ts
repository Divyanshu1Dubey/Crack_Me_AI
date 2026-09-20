import type { BlogPost } from '@/lib/blog';

const post: BlogPost = {
    slug: 'psychiatry-upsc-cms-common-disorders',
    title: 'Psychiatry for UPSC CMS: Common Disorders, Classifications and Drug Mechanisms',
    description: 'Psychiatry for UPSC CMS — common disorders (depression, anxiety, schizophrenia, bipolar), ICD-11 classifications, drug mechanisms and side effects.',
    excerpt: 'Psychiatry for UPSC CMS — depression, anxiety, schizophrenia, bipolar disorder: classifications, drug mechanisms, side effects, and the PYQ patterns.',
    coverImage: '/blog/og/psychiatry-cms-cover.png',
    category: 'Subject Prep',
    subcategory: 'Psychiatry',
    tags: ['Psychiatry', 'ICD', 'Drugs', 'UPSC CMS', 'NEET PG'],
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
    primaryCta: { label: 'Practice Psychiatry PYQs (free)', href: '/questions?topic=psychiatry' },
    relatedExamPaths: ['/cms', '/neet-pg'],
    faqs: [
        { q: 'What is the difference between ICD-10 and ICD-11 classifications?', a: 'ICD-11 (2022) simplified classifications: F32 = single episode depressive disorder, F33 = recurrent depressive disorder, F20 = schizophrenia, F31 = bipolar disorder. UPSC CMS now references ICD-11.' },
        { q: 'What is the first-line drug for depression?', a: 'SSRIs (Fluoxetine, Sertraline, Escitalopram) are first-line. They inhibit serotonin reuptake. Side effects: GI upset, sexual dysfunction, insomnia. SNRIs (Venlafaxine) for atypical depression.' },
        { q: 'What is ECT used for?', a: 'ECT is used for severe depression (especially with suicidality or psychosis), catatonia, and treatment-resistant depression. It is the most effective treatment for severe depression.' },
    ],
    toc: [
        { id: 'depression', label: 'Depression' },
        { id: 'anxiety', label: 'Anxiety Disorders' },
        { id: 'schizophrenia', label: 'Schizophrenia' },
        { id: 'bipolar', label: 'Bipolar Disorder' },
        { id: 'drugs', label: 'Psychiatric Drug Classes' },
    ],
    references: [
        { label: 'ICD-11 Classification', url: 'https://icd.who.int' },
        { label: 'Kaplan and Sadocks Synopsis of Psychiatry', url: 'https://www.wolterskluwer.com' },
    ],
    revisionLog: [{ date: '2026-09-19', note: 'Initial publication' }],
    body: `## Depression

F32 (single episode), F33 (recurrent). Symptoms: low mood, anhedonia, weight change, sleep disturbance, fatigue, guilt, concentration, suicidality. First-line: SSRIs.

## Anxiety Disorders

GAD: excessive worry >6 months. Panic disorder: recurrent panic attacks with anticipatory anxiety. Treatment: SSRIs + CBT.

## Schizophrenia

F20. Positive symptoms: delusions, hallucinations, disorganized speech. Negative symptoms: flat affect, avolition. First-line: atypical antipsychotics (Olanzapine, Risperidone).

## Bipolar Disorder

F31. Manic episode: elevated mood, grandiosity, decreased sleep, pressured speech. Depressive episode as above. Treatment: mood stabilizers (Lithium, Valproate, Carbamazepine).

## Psychiatric Drug Classes

SSRIs, SNRIs, TCAs, MAOIs, Benzodiazepines, Atypical antipsychotics, Mood stabilizers, Stimulants (ADHD).`,
    prelude: undefined,
    outro: undefined,
    pinned: false,
    trending: false,
};

export default post;
