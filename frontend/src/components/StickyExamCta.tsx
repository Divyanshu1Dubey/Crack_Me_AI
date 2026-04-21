'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { ChevronRight, Sparkles } from 'lucide-react';
import { useAuth } from '@/lib/auth';

export default function StickyExamCta() {
  const pathname = usePathname();
  const { isAuthenticated, loading } = useAuth();

  const isHome = pathname === '/';
  if (!isHome || loading || isAuthenticated) return null;

  return (
    <div className="fixed inset-x-0 bottom-0 z-50 border-t border-border bg-background/95 px-4 py-2.5 shadow-lg backdrop-blur supports-[padding:max(0px)]:pb-[max(0.625rem,env(safe-area-inset-bottom))] sm:hidden">
      <div className="mx-auto flex max-w-6xl items-center justify-between gap-3">
        <div className="min-w-0">
          <p className="truncate text-xs font-semibold text-foreground">Start UPSC CMS + NEET PG smart prep</p>
          <p className="truncate text-[11px] text-muted-foreground">Free setup. Personalized study cockpit in minutes.</p>
        </div>
        <Link
          href="/register"
          className="inline-flex shrink-0 items-center gap-1.5 rounded-xl bg-primary px-3 py-2 text-xs font-semibold text-primary-foreground"
          aria-label="Start free preparation now"
        >
          <Sparkles className="h-3.5 w-3.5" />
          Start
          <ChevronRight className="h-3.5 w-3.5" />
        </Link>
      </div>
    </div>
  );
}
