import type { BlogPost } from '@/lib/blog';

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
    reviewedBy: 'dr-aarav-mehta',
    author: 'Dr. Aarav Mehta, MBBS, MD (Internal Medicine)',
    authorRole: 'Senior Editor — Medicine, CrackCMS',
    datePublished: '2026-09-19',
    dateModified: '2026-09-19',
    updatedAt: '2026-09-19',
    readingTime: '9 min',
    wordCount: 2800,
    primaryCta: { label: 'Practice with Elimination Mode', href: '/questions?mode=elimination' },
    relatedExamPaths: ['/cms', '/neet-pg'],
    faqs: [
        { q: 'What is the deselection technique?', a: 'Instead of finding the right answer, you eliminate the three clearly wrong options. This is psychologically easier and statistically increases your accuracy from 25% (random guess) to near 100% when 3 options are eliminated.' },
        { q: 'When should I guess in UPSC CMS?', a: 'When you have eliminated at least 2 options. With 2 remaining and -1 negative marking, your expected value from guessing is positive (0.5 * +3 - 0.5 * -1 = +1 per question).' },
        { q: 'Is educated guessing better than leaving blank?', a: 'Yes — in UPSC CMS (+3/-1 marking), with 2 options eliminated, guessing has positive expected value. With only 1 option eliminated, the expected value is break-even (0.25 * +3 - 0.75 * -1 = 0).' },
    ],
    toc: [
        { id: 'psychology', label: 'The Psychology of Elimination' },
        { id: 'step-1', label: 'Step 1: Identify the Obviously Wrong' },
        { id: 'step-2', label: 'Step 2: Look for Subtle Clues' },
        { id: 'step-3', label: 'Step 3: Check the Remaining Two' },
        { id: 'math', label: 'The Math Behind Guessing' },
    ],
    references: [],
    revisionLog: [{ date: '2026-09-19', note: 'Initial publication' }],
    body: `## The Psychology of Elimination

Finding the right answer among 4 options is hard. Eliminating 3 wrong ones is easier and more reliable. Your brain is better at detecting errors than confirming correctness.

## Step 1: Identify the Obviously Wrong

Scan all 4 options. Immediately cross out any that are factually wrong, use wrong terminology, or violate basic principles you know.

## Step 2: Look for Subtle Clues

Between remaining options, look for: absolute vs relative statements, "always" vs "usually", outdated guidelines, wrong drug doses.

## Step 3: Check the Remaining Two

Use the stem (question stem) for clues. Often the answer is in the question text itself — just disguised.

## The Math Behind Guessing

With +3/-1 marking in UPSC CMS:
- Eliminate 2 options: EV = +1 (guess!)
- Eliminate 1 option: EV = 0 (neutral)
- Eliminate 0 options: EV = -0.5 (skip)`,
    prelude: undefined,
    outro: undefined,
    pinned: false,
    trending: false,
};

export default post;
