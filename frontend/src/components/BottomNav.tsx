'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { cn } from '@/lib/utils';
import CustomIcon from '@/components/CustomIcon';

const items = [
  { href: '/dashboard', iconName: 'dashboard-layout', label: 'Home' },
  { href: '/questions', iconName: 'question-bank-book', label: 'Questions' },
  { href: '/tests', iconName: 'tests-check', label: 'Tests' },
  { href: '/ai-tutor', iconName: 'ai-tutor-brain', label: 'AI Tutor' },
  { href: '/analytics', iconName: 'analytics-growth', label: 'Analytics' },
];

export default function BottomNav() {
  const pathname = usePathname();

  return (
    <nav className="fixed inset-x-0 bottom-3 z-40 px-3 md:hidden">
      <div className="mx-auto flex h-16 max-w-md items-center justify-around rounded-2xl border border-border bg-card/85 px-2 shadow-lg backdrop-blur-xl">
        {items.map((item) => {
          const isActive = pathname === item.href || pathname?.startsWith(item.href + '/');
          return (
            <Link
              key={item.href}
              href={item.href}
              className={cn(
                "flex min-w-[56px] flex-col items-center gap-1 rounded-xl px-3 py-1.5 transition-all",
                isActive ? "bg-primary/10 text-primary" : "text-muted-foreground"
              )}
            >
              <CustomIcon
                name={item.iconName}
                label={item.label}
                className="w-5 h-5"
                variant={isActive ? 'active' : 'subtle'}
              />
              <span className="text-[10px] font-medium">{item.label}</span>
            </Link>
          );
        })}
      </div>
    </nav>
  );
}
