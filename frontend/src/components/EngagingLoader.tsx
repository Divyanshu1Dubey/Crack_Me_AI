'use client';

import { useEffect, useMemo, useState } from 'react';
import BrandMark from '@/components/BrandMark';
import { BookOpen, Brain, Clock3, Sparkles, Target, TrendingUp } from 'lucide-react';

type EngagingLoaderProps = {
  title?: string;
  subtitle?: string;
  fullScreen?: boolean;
  tips?: string[];
};

const defaultTips = [
  'Tip: Solve PYQs daily for faster UPSC CMS retention.',
  'Tip: NEET PG and CMS overlap is strongest in Medicine and PSM.',
  'Tip: Practice in timed blocks to improve exam composure.',
  'Tip: Review weak topics first, then switch to mixed mock mode.',
  'Tip: AI explanations are best used after your first attempt.',
];

const icons = [BookOpen, Brain, Target, TrendingUp, Sparkles, Clock3];

export default function EngagingLoader({
  title = 'Preparing your smart study workspace...',
  subtitle = 'Setting up UPSC CMS and NEET PG focused content for you.',
  fullScreen = true,
  tips,
}: EngagingLoaderProps) {
  const activeTips = tips && tips.length > 0 ? tips : defaultTips;
  const [tipIndex, setTipIndex] = useState(0);
  const safeTipIndex = tipIndex % activeTips.length;

  useEffect(() => {
    const timer = setInterval(() => {
      setTipIndex((prev) => (prev + 1) % activeTips.length);
    }, 2600);
    return () => clearInterval(timer);
  }, [activeTips.length]);

  const Icon = useMemo(() => icons[safeTipIndex % icons.length], [safeTipIndex]);

  return (
    <div
      className={`${fullScreen ? 'min-h-screen' : 'min-h-64'} bg-background flex items-center justify-center p-6`}
      role="status"
      aria-live="polite"
      aria-busy="true"
    >
      <div className="w-full max-w-xl rounded-3xl border border-border/70 bg-card/85 p-7 shadow-sm backdrop-blur">
        <div className="flex items-center justify-between gap-4">
          <BrandMark href="/" compact />
          <div className="h-8 w-8 animate-spin rounded-full border-2 border-primary/30 border-t-primary" aria-hidden="true" />
        </div>

        <h2 className="mt-5 text-lg font-semibold text-foreground">{title}</h2>
        <p className="mt-1 text-sm text-muted-foreground">{subtitle}</p>

        <div className="mt-5 rounded-2xl border border-border/70 bg-muted/40 p-3">
          <div className="flex items-start gap-2.5 text-sm text-foreground">
            <Icon className="mt-0.5 h-4 w-4 shrink-0 text-primary" aria-hidden="true" />
            <span>{activeTips[safeTipIndex]}</span>
          </div>
        </div>

        <div className="mt-4 h-1.5 overflow-hidden rounded-full bg-muted">
          <div className="h-full w-1/3 animate-[loaderPulse_1.4s_ease-in-out_infinite] rounded-full bg-primary" />
        </div>
      </div>
    </div>
  );
}
