'use client';

/**
 * ThemeSync — keeps the Tailwind `class="dark"` mirror in sync with the
 * next-themes `data-theme="dark"` attribute.
 *
 * Why this exists:
 *   - next-themes is configured with `attribute="data-theme"` because the
 *     app has many `[data-theme="dark"]` CSS selectors in globals.css.
 *   - Tailwind v4 `dark:` variants only fire when `<html class="dark">`.
 *   - We need both to work simultaneously.
 *
 * This component reads the resolved theme (light/dark) and toggles the
 * `dark` class on the html element. It runs only on the client and only
 * after hydration to avoid SSR/CSR class mismatch warnings.
 */
import { useEffect } from 'react';
import { useTheme } from 'next-themes';

export function ThemeSync() {
    const { resolvedTheme } = useTheme();

    useEffect(() => {
        if (typeof document === 'undefined') return;
        const root = document.documentElement;
        if (resolvedTheme === 'dark') {
            root.classList.add('dark');
        } else {
            root.classList.remove('dark');
        }
    }, [resolvedTheme]);

    return null;
}
