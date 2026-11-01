'use client';

/**
 * PublicNav — the top navigation of the public (marketing) site: brand,
 * theme toggle, and Log in / Start Free (or Open Dashboard when signed in).
 *
 * - <PublicNavBar /> is the bar itself. The homepage renders it directly,
 *   under its exam-countdown banner.
 * - The default export is mounted once in the root layout and renders the
 *   bar only on public routes that have no header of their own (exam
 *   landings, guides, tools, blog, legal pages, /about — see
 *   publicNavRoutes.ts). Before this, those pages opened with a 12px
 *   breadcrumb: no logo, no way to log in and no theme toggle.
 */

import Link from 'next/link';
import dynamic from 'next/dynamic';
import { usePathname } from 'next/navigation';
import { ChevronRight } from 'lucide-react';
import BrandMark from '@/components/BrandMark';
import { Button } from '@/components/ui/button';
import { useAuth } from '@/lib/auth';
import { isPublicNavPath } from '@/components/publicNavRoutes';

const ThemeToggle = dynamic(() => import('@/components/ThemeToggle'), {
    ssr: false,
    loading: () => <div className="h-9 w-9 rounded-xl border border-border/70 bg-muted/60" aria-hidden="true" />,
});

export function PublicNavBar() {
    const { isAuthenticated } = useAuth();

    return (
        <nav
            aria-label="Main"
            className="sticky top-0 z-50 border-b border-border/40 bg-background/70 backdrop-blur-2xl supports-[backdrop-filter]:bg-background/60"
        >
            <div className="mx-auto flex h-16 max-w-7xl items-center justify-between gap-2 px-4 sm:px-6 lg:px-8">
                {/* The wordmark gives way on very narrow phones (<380px) so the buttons fit. */}
                <BrandMark href="/" compact showTagline={false} className="max-[379px]:[&_.brandmark-text]:hidden" />
                <div className="flex items-center gap-1.5 sm:gap-3">
                    <ThemeToggle />
                    {isAuthenticated ? (
                        <Button asChild className="rounded-xl font-semibold shadow-sm shadow-primary/10">
                            <Link href="/dashboard">
                                Open Dashboard <ChevronRight className="ml-1 h-4 w-4" />
                            </Link>
                        </Button>
                    ) : (
                        <>
                            <Button
                                variant="ghost"
                                asChild
                                className="px-2.5 font-medium text-muted-foreground hover:text-foreground sm:px-4"
                            >
                                <Link href="/login">Log in</Link>
                            </Button>
                            <Button
                                asChild
                                className="rounded-xl px-3 font-semibold shadow-lg shadow-primary/20 transition-all hover:scale-[1.02] hover:shadow-xl hover:shadow-primary/30 active:scale-[0.98] sm:px-4"
                            >
                                <Link href="/register">
                                    Start Free <ChevronRight className="ml-1 hidden h-4 w-4 sm:inline" />
                                </Link>
                            </Button>
                        </>
                    )}
                </div>
            </div>
        </nav>
    );
}

/** Root-layout mount: the bar on public routes without their own header. */
export default function PublicNav() {
    const pathname = usePathname();
    if (!isPublicNavPath(pathname)) return null;
    return <PublicNavBar />;
}
