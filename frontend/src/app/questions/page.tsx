/**
 * questions/page.tsx — UPSC CMS Question Bank landing page.
 *
 * Thin shell that delegates the body to <ExamQuestionBank> with
 * examType='cms' / examSource='UPSC CMS'. Honours `?exam=` (or
 * `?exam_type=`) so users can switch exams via the URL — matched
 * case-insensitively, as a slug (`neet-pg`), an enum value (`neet_pg`,
 * `NEET_PG`) or a label (`NEET PG`) — and the same bank UI is rendered with
 * the matching exam params. `?year=`, `?subject=` (id, name or slug such as
 * `medicine`), `?bookmarked=1` and `?q=<id>` pre-seed the filters / open a
 * question, as on the NEET PG and INI-CET banks.
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
import { examLabelFromParam, examTypeFromParam } from '@/components/question/practiceData';

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
    const urlExam = searchParams.get('exam') || searchParams.get('exam_type');
    // Unknown values fall back to the CMS bank. Blog / landing links use
    // `CMS`, `NEET_PG`, `INI_CET` and `NEET+PG`, which used to miss the
    // lower-case slug table and silently showed the CMS bank.
    const examType = examTypeFromParam(urlExam) || 'cms';
    // 'medical-officer' keeps its own label over the CMS rows.
    const examSource = examLabelFromParam(urlExam) || 'UPSC CMS';
    return (
        <ExamQuestionBank
            examType={examType}
            examSource={examSource}
            defaultYear={searchParams.get('year')}
            initialSubject={searchParams.get('subject')}
            initialQueryId={searchParams.get('q')}
            initialBookmarkOnly={searchParams.get('bookmarked') === '1'}
        />
    );
}