/**
 * /questions/neet-pg/practice — NEET PG Question Bank landing page.
 *
 * Phase 9 (2026-07-26): previously this route rendered the standalone
 * `NeetPgPlayer` with no filters, no year stats, no Practice/Exam
 * toggle, and no AI Deep Analysis. It now delegates to the same
 * `<ExamQuestionBank>` body that powers `/questions` (UPSC CMS) so the
 * two tracks share filters, AI panels, image rendering, discussion
 * thread, year modal, and keyboard shortcuts.
 *
 * The standalone `NeetPgPlayer` is still used by `/tests/[id]` for the
 * immersive timed test player — that page is unchanged.
 *
 * URL contract (backwards-compatible):
 *   /questions/neet-pg/practice                       — full bank, NEET PG
 *   /questions/neet-pg/practice?year=2025             — pre-filter by year
 *   /questions/neet-pg/practice?subject=<id-or-name>  — pre-filter by subject
 *   /questions/neet-pg/practice?bookmarked=1          — only bookmarked
 *   /questions/neet-pg/practice?q=<id>                — open question on load
 */
'use client';
import { Suspense } from 'react';
import { useSearchParams } from 'next/navigation';
import Sidebar from '@/components/Sidebar';
import Header from '@/components/Header';
import EngagingLoader from '@/components/EngagingLoader';
import ExamQuestionBank from '@/components/question/ExamQuestionBank';

export default function NeetPgPracticePage() {
    return (
        <Suspense
            fallback={
                <div className="min-h-screen bg-background">
                    <Sidebar />
                    <div className="main-content">
                        <Header />
                        <EngagingLoader
                            title="Preparing your NEET PG Question Bank"
                            subtitle="Loading PYQs, year stats, and AI deep analysis"
                            tips={[
                                'Pick a year to start a focused practice block.',
                                'Click "Generate AI Analysis" after answering to unlock mnemonics and clinical pearls.',
                                'Bookmark high-yield questions — they show up here on the next visit.',
                            ]}
                        />
                    </div>
                </div>
            }
        >
            <Sidebar />
            <div className="main-content flex flex-col min-h-screen">
                <Header />
                <NeetPgPracticeInner />
            </div>
        </Suspense>
    );
}

function NeetPgPracticeInner() {
    const searchParams = useSearchParams();
    return (
        <ExamQuestionBank
            examType="neet_pg"
            examSource="NEET PG"
            defaultYear={searchParams.get('year')}
            initialQueryId={searchParams.get('q')}
            initialBookmarkOnly={searchParams.get('bookmarked') === '1'}
        />
    );
}