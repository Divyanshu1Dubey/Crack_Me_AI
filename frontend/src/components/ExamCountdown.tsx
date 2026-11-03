'use client';

import { useState, useEffect } from 'react';
import { Star } from 'lucide-react';
import { EXAM_DATES, upcomingExamDates } from '@/lib/examPatterns';

// Exam days live in lib/examPatterns.ts (EXAM_DATES). Concluded exams are
// hidden instead of showing "Exam Concluded" under a "Last Month Revision"
// banner; add the next cycle's dates there once the notices are out.

const DAY_MS = 24 * 60 * 60 * 1000;

// Returns the label/value pair to render for a target date relative to now.
function describeRemaining(target: number, now: number): { kind: 'live' | 'future'; text: string } {
  const distance = target - now;
  if (distance <= 12 * 60 * 60 * 1000) {
    return { kind: 'live', text: 'Exam Today!' };
  }
  const totalDays = Math.floor(distance / DAY_MS);
  if (totalDays >= 30) {
    const months = Math.floor(totalDays / 30);
    const days = totalDays % 30;
    const monthPart = months > 0 ? `${months}mo ` : '';
    return { kind: 'future', text: `${monthPart}${days}d Left` };
  }
  const h = Math.floor((distance % DAY_MS) / (60 * 60 * 1000));
  const m = Math.floor((distance % (60 * 60 * 1000)) / (60 * 1000));
  const s = Math.floor((distance % (60 * 1000)) / 1000);
  return { kind: 'future', text: `${totalDays}d ${h.toString().padStart(2, '0')}h ${m.toString().padStart(2, '0')}m ${s.toString().padStart(2, '0')}s Left` };
}

export default function ExamCountdown() {
  const [now, setNow] = useState(0);
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setNow(Date.now());
    setMounted(true);
    const interval = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(interval);
  }, []);

  const baseBannerClass = 'bg-linear-to-r from-blue-700 via-indigo-600 to-teal-600 text-white py-2 px-4 shadow-md flex flex-col items-center justify-center space-y-1';

  if (!mounted) {
    return (
      <div className={baseBannerClass}>
        <div className="text-xs font-extrabold uppercase tracking-widest text-yellow-300">
          UPSC CMS &amp; NEET PG Practice Platform
        </div>
        <div className="text-xs font-semibold flex flex-wrap justify-center items-center gap-x-6 gap-y-1 h-5" />
      </div>
    );
  }

  const upcoming = upcomingExamDates(new Date(now), EXAM_DATES);
  // "Last month revision" only while an exam is actually close.
  const examSoon = upcoming.some((e) => new Date(`${e.date}T00:00:00`).getTime() - now <= 45 * DAY_MS);

  return (
    <div className={baseBannerClass}>
      <div className="text-xs font-extrabold uppercase tracking-widest text-yellow-300">
        {examSoon ? <>Last Month Revision &amp; Practice Platform</> : <>UPSC CMS &amp; NEET PG Practice Platform</>}
      </div>
      <div className="text-xs font-semibold flex flex-wrap justify-center items-center gap-x-6 gap-y-1">
        {upcoming.length === 0 ? (
          <span className="opacity-90">Next exam dates will appear here once the official notifications are out.</span>
        ) : (
          upcoming.map((exam) => {
            const target = new Date(`${exam.date}T00:00:00`).getTime();
            const { kind, text } = describeRemaining(target, now);
            const dotClass = kind === 'live' ? 'text-red-400 fill-red-400 animate-pulse' : 'text-yellow-300 fill-yellow-300';
            return (
              <div key={exam.date + exam.name} className="flex items-center gap-2">
                <Star className={`w-3.5 h-3.5 ${dotClass}`} />
                <span>
                  {exam.name}: {text}
                </span>
              </div>
            );
          })
        )}
      </div>
    </div>
  );
}
