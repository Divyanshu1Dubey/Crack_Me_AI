'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { LayoutDashboard, BookOpen, FileText, Brain, BarChart3 } from 'lucide-react';
import { cn } from '@/lib/utils';

const items = [
  { href: '/dashboard', icon: LayoutDashboard, label: 'Home' },
  { href: '/questions', icon: BookOpen, label: 'Questions' },
  { href: '/tests', icon: FileText, label: 'Tests' },
  { href: '/ai-tutor', icon: Brain, label: 'AI Tutor' },
  { href: '/analytics', icon: BarChart3, label: 'Analytics' },
];

export default function BottomNav() {
  const pathname = usePathname();

  return (
    <nav className="fixed bottom-0 left-0 right-0 z-40 border-t border-border bg-background/95 backdrop-blur-sm md:hidden">
      <div className="flex items-center justify-around h-16 px-2">
        {items.map((item) => {
          const isActive = pathname === item.href || pathname?.startsWith(item.href + '/');
          return (
            <Link
              key={item.href}
              href={item.href}
              className={cn(
                "flex flex-col items-center gap-1 px-3 py-1.5 rounded-lg transition-colors min-w-[56px]",
                isActive ? "text-primary" : "text-muted-foreground"
              )}
            >
              <item.icon className={cn("w-5 h-5", isActive && "stroke-[2.5]")} />
              <span className="text-[10px] font-medium">{item.label}</span>
            </Link>
          );
        })}
      </div>
    </nav>
  );
}
