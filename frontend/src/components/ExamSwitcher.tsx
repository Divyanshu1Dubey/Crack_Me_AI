'use client';

import { useState, useEffect } from 'react';
import { usePathname, useRouter } from 'next/navigation';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { BookOpen } from 'lucide-react';
import { useExamTrack } from '@/components/ExamTrackProvider';
import {
  EXAM_CODES,
  EXAM_LABELS,
  examFromPathname,
  isExamTrack,
  type ExamTrack,
} from '@/lib/appShellRoutes';

const EXAM_OPTIONS = (Object.keys(EXAM_LABELS) as ExamTrack[]).map((value) => ({
  value,
  label: EXAM_LABELS[value],
}));

const ROUTE_BY_EXAM: Record<ExamTrack, string> = {
  cms: '/questions?exam=cms',
  neet_pg: '/questions/neet-pg/practice',
  ini_cet: '/questions/inicet/practice',
  usmle: '/questions?exam=usmle',
  fmge: '/questions?exam=fmge',
};

export default function ExamSwitcher({ compact = false }: { compact?: boolean }) {
  const router = useRouter();
  const pathname = usePathname();
  // The exam track lives in ExamTrackProvider (Sidebar links, the
  // data-track accent colours). Writing it there updates the whole app at
  // once; a private copy here left the Sidebar on the old track until reload.
  const { activeTrack, setActiveTrack, hydrated } = useExamTrack();
  const [mounted, setMounted] = useState(false);

  useEffect(() => { setMounted(true); }, []);

  // The NEET PG and INI-CET banks are dedicated players: show their exam
  // there even when the saved preference is another track.
  const value: ExamTrack = examFromPathname(pathname) ?? (isExamTrack(activeTrack) ? activeTrack : 'cms');

  const handleExamChange = (val: string) => {
    if (!isExamTrack(val)) return;
    setActiveTrack(val);
    try {
      // tests/page.tsx still reads crack_target_exam on 'exam_changed'.
      localStorage.setItem('crack_target_exam', val);
      localStorage.setItem('active_exam_track', val);
    } catch {
      // Storage can be unavailable (private mode); the provider state still updates.
    }
    window.dispatchEvent(new Event('exam_changed'));
    router.push(ROUTE_BY_EXAM[val]);
  };

  if (!mounted || !hydrated) {
    return (
      <div
        aria-hidden="true"
        className={`h-9 rounded-xl bg-muted animate-pulse ${compact ? 'w-14 min-[380px]:w-[5.5rem]' : 'w-[140px]'}`}
      />
    );
  }

  const options = (
    <SelectContent>
      {EXAM_OPTIONS.map((opt) => (
        <SelectItem key={opt.value} value={opt.value} className="text-xs">
          {opt.label}
        </SelectItem>
      ))}
    </SelectContent>
  );

  if (compact) {
    // Header variant: the trigger itself is the pill, sized to its label
    // (a fixed 36px trigger showed only "U..."). The exam name fits the
    // phone header from 380px (390px phones included); only narrower
    // screens get the short code. Keep both spans on one breakpoint.
    return (
      <Select value={value} onValueChange={handleExamChange}>
        <SelectTrigger
          aria-label={`Exam track: ${EXAM_LABELS[value]}. Change exam track`}
          title="Switch exam track"
          className="h-9 w-auto shrink-0 gap-1 whitespace-nowrap rounded-xl border-border/80 bg-muted/70 px-2 py-0 text-[11px] font-semibold text-foreground shadow-none transition-colors hover:bg-accent focus:ring-0 focus:ring-offset-0 focus-visible:ring-2 focus-visible:ring-ring [&>svg]:h-3.5 [&>svg]:w-3.5"
        >
          <SelectValue>
            <span className="min-[380px]:hidden">{EXAM_CODES[value]}</span>
            <span className="hidden min-[380px]:inline">{EXAM_LABELS[value]}</span>
          </SelectValue>
        </SelectTrigger>
        {options}
      </Select>
    );
  }

  return (
    <div className="flex items-center gap-1 bg-muted/50 rounded-md border shadow-sm p-1 pl-3">
      <BookOpen className="w-3.5 h-3.5 text-muted-foreground shrink-0" aria-hidden="true" />
      <Select value={value} onValueChange={handleExamChange}>
        <SelectTrigger
          className="border-0 bg-transparent focus:ring-0 focus:ring-offset-0 p-0 pr-1 shadow-none text-xs font-semibold w-auto min-w-[6.5rem] h-7 gap-1 whitespace-nowrap"
          aria-label="Select exam track"
        >
          <SelectValue placeholder="Exam">{EXAM_LABELS[value]}</SelectValue>
        </SelectTrigger>
        {options}
      </Select>
    </div>
  );
}
