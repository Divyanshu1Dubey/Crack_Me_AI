/**
 * /questions/inicet/practice — INI-CET Question Bank landing page.
 *
 * Phase 9 (2026-07-26): previously this route rendered the standalone
 * `IniCetPlayer` with no filters, no year stats, no Practice/Exam
 * toggle, and no AI Deep Analysis. It now delegates to the same
 * `<ExamQuestionBank>` body that powers `/questions` (UPSC CMS) and
 * `/questions/neet-pg/practice` so all three banks share filters, AI
 * panels, image rendering, discussion thread, year modal, and keyboard
 * shortcuts.
 *
 * The standalone `IniCetPlayer` is still used by `/tests/[id]` for the
 * immersive timed test player — that page is unchanged.
 *
 * URL contract (backwards-compatible):
 *   /questions/inicet/practice                       — full bank, INI-CET
 *   /questions/inicet/practice?year=2024             — pre-filter by year
 *   /questions/inicet/practice?subject=<id-or-name>  — pre-filter by subject
 *   /questions/inicet/practice?q=<id>                — open question on load
 */
'use client';
import { Suspense } from 'react';
import { useSearchParams } from 'next/navigation';
import Sidebar from '@/components/Sidebar';
import Header from '@/components/Header';
import EngagingLoader from '@/components/EngagingLoader';
import ExamQuestionBank from '@/components/question/ExamQuestionBank';

export default function IniCetPracticePage() {
    return (
        <Suspense
            fallback={
                <div className="min-h-screen bg-background">
                    <Sidebar />
                    <div className="main-content">
                        <Header />
                        <EngagingLoader
                            title="Preparing your INI-CET Question Bank"
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
                <IniCetPracticeInner />
            </div>
        </Suspense>
    );
}

function IniCetPracticeInner() {
    const searchParams = useSearchParams();
    return (
        <ExamQuestionBank
            examType="ini_cet"
            examSource="INI-CET"
            defaultYear={searchParams.get('year')}
            initialQueryId={searchParams.get('q')}
            initialBookmarkOnly={searchParams.get('bookmarked') === '1'}
        />
    );
}