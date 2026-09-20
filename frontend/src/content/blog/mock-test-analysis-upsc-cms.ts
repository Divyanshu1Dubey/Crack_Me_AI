import type { BlogPost } from '@/lib/blog';

const post: BlogPost = {
    slug: 'mock-test-analysis-upsc-cms',
    title: 'Mock Test Analysis for UPSC CMS: What Your Score Report Is Actually Telling You',
    description: 'How to analyze UPSC CMS mock test results — identifying weak subjects, time management issues, and building a targeted revision plan from your score report.',
    excerpt: 'Mock test analysis for UPSC CMS — what your score report actually tells you, how to identify real vs apparent weaknesses, and how to build a targeted revision plan.',
    coverImage: '/blog/og/mock-test-analysis-cover.png',
    category: 'Exam Strategy',
    subcategory: 'Mock Tests',
    tags: ['Mock Tests', 'Analysis', 'Score Report', 'UPSC CMS', 'Weak Areas'],
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
    primaryCta: { label: 'Try Mock Test Simulator', href: '/simulator' },
    relatedExamPaths: ['/cms'],
    faqs: [
        { q: 'How many mock tests should I take before UPSC CMS?', a: 'Minimum 15-20 full mock tests in the 3 months before the exam. Space them: 2 per week initially, then daily in the last 2 weeks.' },
        { q: 'What should I analyze after each mock test?', a: 'Subject-wise accuracy, time spent per question, topics where you guessed, repeated mistakes, and whether you left easy questions unattempted due to time pressure.' },
        { q: 'How do I track progress?', a: 'Create a spreadsheet: date, mock name, total score, subject scores, time taken, mistakes made. Plot scores over time — you should see a steady upward trend.' },
    ],
    toc: [
        { id: 'what-to-analyze', label: 'What to Analyze in Every Mock' },
        { id: 'subject-wise', label: 'Subject-Wise Analysis' },
        { id: 'time-analysis', label: 'Time Management Analysis' },
        { id: 'revision-plan', label: 'Building a Targeted Revision Plan' },
    ],
    references: [],
    revisionLog: [{ date: '2026-09-19', note: 'Initial publication' }],
    body: `## What to Analyze in Every Mock

1. Overall score and percentile
2. Subject-wise breakdown (accuracy per subject)
3. Time spent on correct vs incorrect answers
4. Topics with repeated mistakes
5. Unattempted easy questions (time management failure)

## Subject-Wise Analysis

Plot accuracy per subject. A subject at <50% accuracy needs urgent attention. A subject at 70-80% needs targeted revision. Above 80% = just maintain.

## Time Management Analysis

Check if you spent too much time on difficult questions and missed easy ones. Target: 60 seconds per question average.

## Building a Targeted Revision Plan

Based on mock analysis:
- Red zone (<50%): Re-learn the topic, solve 100 PYQs
- Yellow zone (50-75%): Review weak subtopics, solve 50 PYQs
- Green zone (>75%): Light revision, focus on other subjects`,
    prelude: undefined,
    outro: undefined,
    pinned: false,
    trending: false,
};

export default post;
