/**
 * ThemeToggle.tsx — Compact dark/light theme toggle.
 */
'use client';

import { useTheme } from 'next-themes';
import { Moon, Sun } from 'lucide-react';

export default function ThemeToggle() {
    const { setTheme, resolvedTheme } = useTheme();
    if (!resolvedTheme) return <div className="p-2 w-8.5 h-8.5" />;

    const isDark = resolvedTheme === 'dark';

    return (
        <button
            onClick={() => setTheme(isDark ? 'light' : 'dark')}
            className="p-2 rounded-lg hover:bg-accent transition-colors"
            title={isDark ? 'Switch to light mode' : 'Switch to dark mode'}
        >
            {isDark ? (
                <Sun className="w-4.5 h-4.5 text-muted-foreground" />
            ) : (
                <Moon className="w-4.5 h-4.5 text-muted-foreground" />
            )}
        </button>
    );
}
