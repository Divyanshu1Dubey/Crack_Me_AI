import type { BlogPost } from '@/lib/blog';

const post: BlogPost = {
    slug: 'negative-marking-strategy-upsc-cms',
    title: 'Negative Marking Strategy for UPSC CMS: When to Attempt, Skip or Guess (-1 Mark per Wrong Answer)',
    description: 'Negative marking strategy for UPSC CMS (+3/-1) — when to attempt, skip, or guess. Mathematical analysis of expected value and the exact thresholds for each decision.',
    excerpt: 'Negative marking strategy for UPSC CMS (+3/-1) — when to attempt, skip, or guess. The mathematical thresholds and the 3-option elimination rule.',
    coverImage: '/blog/og/negative-marking-strategy-cover.png',
    category: 'Exam Strategy',
    subcategory: 'Scoring Tactics',
    tags: ['Negative Marking', 'Guessing Strategy', 'UPSC CMS', 'Score Calculator', 'Strategy'],
    difficulty: 'intermediate',
    authorId: 'dr-aarav-mehta',
    reviewedBy: 'dr-aarav-mehta',
    author: 'Dr. Aarav Mehta, MBBS, MD (Internal Medicine)',
    authorRole: 'Senior Editor — Medicine, CrackCMS',
    datePublished: '2026-09-19',
    dateModified: '2026-09-19',
    updatedAt: '2026-09-19',
    readingTime: '7 min',
    wordCount: 2000,
    primaryCta: { label: 'Try Score Calculator', href: '/tools/score-calculator' },
    relatedExamPaths: ['/cms'],
    faqs: [
        { q: 'What is the marking scheme for UPSC CMS?', a: '+3 marks for correct answer, -1 mark for wrong answer, 0 for unattempted. There is no negative marking for "B" and "C" in CSAT Paper II.' },
        { q: 'When should I guess?', a: 'Guess when you can eliminate at least 2 options (EV = +1). Skip when you can eliminate 0-1 options (EV = -0.5 or 0).' },
        { q: 'How much can negative marking affect my rank?', a: 'Significantly. At 120 questions with 60% accuracy and 30 blind guesses: raw score = 144, with negative marking = 129. The 15-mark difference can shift your rank by hundreds.' },
    ],
    toc: [
        { id: 'marking-scheme', label: 'UPSC CMS Marking Scheme' },
        { id: 'expected-value', label: 'Expected Value Analysis' },
        { id: 'decision-table', label: 'Decision Table: When to Guess' },
        { id: 'practical-tips', label: 'Practical Tips' },
    ],
    references: [],
    revisionLog: [{ date: '2026-09-19', note: 'Initial publication' }],
    body: `## UPSC CMS Marking Scheme

Paper I: +3 for correct, -1 for wrong, 0 for blank.
Paper II: +3 for correct, -1 for wrong for Q1-75. Q76-100 (CSAT): +2.5/-0.83 for "B" and "C".

## Expected Value Analysis

| Options Eliminated | Probability Correct | Expected Value | Decision |
|-------------------|--------------------|---------------------|---------|
| 3 | 100% | +3 | Definitely attempt |
| 2 | 50% | +1 | Attempt |
| 1 | 33% | 0 | Break-even, skip if time-pressured |
| 0 | 25% | -0.5 | Definitely skip |

## Decision Table: When to Guess

1. Can I eliminate 2 or more options? -> Guess
2. Can I eliminate 1 option? -> Skip (unless you have a strong hunch)
3. Can I eliminate 0? -> Mark and move on

## Practical Tips

Use the last 10 minutes for reviewing marked questions. Never change an answer unless you find a definite error in your reasoning.`,
    prelude: undefined,
    outro: undefined,
    pinned: false,
    trending: false,
};

export default post;
