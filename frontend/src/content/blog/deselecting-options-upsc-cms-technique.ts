import type { BlogPost } from '@/lib/blog';
import { CMS_MARKS_PER_QUESTION, CMS_PENALTY_PER_WRONG, round2 } from '@/lib/examPatterns';

// UPSC CMS marking (lib/examPatterns.ts): +2.08 per correct answer and
// one-third of that (−0.69) per wrong answer — not "+3/-1".
const fmt = (n: number) => round2(n).toFixed(2);
/** Expected marks from guessing among `left` remaining options (one correct). */
const ev = (left: number) => (1 / left) * CMS_MARKS_PER_QUESTION - ((left - 1) / left) * CMS_PENALTY_PER_WRONG;

const post: BlogPost = {
    slug: 'deselecting-options-upsc-cms-technique',
    title: 'The Deselection Technique: How Toppers Eliminate 3 Options in Every UPSC CMS MCQ',
    description: 'Learn the deselection technique for UPSC CMS — how toppers systematically eliminate 3 wrong options and improve accuracy from 40% to 80%+ without extra study time.',
    excerpt: 'The deselection technique for UPSC CMS — how toppers eliminate 3 options in every MCQ, boosting accuracy from 40% to 80%+ without studying more.',
    coverImage: '/blog/og/deselection-technique-cover.png',
    category: 'Exam Strategy',
    subcategory: 'Question-Solving',
    tags: ['Elimination', 'Deselection', 'MCQ Strategy', 'UPSC CMS', 'NEET PG', 'Smart Guessing'],
    difficulty: 'intermediate',
    authorId: 'dr-aarav-mehta',
    reviewedBy: 'crackcms-editorial',
    author: 'Dr. Aarav Mehta, MBBS, MD (Internal Medicine)',
    authorRole: 'Senior Editor — Medicine, CrackCMS',
    datePublished: '2026-09-19',
    dateModified: '2026-11-01',
    updatedAt: '2026-11-01',
    readingTime: '9 min',
    wordCount: 2800,
    // There is no "elimination mode"; the bank ignored ?mode=.
    primaryCta: { label: 'Practise UPSC CMS PYQs', href: '/questions?exam=cms' },
    relatedExamPaths: ['/cms', '/neet-pg'],
    faqs: [
        { q: 'What is the deselection technique?', a: 'Instead of finding the right answer, you eliminate the three clearly wrong options. This is psychologically easier and statistically increases your accuracy from 25% (random guess) to near 100% when 3 options are eliminated.' },
        { q: 'When should I guess in UPSC CMS?', a: `Whenever you can eliminate at least one option. UPSC CMS deducts one-third of a question's marks for a wrong answer (−${fmt(CMS_PENALTY_PER_WRONG)} against +${fmt(CMS_MARKS_PER_QUESTION)}), so with 2 options left a guess is worth 0.5 × ${fmt(CMS_MARKS_PER_QUESTION)} − 0.5 × ${fmt(CMS_PENALTY_PER_WRONG)} = +${fmt(ev(2))} marks on average.` },
        { q: 'Is educated guessing better than leaving blank?', a: `Yes. With one option eliminated the expected value is +${fmt(ev(3))}; with two eliminated it is +${fmt(ev(2))}. Only a blind guess among all four options breaks even (0.25 × ${fmt(CMS_MARKS_PER_QUESTION)} − 0.75 × ${fmt(CMS_PENALTY_PER_WRONG)} = 0).` },
    ],
    toc: [
        { id: 'psychology', label: 'The Psychology of Elimination' },
        { id: 'step-1', label: 'Step 1: Identify the Obviously Wrong' },
        { id: 'step-2', label: 'Step 2: Look for Subtle Clues' },
        { id: 'step-3', label: 'Step 3: Check the Remaining Two' },
        { id: 'math', label: 'The Math Behind Guessing' },
    ],
    references: [],
    revisionLog: [
        { date: '2026-09-19', note: 'Initial publication' },
        { date: '2026-11-01', note: 'Corrected the guessing maths to the UPSC CMS one-third negative marking (+2.08 / −0.69).' },
    ],
    body: `## The Psychology of Elimination

Finding the right answer among 4 options is hard. Eliminating 3 wrong ones is easier and more reliable. Your brain is better at detecting errors than confirming correctness.

## Step 1: Identify the Obviously Wrong

Scan all 4 options. Immediately cross out any that are factually wrong, use wrong terminology, or violate basic principles you know.

## Step 2: Look for Subtle Clues

Between remaining options, look for: absolute vs relative statements, "always" vs "usually", outdated guidelines, wrong drug doses.

## Step 3: Check the Remaining Two

Use the stem (question stem) for clues. Often the answer is in the question text itself — just disguised.

## The Math Behind Guessing

UPSC CMS gives +${fmt(CMS_MARKS_PER_QUESTION)} for a correct answer and takes one-third of that (−${fmt(CMS_PENALTY_PER_WRONG)}) for a wrong one:
- Eliminate 2 options: EV = +${fmt(ev(2))} (guess!)
- Eliminate 1 option: EV = +${fmt(ev(3))} (small but positive — guess)
- Eliminate 0 options: EV = ${fmt(ev(4))} (pure gamble — skip unless you have a real hunch)`,
    prelude: undefined,
    outro: undefined,
    pinned: false,
    trending: false,
};

export default post;
