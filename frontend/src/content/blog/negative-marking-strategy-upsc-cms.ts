import type { BlogPost } from '@/lib/blog';
import { CMS_MARKS_PER_QUESTION, CMS_PENALTY_PER_WRONG, UPSC_CMS_PATTERN, round2 } from '@/lib/examPatterns';

// Marking from the UPSC CMS notice (lib/examPatterns.ts): each paper is 120
// questions for 250 marks, and a wrong answer costs one-third of the
// question's marks. (This post used to describe a "+3/-1" scheme with a CSAT
// section — that is the Civil Services prelims, not CMS.)
const c = CMS_MARKS_PER_QUESTION; // ≈ 2.083
const p = CMS_PENALTY_PER_WRONG; // ≈ 0.694
const fmt = (n: number) => round2(n).toFixed(2);
/** Expected marks from guessing among `left` remaining options (one correct). */
const ev = (left: number) => (1 / left) * c - ((left - 1) / left) * p;
const paper = UPSC_CMS_PATTERN.papers[0];
// Worked example: 100 attempted in one paper, 70 right and 30 wrong.
const exRight = 70;
const exWrong = 30;

const post: BlogPost = {
    slug: 'negative-marking-strategy-upsc-cms',
    title: 'Negative Marking Strategy for UPSC CMS: When to Attempt, Skip or Guess (One-Third Penalty per Wrong Answer)',
    description: `Negative marking strategy for UPSC CMS (+${fmt(c)} / −${fmt(p)} per question) — when to attempt, skip, or guess. Expected-value analysis of the one-third penalty in the computer-based test.`,
    excerpt: `Negative marking strategy for UPSC CMS (+${fmt(c)} / −${fmt(p)}) — when to attempt, skip, or guess, and why eliminating even one option makes a guess worth it.`,
    coverImage: '/blog/og/negative-marking-strategy-cover.png',
    category: 'Exam Strategy',
    subcategory: 'Scoring Tactics',
    tags: ['Negative Marking', 'Guessing Strategy', 'UPSC CMS', 'Score Calculator', 'Strategy'],
    difficulty: 'intermediate',
    authorId: 'dr-aarav-mehta',
    reviewedBy: 'crackcms-editorial',
    author: 'Dr. Aarav Mehta, MBBS, MD (Internal Medicine)',
    authorRole: 'Senior Editor — Medicine, CrackCMS',
    datePublished: '2026-09-19',
    dateModified: '2026-11-01',
    updatedAt: '2026-11-01',
    readingTime: '7 min',
    wordCount: 2000,
    primaryCta: { label: 'Try Score Calculator', href: '/tools/score-calculator' },
    relatedExamPaths: ['/cms'],
    faqs: [
        { q: 'What is the marking scheme for UPSC CMS?', a: `Each paper has ${paper.questions} questions for ${paper.marks} marks, so a correct answer earns about ${fmt(c)} marks. A wrong answer costs one-third of that (about ${fmt(p)}); an unanswered question costs nothing. The same rule applies to Paper I and Paper II.` },
        { q: 'When should I guess?', a: `With four options, a blind guess has an expected value of exactly zero under the one-third rule. Eliminate one option and a guess is worth about +${fmt(ev(3))} marks on average; eliminate two and it is worth about +${fmt(ev(2))}.` },
        { q: 'How much can negative marking affect my score?', a: `Attempting 100 questions in a paper with ${exRight} right and ${exWrong} wrong gives ${fmt(exRight * c)} − ${fmt(exWrong * p)} = ${fmt(exRight * c - exWrong * p)} marks out of ${paper.marks}. The ${fmt(exWrong * p)} marks lost to wrong answers can move your rank a long way.` },
    ],
    toc: [
        { id: 'marking-scheme', label: 'UPSC CMS Marking Scheme' },
        { id: 'expected-value', label: 'Expected Value Analysis' },
        { id: 'decision-table', label: 'Decision Table: When to Guess' },
        { id: 'practical-tips', label: 'Practical Tips' },
    ],
    references: [],
    revisionLog: [
        { date: '2026-09-19', note: 'Initial publication' },
        { date: '2026-11-01', note: 'Corrected the marking scheme to the UPSC CMS notice (one-third of 2.08 per wrong answer, both papers, computer-based test) and recomputed the expected values.' },
    ],
    body: `## UPSC CMS Marking Scheme

Both papers follow the same rule. Each paper has ${paper.questions} questions for ${paper.marks} marks, so:

- Correct answer: about **+${fmt(c)}** marks (${paper.marks} ÷ ${paper.questions})
- Wrong answer: **one-third** of that, about **−${fmt(p)}**
- Unanswered: **0**

The exam is a computer-based test, so you mark answers on screen as you go.

## Expected Value Analysis

Each question has four options and one correct answer.

| Options Eliminated | Probability Correct | Expected Value | Decision |
|-------------------|--------------------|---------------------|---------|
| 3 | 100% | +${fmt(ev(1))} | Definitely attempt |
| 2 | 50% | +${fmt(ev(2))} | Attempt |
| 1 | 33% | +${fmt(ev(3))} | Attempt — small but positive |
| 0 | 25% | ${fmt(ev(4))} | Pure gamble — skip unless you have a real hunch |

The one-third penalty is designed so that blind guessing on a four-option question averages out to zero. Any genuine elimination tips the odds in your favour.

## Decision Table: When to Guess

1. Can I eliminate 2 or more options? -> Guess
2. Can I eliminate 1 option? -> Guess (the expected value is positive, though small)
3. Can I eliminate 0? -> Mark for review and move on

## Practical Tips

Use the last 10 minutes for reviewing questions marked for review. Never change an answer unless you find a definite error in your reasoning.`,
    prelude: undefined,
    outro: undefined,
    pinned: false,
    trending: false,
};

export default post;
