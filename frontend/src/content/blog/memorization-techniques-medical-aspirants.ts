import type { BlogPost } from '@/lib/blog';

const post: BlogPost = {
    slug: 'memorization-techniques-medical-aspirants',
    title: 'Evidence-Based Memorization Techniques for Medical Aspirants: Spaced Repetition, Feynman and More',
    description: 'Evidence-based memorization techniques for medical PG aspirants — spaced repetition, Feynman technique, active recall, interleaving, and the science of memory.',
    excerpt: 'Evidence-based memorization techniques for medical aspirants — spaced repetition, Feynman, active recall, interleaving, and what cognitive science says about memory.',
    coverImage: '/blog/og/memorization-techniques-cover.png',
    category: 'Exam Strategy',
    subcategory: 'Study Methods',
    tags: ['Memorization', 'Spaced Repetition', 'Feynman', 'Study Methods', 'UPSC CMS', 'NEET PG'],
    difficulty: 'beginner',
    authorId: 'crackcms-editorial',
    reviewedBy: 'crackcms-editorial',
    author: 'CrackCMS Editorial Team',
    authorRole: 'Clinical Content Editors, CrackCMS',
    datePublished: '2026-09-19',
    dateModified: '2026-09-19',
    updatedAt: '2026-09-19',
    readingTime: '8 min',
    wordCount: 2400,
    primaryCta: { label: 'Start Flashcards Practice', href: '/flashcards' },
    relatedExamPaths: ['/cms', '/neet-pg'],
    faqs: [
        { q: 'What is spaced repetition and does it work?', a: 'Spaced repetition is a learning technique where you review information at increasing intervals. Based on the forgetting curve (Ebbinghaus), it improves long-term retention by 200-400% compared to cramming. Use Anki or our built-in flashcard system.' },
        { q: 'What is the Feynman technique?', a: 'Learn a concept, then teach it in simple terms as if explaining to a 12-year-old. Identify gaps in your explanation, go back to the source, and simplify further. This forces deep understanding rather than surface memorization.' },
        { q: 'Is active recall better than re-reading?', a: 'Yes — by a large margin. Studies show active recall (testing yourself) produces 50% better retention than passive re-reading. Use flashcards, write answers from memory, and solve questions without looking at notes.' },
    ],
    toc: [
        { id: 'spaced-repetition', label: 'Spaced Repetition' },
        { id: 'active-recall', label: 'Active Recall' },
        { id: 'feynman', label: 'Feynman Technique' },
        { id: 'interleaving', label: 'Interleaving' },
    ],
    references: [
        { label: 'Make It Stick: The Science of Successful Learning', url: 'https://www.harvard.com' },
    ],
    revisionLog: [{ date: '2026-09-19', note: 'Initial publication' }],
    body: `## Spaced Repetition

Review schedule: Day 1 (learn) -> Day 2 -> Day 7 -> Day 14 -> Day 30 -> Day 60. Use SM-2 algorithm (Anki default) for optimal intervals.

## Active Recall

Close the book and write/recall everything. Then check. The act of retrieval strengthens memory. 10 minutes of active recall > 60 minutes of re-reading.

## Feynman Technique

1. Choose a concept
2. Teach it simply (no jargon)
3. Identify the gap
4. Simplify and reorganize

## Interleaving

Mix different topics/subjects in one study session rather than blocking. Improves ability to differentiate between problem types — critical for MCQ exams.

## Other Techniques

- **Pomodoro**: 25 min focus + 5 min break
- **Dual coding**: Combine words with images
- **Elaborative interrogation**: Ask "why" for every fact
- **Concrete examples**: Link abstract facts to real patients`,
    prelude: undefined,
    outro: undefined,
    pinned: false,
    trending: false,
};

export default post;
