'use client';

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { BookOpen } from 'lucide-react';

const EXAM_OPTIONS = [
  { value: 'cms', label: 'UPSC CMS' },
  { value: 'neet_pg', label: 'NEET PG' },
  { value: 'usmle', label: 'USMLE' },
  { value: 'fmge', label: 'FMGE' },
];

export default function ExamSwitcher() {
  const router = useRouter();
  const [exam, setExam] = useState(() => {
    if (typeof window !== 'undefined') {
      return localStorage.getItem('crack_target_exam') || 'cms';
    }
    return 'cms';
  });
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
     
    setMounted(true);
  }, []);

  const handleExamChange = (val: string) => {
    if (val !== 'cms') {
      router.push(`/exams/${val.replace('_', '-')}`);
      return;
    }
    
    setExam(val);
    localStorage.setItem('crack_target_exam', val);
    
    // Dispatch a custom event so other components can react
    window.dispatchEvent(new Event('exam_changed'));
    
    // Optionally trigger a soft refresh
    router.refresh();
  };

  if (!mounted) return <div className="w-[140px] h-9 bg-muted rounded-md animate-pulse" />;

  return (
    <div className="flex items-center gap-2 bg-muted/50 rounded-md border p-1 pl-3 shadow-sm">
      <BookOpen className="w-4 h-4 text-muted-foreground" />
      <Select value={exam} onValueChange={handleExamChange}>
        <SelectTrigger className="w-[120px] h-7 border-0 bg-transparent focus:ring-0 focus:ring-offset-0 p-0 pr-3 shadow-none text-xs font-semibold">
          <SelectValue placeholder="Target Exam" />
        </SelectTrigger>
        <SelectContent>
          {EXAM_OPTIONS.map((opt) => (
            <SelectItem key={opt.value} value={opt.value} className="text-xs">
              {opt.label}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
    </div>
  );
}
