'use client';

import { useTheme } from 'next-themes';
import { Moon, Sun } from 'lucide-react';

export default function ThemeToggle() {
  const { setTheme, resolvedTheme } = useTheme();
  if (!resolvedTheme) return <div className="w-10 h-10 rounded-full border border-border/60 bg-muted/30" aria-hidden="true" />;

  const isDark = resolvedTheme === 'dark';

  return (
    <button
      type="button"
      onClick={(e) => { e.preventDefault(); e.stopPropagation(); setTheme(isDark ? 'light' : 'dark'); }}
      className="flex items-center justify-center w-10 h-10 rounded-full border border-border/70 bg-muted/40 hover:bg-muted/80 backdrop-blur-md transition-all duration-300 hover:rotate-45 active:scale-95 shadow-sm hover:shadow-md cursor-pointer text-foreground"
      title={isDark ? 'Switch to light mode' : 'Switch to dark mode'}
      aria-label="Toggle theme"
    >
      {isDark ? (
        <Sun className="w-4.5 h-4.5 text-amber-400" />
      ) : (
        <Moon className="w-4.5 h-4.5 text-slate-700" />
      )}
    </button>
  );
}
