import type { BlogPost } from '@/lib/blog';

const post: BlogPost = {
    slug: 'ecg-interpretation-upsc-cms-made-easy',
    title: 'ECG Interpretation for UPSC CMS: A 10-Step Framework That Never Fails',
    description: 'Master ECG interpretation for UPSC CMS and NEET PG with our 10-step framework. Covers rate, rhythm, axis, ST segments, common diagnoses and the ECG patterns that appear every year.',
    excerpt: 'A 10-step ECG interpretation framework for UPSC CMS and NEET PG — rate, rhythm, axis, ST segments, T waves, QT interval and the diagnoses that appear every year.',
    coverImage: '/blog/og/ecg-interpretation-upsc-cms-cover.png',
    category: 'Clinical Concepts',
    subcategory: 'Cardiology',
    tags: ['ECG', 'Cardiology', 'UPSC CMS', 'NEET PG', 'Clinical Skills', 'Medical Officers'],
    difficulty: 'intermediate',
    authorId: 'dr-aarav-mehta',
    reviewedBy: 'dr-aarav-mehta',
    author: 'Dr. Aarav Mehta, MBBS, MD (Internal Medicine)',
    authorRole: 'Senior Editor — Medicine, CrackCMS',
    datePublished: '2026-09-19',
    dateModified: '2026-09-19',
    updatedAt: '2026-09-19',
    readingTime: '12 min',
    wordCount: 3500,
    primaryCta: { label: 'Practice Cardiology PYQs (free)', href: '/questions?topic=cardiology' },
    relatedExamPaths: ['/cms', '/neet-pg'],
    faqs: [
        { q: 'How many ECG questions come in UPSC CMS?', a: 'Typically 3-5 ECG-based questions appear in UPSC CMS Paper I and II combined. They test rate, rhythm, axis, and specific diagnoses like STEMI, AF, and hyperkalemia.' },
        { q: 'Is ECG interpretation important for NEET PG too?', a: 'Yes, NEET PG also includes 2-4 ECG interpretation questions. The same framework applies to both exams — mastering it once covers both.' },
        { q: 'What is the best resource for ECG learning?', a: "Dubin's Rapid Interpretation of EKGs for basics, plus free online ECG simulators for practice. Our AI tutor can explain any ECG strip interactively." },
    ],
    toc: [
        { id: 'step-1-rate-rhythm', label: 'Step 1: Rate and Rhythm' },
        { id: 'step-2-axis', label: 'Step 2: Axis' },
        { id: 'step-3-p-waves', label: 'Step 3: P Waves' },
        { id: 'step-4-pr-interval', label: 'Step 4: PR Interval' },
        { id: 'step-5-qrs-duration', label: 'Step 5: QRS Duration' },
        { id: 'step-6-st-segment', label: 'Step 6: ST Segment' },
        { id: 'step-7-t-waves', label: 'Step 7: T Waves' },
        { id: 'step-8-qt-interval', label: 'Step 8: QT Interval' },
        { id: 'step-9-u-waves', label: 'Step 9: U Waves' },
        { id: 'step-10-put-it-together', label: 'Step 10: Put It All Together' },
    ],
    references: [
        { label: 'Dubin D. Rapid Interpretation of EKGs. 6th ed.', url: 'https://www.amazon.com/Rapid-Interpretation-EKGs-Sixth/dp/0963123215' },
        { label: 'AHA/ACC/HRS ECG Standards', url: 'https://www.ahajournals.org' },
    ],
    revisionLog: [{ date: '2026-09-19', note: 'Initial publication' }],
    body: `## Step 1: Rate and Rhythm

Calculate the heart rate. Regular rhythm at 60-100 bpm = sinus rhythm. Above 100 = tachycardia, below 60 = bradycardia.

## Step 2: Axis

Look at leads I and aVF. If both are positive = normal axis.

## Step 3: P Waves

Are P waves present before every QRS? Are they normal morphology?

## Step 4: PR Interval

Normal: 0.12-0.20 seconds. Short PR = WPW. Prolonged = first-degree AV block.

## Step 5: QRS Duration

Normal < 0.12s. Wide QRS = bundle branch block, hyperkalemia, or ventricular rhythm.

## Step 6: ST Segment

ST elevation = STEMI (or pericarditis). ST depression = ischemia or digoxin effect.

## Step 7: T Waves

Peaked T waves = hyperkalemia. Inverted T waves = ischemia.

## Step 8: QT Interval

Corrected QT > 440ms in men or > 460ms in women = prolonged. Risk of torsades de pointes.

## Step 9: U Waves

Prominent U waves = hypokalemia or hypothyroidism.

## Step 10: Put It All Together

Match the combination to the diagnosis. UPSC CMS favourite combinations: AF with RVR, LBBB, STEMI patterns, and hyperkalemia ECG changes.

## Common ECG Diagnoses in UPSC CMS

| Condition | Key Finding |
|-----------|-------------|
| STEMI | ST elevation in contiguous leads |
| NSTEMI | ST depression + T wave inversion |
| AF | Irregularly irregular, no P waves |
| VF | Chaotic waveform, no QRS |
| Hyperkalemia | Peaked T, wide QRS |

## Study Tips

Practice 50 ECGs daily for 2 weeks using free online resources. Memorize the criteria for LVH, RVH, and the criteria for STEMI equivalents.`,
    prelude: undefined,
    outro: undefined,
    pinned: false,
    trending: false,
};

export default post;
