'use client';

import { useState, useEffect } from 'react';
import { Star } from 'lucide-react';

export default function ExamCountdown() {
  const [now, setNow] = useState(0);
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setNow(new Date().getTime());
    setMounted(true);
    const interval = setInterval(() => {
      setNow(new Date().getTime());
    }, 1000);
    return () => clearInterval(interval);
  }, []);

  const getRemaining = (targetDate: string) => {
    const distance = new Date(targetDate).getTime() - now;
    if (distance < 0) return '0d 0h 0m 0s';
    
    const d = Math.floor(distance / (1000 * 60 * 60 * 24));
    const h = Math.floor((distance % (1000 * 60 * 60 * 24)) / (1000 * 60 * 60));
    const m = Math.floor((distance % (1000 * 60 * 60)) / (1000 * 60));
    const s = Math.floor((distance % (1000 * 60)) / 1000);
    
    return `${d}d ${h.toString().padStart(2, '0')}h ${m.toString().padStart(2, '0')}m ${s.toString().padStart(2, '0')}s`;
  };

  if (!mounted) {
    return (
      <div className="bg-gradient-to-r from-blue-700 via-indigo-600 to-teal-600 text-white py-2 px-4 shadow-md flex flex-col items-center justify-center space-y-1">
        <div className="text-xs font-extrabold uppercase tracking-widest text-yellow-300">
          Last Month Revision & Practice Platform
        </div>
        <div className="text-xs font-semibold flex flex-wrap justify-center items-center gap-x-6 gap-y-1 h-5">
        </div>
      </div>
    );
  }

  return (
    <div className="bg-gradient-to-r from-blue-700 via-indigo-600 to-teal-600 text-white py-2 px-4 shadow-md flex flex-col items-center justify-center space-y-1">
      <div className="text-xs font-extrabold uppercase tracking-widest text-yellow-300">
        Last Month Revision & Practice Platform
      </div>
      <div className="text-xs font-semibold flex flex-wrap justify-center items-center gap-x-6 gap-y-1 font-mono">
        <div className="flex items-center gap-2">
          <Star className="w-3.5 h-3.5 text-yellow-300 fill-yellow-300" />
          <span>NEET PG: {getRemaining('2026-08-30T00:00:00Z')} Left</span>
        </div>
        <div className="flex items-center gap-2">
          <Star className="w-3.5 h-3.5 text-yellow-300 fill-yellow-300" />
          <span>UPSC CMS: {getRemaining('2026-08-02T00:00:00Z')} Left</span>
        </div>
      </div>
    </div>
  );
}
