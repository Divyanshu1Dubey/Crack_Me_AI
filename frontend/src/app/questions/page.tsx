/**
 * questions/page.tsx — UPSC CMS Question Bank landing page.
 *
 * Thin shell that delegates the body to <ExamQuestionBank> with
 * examType='cms' / examSource='UPSC CMS'. Honours `?exam=neet-pg` (and
 * similar slugs) so users can switch exams via the URL — the same bank
 * UI is rendered with the matching exam params.
 *
 * Phase 9 (2026-07-26): the bank body was extracted to
 * `frontend/src/components/question/ExamQuestionBank.tsx` so NEET-PG and
 * INI-CET practice routes can render the same UI without forking.
 */
'use client';
import { Suspense } from 'react';
import { useSearchParams } from 'next/navigation';
import Sidebar from '@/components/Sidebar';
import Header from '@/components/Header';
import EngagingLoader from '@/components/EngagingLoader';
import ExamQuestionBank from '@/components/question/ExamQuestionBank';

const SLUG_TO_EXAM_TYPE: Record<string, string> = {
    'cms': 'cms',
    'neet-pg': 'neet_pg',
    'neet_pg': 'neet_pg',
    'ini-cet': 'ini_cet',
    'inicet': 'ini_cet',
    'ini-cet-pg': 'ini_cet',
    'fmge': 'fmge',
    'usmle': 'usmle',
    'medical-officer': 'cms',
};
const SLUG_TO_EXAM_SOURCE: Record<string, string> = {
    'cms': 'UPSC CMS',
    'neet-pg': 'NEET PG',
    'neet_pg': 'NEET PG',
    'ini-cet': 'INI-CET',
    'ini_cet': 'INI-CET',
    'inicet': 'INI-CET',
    'fmge': 'FMGE',
    'usmle': 'USMLE',
    'medical-officer': 'Medical Officer',
};

export default function QuestionsPage() {
    return (
        <Suspense
            fallback={
                <div className="min-h-screen bg-background">
                    <Sidebar />
                    <div className="main-content">
                        <Header />
                        <EngagingLoader
                            title="Preparing Your Question Bank"
                            subtitle="Loading PYQs, filters, and topic mapping for a smoother attempt flow"
                            tips={[
                                'Use subject + year filters to simulate exam-weighted practice blocks.',
                                'Attempt first, then open AI analysis to strengthen retention and reasoning.',
                                'Bookmark difficult concepts and revise them in spaced cycles.',
                            ]}
                        />
                    </div>
                </div>
            }
        >
            <Sidebar />
            <div className="main-content flex flex-col min-h-screen">
                <Header />
                <QuestionsContent />
            </div>
        </Suspense>
    );
}

function QuestionsContent() {
    const searchParams = useSearchParams();
    const urlExam = searchParams.get('exam');
    const examType = (urlExam && SLUG_TO_EXAM_TYPE[urlExam]) || 'cms';
    // Look up the source for the requested exam first; fall back to
    // 'cms'/'UPSC CMS' only when the slug is unknown. Previously the
    // fallback short-circuited valid slugs like 'medical-officer' and
    // showed 'UPSC CMS' as the source label.
    const examSource = (urlExam && SLUG_TO_EXAM_SOURCE[urlExam]) || SLUG_TO_EXAM_SOURCE.cms;
    return (
        <ExamQuestionBank
            examType={examType}
            examSource={examSource}
            initialQueryId={searchParams.get('q')}
            initialBookmarkOnly={searchParams.get('bookmarked') === '1'}
        />
    );
}