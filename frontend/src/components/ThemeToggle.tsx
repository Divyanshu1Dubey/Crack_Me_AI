/**
 * ThemeToggle.tsx — Dark/Light theme toggle button.
 * Uses next-themes for persistence. Shows "Midnight Aurora" (dark) or
 * "Crystal Cloud" (light) with animated glow indicator dot.
 */
'use client';

import { useTheme } from 'next-themes';
import { Moon, Sun } from 'lucide-react';
import { useEffect, useState } from 'react';

export default function ThemeToggle() {
    const { theme, setTheme, resolvedTheme } = useTheme();
    const [mounted, setMounted] = useState(false);

    useEffect(() => {
        setMounted(true);
    }, []);

    if (!mounted) return null;

    const isDark = resolvedTheme === 'dark';

    return (
        <button
            onClick={() => setTheme(isDark ? 'light' : 'dark')}
            className="w-full flex items-center justify-between px-4 py-3 rounded-xl transition-all duration-300 transform active:scale-95"
            style={{
                background: isDark ? 'rgba(0, 240, 255, 0.08)' : 'rgba(14, 165, 233, 0.08)',
                border: `1px solid ${isDark ? 'rgba(0, 240, 255, 0.25)' : 'rgba(14, 165, 233, 0.25)'}`,
                color: 'var(--text-primary)',
                boxShadow: isDark ? '0 0 15px rgba(0, 240, 255, 0.1)' : '0 0 15px rgba(14, 165, 233, 0.1)'
            }}
        >
            <div className="flex items-center gap-3">
                {isDark ? (
                    <Moon className="w-5 h-5 text-cyan-400" />
                ) : (
                    <Sun className="w-5 h-5 text-amber-500" />
                )}
                <span className="text-sm font-bold">
                    {isDark ? 'Midnight Aurora' : 'Crystal Cloud'}
                </span>
            </div>
            <div className={`w-2 h-2 rounded-full ${isDark ? 'bg-cyan-400 shadow-[0_0_8px_rgba(0,240,255,0.8)]' : 'bg-amber-500 shadow-[0_0_8px_rgba(245,158,11,0.8)]'}`} />
        </button>
    );
}
