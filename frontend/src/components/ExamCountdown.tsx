'use client';

import React, { useState, useEffect } from 'react';
import { Sparkles, Trophy } from 'lucide-react';
import './ExamCountdown.css';

interface TimeLeft {
  d: number;
  h: number;
  m: number;
  s: number;
}

function DigitCard({ val, label }: { val: number; label: string }) {
  const str = String(val).padStart(2, '0');
  return (
    <div className="inline-flex items-center gap-1">
      <div className="digit-flip-box">
        <span key={str} className="digit-slide-up">
          {str}
        </span>
      </div>
      <span className="text-[10px] font-semibold text-slate-200 uppercase">{label}</span>
    </div>
  );
}

export default function ExamCountdown() {
  const [now, setNow] = useState<number>(0);
  const [mounted, setMounted] = useState<boolean>(false);

  useEffect(() => {
    setNow(new Date().getTime());
    setMounted(true);
    const interval = setInterval(() => {
      setNow(new Date().getTime());
    }, 1000);
    return () => clearInterval(interval);
  }, []);

  const getTimeLeft = (targetDate: string): TimeLeft => {
    if (!mounted || !now) return { d: 0, h: 0, m: 0, s: 0 };
    const distance = new Date(targetDate).getTime() - now;
    if (distance < 0) return { d: 0, h: 0, m: 0, s: 0 };

    const d = Math.floor(distance / (1000 * 60 * 60 * 24));
    const h = Math.floor((distance % (1000 * 60 * 60 * 24)) / (1000 * 60 * 60));
    const m = Math.floor((distance % (1000 * 60 * 60)) / (1000 * 60));
    const s = Math.floor((distance % (1000 * 60)) / 1000);

    return { d, h, m, s };
  };

  const neetTime = getTimeLeft('2026-08-30T00:00:00Z');
  const cmsTime = getTimeLeft('2026-08-02T00:00:00Z');

  return (
    <div className="announcement-bar py-2 px-4 flex flex-col items-center justify-center space-y-1.5 z-40">
      {/* Static Announcement Header */}
      <div className="text-[11px] font-black uppercase tracking-widest text-amber-300 flex items-center gap-1.5 drop-shadow-xs">
        <Sparkles className="w-3.5 h-3.5 text-amber-300 animate-pulse" />
        <span>LAST MONTH REVISION & PRACTICE PLATFORM</span>
        <Sparkles className="w-3.5 h-3.5 text-amber-300 animate-pulse" />
      </div>

      {/* Exam Countdown Badges with breathing glow & Flip Digits */}
      <div className="flex flex-wrap justify-center items-center gap-x-4 gap-y-2 text-xs">
        {/* NEET PG Pill Badge */}
        <div className="exam-pill-badge">
          <Trophy className="w-3.5 h-3.5 text-amber-300 shrink-0" />
          <span className="font-extrabold text-white text-xs">NEET PG:</span>
          <div className="flex items-center gap-1.5 ml-0.5">
            <DigitCard val={neetTime.d} label="d" />
            <DigitCard val={neetTime.h} label="h" />
            <DigitCard val={neetTime.m} label="m" />
            <DigitCard val={neetTime.s} label="s" />
          </div>
        </div>

        {/* UPSC CMS Pill Badge */}
        <div className="exam-pill-badge">
          <Trophy className="w-3.5 h-3.5 text-teal-300 shrink-0" />
          <span className="font-extrabold text-white text-xs">UPSC CMS:</span>
          <div className="flex items-center gap-1.5 ml-0.5">
            <DigitCard val={cmsTime.d} label="d" />
            <DigitCard val={cmsTime.h} label="h" />
            <DigitCard val={cmsTime.m} label="m" />
            <DigitCard val={cmsTime.s} label="s" />
          </div>
        </div>
      </div>
    </div>
  );
}
