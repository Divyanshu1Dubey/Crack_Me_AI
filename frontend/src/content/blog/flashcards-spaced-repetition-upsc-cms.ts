import type { BlogPost } from '@/lib/blog';

const post: BlogPost = {
    slug: 'flashcards-spaced-repetition-upsc-cms',
    title: 'Spaced Repetition Flashcards for UPSC CMS: How to Build a Deck That Cuts Revision Time by 60%',
    description: 'How to build and use spaced repetition flashcards for UPSC CMS and NEET PG — the SM-2 algorithm, card design principles, and the exact subjects to prioritize.',
    excerpt: 'Spaced repetition flashcards for UPSC CMS — build a deck that cuts revision time by 60% using the SM-2 algorithm and smart card design principles.',
    coverImage: '/blog/og/flashcards-spaced-repetition-cover.png',
    category: 'Exam Strategy',
    subcategory: 'Study Methods',
    tags: ['Flashcards', 'Spaced Repetition', 'Anki', 'UPSC CMS', 'NEET PG', 'SM-2'],
    difficulty: 'intermediate',
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
        { q: 'How many flashcards should I make for UPSC CMS?', a: 'Start with 500-800 cards covering the highest-yield topics. Focus on: one-liners, drug classifications, clinical signs, and PYQ facts. Quality > quantity — better to master 500 cards than to have 5000 mediocre ones.' },
        { q: 'Should I use Anki or physical flashcards?', a: 'Anki (free, desktop + mobile) is better for large decks because it automates spaced repetition. Physical cards are better for visual topics (anatomy diagrams, histology). Use both for best results.' },
        { q: 'What makes a good flashcard?', a: 'One question, one answer. Maximum 15 words. Use cloze deletion (fill-in-the-blank) for facts. Use images for visual topics. Avoid long paragraphs.' },
    ],
    toc: [
        { id: 'sm-2-algorithm', label: 'The SM-2 Algorithm' },
        { id: 'card-design', label: 'Card Design Principles' },
        { id: 'subjects-priority', label: 'Subject Priority' },
        { id: 'daily-routine', label: 'Daily Flashcard Routine' },
    ],
    references: [
        { label: 'Anki Manual', url: 'https://docs.ankiweb.net' },
    ],
    revisionLog: [{ date: '2026-09-19', note: 'Initial publication' }],
    body: `## The SM-2 Algorithm

SM-2 (used by Anki): After answering, rate difficulty (Again/Hard/Good/Easy). Card reappears based on ease factor:
- Again: < 1 minute
- Hard: 1-3 days
- Good: 3-7 days (default)
- Easy: 10+ days

## Card Design Principles

- One question, one answer
- Max 15 words per card
- Cloze deletion for facts
- Images for visual topics
- NO long paragraphs

## Subject Priority

Highest ROI: PSM (many facts), Pharmacology (drug facts), Microbiology (organisms), FSM (straight facts).
Lower ROI: Medicine (complex concepts), Surgery (procedures).

## Daily Flashcard Routine

Morning: 20 min review of due cards
Evening: 10 min add new cards from today's study
Weekly: 30 min cleanup (edit/delete stale cards)`,
    prelude: undefined,
    outro: undefined,
    pinned: false,
    trending: false,
};

export default post;
