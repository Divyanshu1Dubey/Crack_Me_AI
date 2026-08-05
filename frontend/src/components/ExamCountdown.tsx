'use client';

import { useState, useEffect } from 'react';
import { Star } from 'lucide-react';

interface ExamRow {
  label: string;
  iso: string;
}

// All times are stored as ISO strings in UTC. Update these annually.
const UPCOMING_EXAMS: ExamRow[] = [
  { label: 'NEET PG', iso: '2026-08-30T00:00:00Z' },
  { label: 'UPSC CMS', iso: '2026-08-02T00:00:00Z' },
];

// Returns the label/value pair to render for a target date relative to now.
function describeRemaining(target: number, now: number): { kind: 'live' | 'future' | 'past'; text: string } {
  // Within ±12 hours of the target the exam is considered "Today" — anything
  // tighter than a day reads better as a single "Today" pill than as 0d.
  const DAY_MS = 24 * 60 * 60 * 1000;
  const distance = target - now;
  if (Math.abs(distance) <= 12 * 60 * 60 * 1000) {
    return { kind: 'live', text: 'Exam Today!' };
  }
  if (distance > 0) {
    const totalDays = Math.floor(distance / DAY_MS);
    if (totalDays >= 30) {
      const months = Math.floor(totalDays / 30);
      const days = totalDays % 30;
      const monthPart = months > 0 ? `${months}mo ` : '';
      return { kind: 'future', text: `${monthPart}${days}d Left` };
    }
    const d = totalDays;
    const h = Math.floor((distance % DAY_MS) / (60 * 60 * 1000));
    const m = Math.floor((distance % (60 * 60 * 1000)) / (60 * 1000));
    const s = Math.floor((distance % (60 * 1000)) / 1000);
    return { kind: 'future', text: `${d}d ${h.toString().padStart(2, '0')}h ${m.toString().padStart(2, '0')}m ${s.toString().padStart(2, '0')}s Left` };
  }
  // Past
  const pastDays = Math.floor(-distance / DAY_MS);
  if (pastDays <= 30) {
    return { kind: 'past', text: `Started ${pastDays}d ago` };
  }
  return { kind: 'past', text: 'Exam Concluded' };
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
          Last Month Revision &amp; Practice Platform
        </div>
        <div className="text-xs font-semibold flex flex-wrap justify-center items-center gap-x-6 gap-y-1 h-5" />
      </div>
    );
  }

  return (
    <div className={baseBannerClass}>
      <div className="text-xs font-extrabold uppercase tracking-widest text-yellow-300">
        Last Month Revision &amp; Practice Platform
      </div>
      <div className="text-xs font-semibold flex flex-wrap justify-center items-center gap-x-6 gap-y-1">
        {UPCOMING_EXAMS.map((exam) => {
          const target = new Date(exam.iso).getTime();
          const { kind, text } = describeRemaining(target, now);
          const dotClass =
            kind === 'live'
              ? 'text-red-400 fill-red-400 animate-pulse'
              : kind === 'past'
                ? 'text-slate-300 fill-slate-300'
                : 'text-yellow-300 fill-yellow-300';
          const labelClass = kind === 'past' ? 'opacity-80' : '';
          return (
            <div key={exam.iso} className={`flex items-center gap-2 ${labelClass}`}>
              <Star className={`w-3.5 h-3.5 ${dotClass}`} />
              <span>
                {exam.label}: {text}
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}
