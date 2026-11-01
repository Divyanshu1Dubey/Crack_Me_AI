/**
 * Sidebar.tsx — Production-grade primary navigation.
 *
 * Desktop:
 *   - 260px fixed sidebar, collapsible to hidden via top-left toggle.
 *   - Grouped sections (Study / AI Tools / Resources / Account) + admin.
 *   - Active route highlighted with primary-tinted border + soft bg.
 *
 * Mobile (<768px):
 *   - Slide-in drawer with translucent backdrop + backdrop blur.
 *   - Sticky header inside drawer (logo + close button).
 *   - Footer pinned to bottom with quick tip + sign out.
 *   - Scroll position persists across route changes.
 */
'use client';
import { useState, useEffect, useRef } from 'react';
import Link from 'next/link';
import dynamic from 'next/dynamic';
import { usePathname, useRouter } from 'next/navigation';
import { useAuth } from '@/lib/auth';
import { Menu, X, PanelLeftClose, PanelLeftOpen, ShieldAlert, FileQuestion, Megaphone, Briefcase, LogOut, LogIn, Sparkles, ChevronRight, BarChart3, Lock, FileUp, Layers, type LucideIcon } from 'lucide-react';
import { Separator } from '@/components/ui/separator';
import BrandMark from '@/components/BrandMark';
import CustomIcon from '@/components/CustomIcon';
import { useExamTrack } from '@/components/ExamTrackProvider';
import { decodeMojiB } from '@/lib/textCleanup';
import { useSidebar } from '@/context/SidebarContext';
import { usePaywall } from '@/lib/paywall/paywallContext';

// Same lazy, client-only toggle as the Header (it reads the resolved theme).
const ThemeToggle = dynamic(() => import('@/components/ThemeToggle'), {
    ssr: false,
    loading: () => <div className="h-[34px] w-[34px]" aria-hidden="true" />,
});

interface NavItem {
    href: string;
    iconName: string;
    label: string;
    badge?: string;
    adminOnly?: boolean;
    requireTrack?: string[];
    /** Freemium gate (Task 10): if true, free users see a lock icon next to
     *  the label, and clicking opens the UpgradeModal. Premium + admin
     *  users see no lock and the link is fully clickable. */
    premium?: boolean;
    /** Display label used in the upgrade modal trigger — defaults to `label`. */
    premiumFeature?: string;
}

interface NavSection {
    title: string;
    items: NavItem[];
}

const navSections: NavSection[] = [
    {
        title: 'Study',
        items: [
            { href: '/dashboard', iconName: 'dashboard-layout', label: 'Dashboard' },
            // Freemium: free users get a "Premium" badge next to Question Bank
            // but the link still routes — clicks inside the bank hit the
            // backend filter (Task 6) which restricts to 10 showcase items.
            { href: '/questions', iconName: 'question-bank-book', label: 'Question Bank', premium: true, premiumFeature: 'Full PYQ practice' },
            { href: '/tests', iconName: 'tests-check', label: 'Tests', premium: true, premiumFeature: 'Mock Tests' },
            { href: '/flashcards', iconName: 'flashcards-cards', label: 'Flashcards', premium: true, premiumFeature: 'Flashcards' },
            { href: '/simulator', iconName: 'simulator-target', label: 'CMS Simulator', premium: true, premiumFeature: 'Mock Tests' },
            { href: '/mistake-notebook', iconName: 'book-open', label: 'Mistake Notebook' },
            { href: '/study-time', iconName: 'clock', label: 'Study Time' },
        ]
    },
    {
        title: 'AI Tools',
        items: [
            { href: '/ai-tutor', iconName: 'ai-tutor-brain', label: 'AI Tutor', badge: 'AI', premium: true, premiumFeature: 'AI Tutor' },
            { href: '/generate', iconName: 'ai-questions-creativity', label: 'Question Generator', badge: 'AI', premium: true, premiumFeature: 'AI Tutor' },
            // Same name as the page heading and the Header title.
            { href: '/roadmap', iconName: 'study-roadmap-map', label: 'Study Roadmap', badge: 'AI', premium: true, premiumFeature: 'AI Tutor' },
        ]
    },
    {
        title: 'Resources',
        items: [
            { href: '/resources', iconName: 'resources-folder', label: 'Resources' },
            { href: '/textbooks', iconName: 'textbooks-open-book', label: 'Textbooks' },
            { href: '/jobs', iconName: 'briefcase', label: 'Jobs Portal', requireTrack: ['cms'] },
            { href: '/trends', iconName: 'trends-graph', label: 'Exam Trends' },
            { href: '/upload', iconName: 'upload-train', label: 'Upload & Train', adminOnly: true },
        ]
    },
    {
        title: 'Account',
        items: [
            // Analytics is open to every signed-in user: no Deep Analytics
            // gate was ever built (no 402, no locked state on /analytics), so
            // a lock here only opened the upgrade modal on a free page (AN-08).
            { href: '/analytics', iconName: 'analytics-growth', label: 'Analytics' },
            { href: '/leaderboard', iconName: 'leaderboard-trophy', label: 'Leaderboard' },
            { href: '/bookmarks', iconName: 'bookmarks-ribbon', label: 'Bookmarks' },
            { href: '/subscription', iconName: 'subscription-gold', label: 'Subscription' },
            { href: '/feedback', iconName: 'feedback-chat', label: 'Feedback' },
            { href: '/contact', iconName: 'contact-support', label: 'Contact Us' },
            { href: '/quests', iconName: 'flame', label: 'Quests' },
            { href: '/topic-notes', iconName: 'file-text', label: 'Topic Notes' },
        ]
    },
];

const TRACK_LABEL: Record<string, string> = {
    cms: 'UPSC CMS',
    neet_pg: 'NEET PG',
    usmle: 'USMLE',
    fmge: 'FMGE',
    ini_cet: 'INI-CET',
};

/** Map generic /questions href → exam-specific dedicated player URL.
 *  Phase 9: each exam with image-rich recalls gets its own player route. */
const EXAM_TRACK_PLAYER_HREF: Record<string, string> = {
    neet_pg: '/questions/neet-pg/practice',
    ini_cet: '/questions/inicet/practice',
};

/** Admin tools. A link is active on its own route and its sub-routes
 *  (except the /admin dashboard, which would otherwise match every tool). */
const ADMIN_LINKS: { href: string; label: string; icon: LucideIcon; exact?: boolean }[] = [
    { href: '/admin', label: 'Admin Dashboard', icon: ShieldAlert, exact: true },
    { href: '/admin/analytics-dashboard', label: 'Analytics Dashboard', icon: BarChart3 },
    { href: '/admin/questions-editor', label: 'Questions Editor', icon: FileQuestion },
    { href: '/admin/announcements', label: 'Announcements', icon: Megaphone },
    { href: '/admin/jobs', label: 'Manage Jobs', icon: Briefcase },
    { href: '/admin/ingestion', label: 'Ingestion', icon: FileQuestion },
    // Import Center and Recall had no link anywhere in the app.
    { href: '/admin/import-center', label: 'Import Center', icon: FileUp },
    { href: '/admin/recall', label: 'Recall Admin', icon: Layers },
];

export default function Sidebar() {
    const pathname = usePathname();
    const { user, logout, loading: authLoading } = useAuth();
    const { activeTrack, hydrated } = useExamTrack();
    const { show: showPaywall } = usePaywall();
    const router = useRouter();
    const [open, setOpen] = useState(false);
    const navRef = useRef<HTMLElement | null>(null);
    const SIDEBAR_SCROLL_KEY = 'crackcms_sidebar_scroll_top';
    // Desktop visibility is now owned by SidebarContext so route-level
    // controllers (e.g. SidebarAutoHide on /questions) can flip it without
    // duplicating localStorage / body-class side effects.
    const { desktopOpen, setDesktopOpen } = useSidebar();

    useEffect(() => {
        const handler = (e: KeyboardEvent) => { if (e.key === 'Escape') setOpen(false); };
        window.addEventListener('keydown', handler);
        return () => window.removeEventListener('keydown', handler);
    }, []);

    // Cleanup the sidebar-hidden body class on unmount so we don't leak
    // the class when this sidebar instance goes away (e.g. user navigates
    // to a route that doesn't render Sidebar). The context re-applies the
    // class on its own desktopOpen effect if another Sidebar instance is
    // mounted, so this is safe.
    useEffect(() => {
        return () => {
            if (typeof document !== 'undefined') {
                document.body.classList.remove('sidebar-hidden');
            }
        };
    }, []);

    useEffect(() => {
        if (typeof window === 'undefined') return;
        const nav = navRef.current;
        if (!nav) return;
        const saved = window.sessionStorage.getItem(SIDEBAR_SCROLL_KEY);
        if (saved) {
            const top = Number(saved);
            if (!Number.isNaN(top)) nav.scrollTop = top;
        }
        // Keep the current page's link visible: on a 900px-tall screen the
        // Account and Admin groups sit below the fold, so on /trends or
        // /admin nothing highlighted was in view. Adjusts only the nav's own
        // scroll (scrollIntoView could also scroll the page).
        const active = nav.querySelector<HTMLElement>('[aria-current="page"]');
        if (active) {
            const navBox = nav.getBoundingClientRect();
            const linkBox = active.getBoundingClientRect();
            if (linkBox.bottom > navBox.bottom) nav.scrollTop += linkBox.bottom - navBox.bottom + 12;
            else if (linkBox.top < navBox.top) nav.scrollTop -= navBox.top - linkBox.top + 12;
        }
        // Close drawer on route change so it doesn't stay open.
        setOpen(false);
    }, [pathname]);

    const saveSidebarScroll = () => {
        if (typeof window === 'undefined') return;
        const nav = navRef.current;
        if (!nav) return;
        window.sessionStorage.setItem(SIDEBAR_SCROLL_KEY, String(nav.scrollTop));
    };

    // Wait for the sign-out to finish: navigating first let the next route
    // still see the session and bounce the user back in (AUTH-08).
    const handleLogout = async () => {
        try {
            await logout();
        } finally {
            router.push('/');
        }
    };

    const isAdmin = user?.role === 'admin' || user?.is_admin;
    // Freemium (Task 10): a user is "premium" if they have an active
    // subscription OR are admin/staff. Mirrors the backend source of truth
    // (`accounts.utils.is_premium`); `user.is_premium` is already on the
    // /api/auth/profile/ payload (Task 9) so we read it here without an
    // extra request. Falls back to subscription_info for legacy sessions.
    const isPremium =
        isAdmin ||
        user?.is_premium === true ||
        user?.subscription_info?.is_active === true;
    // IMPORTANT: only honour the activeTrack from the provider AFTER hydration.
    // Until then the server-rendered HTML used 'cms' (the default), so the
    // /questions href on the client must also be '/questions' to avoid React
    // #418 hydration mismatches. Once `hydrated` flips, we re-render with
    // the real exam-specific player URL.
    const effectiveTrack = hydrated ? activeTrack : 'cms';
    const trackLabel = TRACK_LABEL[effectiveTrack] || effectiveTrack;

    useEffect(() => {
        if (typeof document === 'undefined') return;
        document.body.style.overflow = open ? 'hidden' : '';
        return () => {
            document.body.style.overflow = '';
        };
    }, [open]);

    return (
        <>
            {/* Desktop sidebar toggle (top-left, only on desktop) */}
            <button
                className="desktop-sidebar-toggle-btn"
                aria-label={desktopOpen ? 'Hide sidebar' : 'Show sidebar'}
                onClick={() => setDesktopOpen(!desktopOpen)}
            >
                {desktopOpen ? <PanelLeftClose className="w-5 h-5" /> : <PanelLeftOpen className="w-5 h-5" />}
            </button>

            {/* Mobile menu button (floating, top-left) */}
            <button
                className="mobile-menu-btn"
                onClick={() => setOpen(!open)}
                aria-label={open ? 'Close menu' : 'Open menu'}
                aria-expanded={open}
            >
                {open ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
            </button>

            {/* Mobile overlay */}
            <div
                className={`sidebar-overlay ${open ? 'active' : ''}`}
                onClick={() => setOpen(false)}
                aria-hidden={!open}
            />

            <aside
                className={`sidebar ${open ? 'open' : ''} ${desktopOpen ? '' : 'desktop-hidden'}`}
                aria-label="Primary sidebar navigation"
            >
                {/* Mobile drawer header — visible only on phones.
                    Provides logo + close button so the drawer has a clear
                    chrome instead of looking like the page content. */}
                <div className="sidebar-mobile-header">
                    <div className="flex items-center gap-2 min-w-0">
                        <BrandMark href="/dashboard" compact className="min-w-0" />
                    </div>
                    <div className="flex shrink-0 items-center gap-1.5">
                        {/* The phone header has no room for the theme toggle. */}
                        <ThemeToggle />
                        <button
                            type="button"
                            onClick={() => setOpen(false)}
                            aria-label="Close menu"
                            className="flex items-center justify-center w-9 h-9 rounded-xl border border-border bg-background text-foreground hover:bg-muted transition-colors"
                        >
                            <X className="w-4 h-4" />
                        </button>
                    </div>
                </div>

                {/* Desktop logo block */}
                <div className="sidebar-brand hidden md:block px-4 pt-4 pb-3">
                    <div className="sidebar-brand-card rounded-2xl border border-border bg-linear-to-br from-primary/10 via-sky-500/10 to-teal-500/10 p-3">
                        <BrandMark href="/dashboard" className="min-w-0" />
                        <div className="sidebar-label mt-3 inline-flex items-center gap-1.5 rounded-full border border-border bg-background/70 px-2.5 py-1 text-[10px] font-semibold text-muted-foreground dark:text-slate-300">
                            <CustomIcon name="medical-stethoscope" label="Medical" className="w-3 h-3" variant="subtle" />
                            {decodeMojiB(trackLabel)}
                        </div>
                    </div>
                </div>

                <Separator className="mb-2" />

                {/* Nav links */}
                <nav
                    ref={navRef}
                    onScroll={saveSidebarScroll}
                    className="flex-1 overflow-y-auto overscroll-contain px-1"
                    style={{ scrollbarWidth: 'thin' }}
                >
                    <div className="space-y-4 pb-2">
                        {navSections.map((section) => (
                            <div key={section.title}>
                                <div className="section-title sidebar-section-title mb-1.5">{section.title}</div>
                                <div className="space-y-0.5">
                                    {section.items
                                        .filter(item => !item.adminOnly || isAdmin)
                                        .filter(item => !item.requireTrack || item.requireTrack.includes(effectiveTrack))
                                        .map((item) => {
                                            // Resolve /questions for tracks with a dedicated
                                            // player (NEET PG + INI-CET) so users land on the
                                            // new player instead of the (UPSC-CMS-style) bank.
                                            const resolvedHref = item.href === '/questions' && EXAM_TRACK_PLAYER_HREF[effectiveTrack]
                                                ? EXAM_TRACK_PLAYER_HREF[effectiveTrack]
                                                : item.href;
                                            const isActive = pathname === resolvedHref
                                                || pathname?.startsWith(resolvedHref + '/')
                                                || (resolvedHref === '/questions' && (pathname === '/questions' || pathname?.startsWith('/questions/')));
                                            // Freemium (Task 10): free users see a small
                                            // "Premium" pill next to the label, but the link
                                            // is still clickable — visibility of premium
                                            // features is part of the conversion funnel.
                                            // The page itself enforces the gate; the
                                            // api.ts interceptor opens the UpgradeModal.
                                            const showLock = !isPremium && item.premium === true;
                                            const handleClick = (e: React.MouseEvent<HTMLAnchorElement>) => {
                                                saveSidebarScroll();
                                                setOpen(false);
                                                if (showLock) {
                                                    // Free user clicking a premium link — open
                                                    // the upgrade modal explicitly so they get a
                                                    // nudge before the page itself gates them.
                                                    showPaywall(item.premiumFeature || item.label);
                                                }
                                            };
                                            return (
                                                <Link
                                                    key={item.href}
                                                    href={resolvedHref}
                                                    onClick={handleClick}
                                                    prefetch={false}
                                                    className={`sidebar-link ${isActive ? 'active' : ''}`}
                                                    aria-current={isActive ? 'page' : undefined}
                                                    // Tooltip for the icon-only tablet rail and the lock icon.
                                                    title={showLock ? `${item.label} (Premium)` : item.label}
                                                    aria-label={showLock ? `${item.label} (Premium)` : undefined}
                                                >
                                                    <CustomIcon
                                                        name={item.iconName}
                                                        label={item.label}
                                                        className="shrink-0"
                                                        size={18}
                                                        variant={isActive ? 'active' : 'default'}
                                                    />
                                                    <span className="sidebar-label text-sm flex-1 truncate">{item.label}</span>
                                                    {showLock && (
                                                        <>
                                                            {/* A lock icon (the PREMIUM pill truncated labels to
                                                                "Question Ba..."); a dot in the 72px tablet rail. */}
                                                            <span className="sidebar-label shrink-0 text-amber-600 dark:text-amber-400" aria-hidden="true">
                                                                <Lock className="h-3.5 w-3.5" />
                                                            </span>
                                                            <span className="sidebar-rail-lock" aria-hidden="true" />
                                                        </>
                                                    )}
                                                    {item.badge && !showLock && (
                                                        <span className="sidebar-label text-[9px] font-bold uppercase tracking-wider rounded px-1.5 py-0.5 bg-primary/15 text-primary">
                                                            {item.badge}
                                                        </span>
                                                    )}
                                                    {/* No chevron next to the lock: both together clipped
                                                        "Question Generator" when it was the active page. */}
                                                    {isActive && !showLock && <ChevronRight className="sidebar-label w-3.5 h-3.5 shrink-0 opacity-70" />}
                                                </Link>
                                            );
                                        })}
                                </div>
                            </div>
                        ))}

                        {/* Admin */}
                        {isAdmin && (
                            <div>
                                <div className="section-title sidebar-section-title mb-1.5">
                                    <ShieldAlert className="w-3 h-3 inline mr-1" />
                                    Admin
                                </div>
                                <div className="space-y-0.5">
                                    {ADMIN_LINKS.map(({ href, label, icon: Icon, exact }) => {
                                        const isActive = pathname === href || (!exact && !!pathname?.startsWith(`${href}/`));
                                        return (
                                            <Link
                                                key={href}
                                                href={href}
                                                onClick={() => { saveSidebarScroll(); setOpen(false); }}
                                                className={`sidebar-link ${isActive ? 'active' : ''}`}
                                                aria-current={isActive ? 'page' : undefined}
                                                title={label}
                                            >
                                                <Icon className="w-5 h-5 shrink-0" />
                                                <span className="sidebar-label text-sm">{label}</span>
                                            </Link>
                                        );
                                    })}
                                </div>
                            </div>
                        )}
                    </div>
                </nav>

                {/* Footer — pinned to bottom */}
                <div className="mt-auto px-2 pb-3 pt-2">
                    <Separator className="mb-3" />
                    {/* Hidden on short screens (<=900px tall) so the nav keeps
                        room for more links above the fold. */}
                    <div className="sidebar-label mx-2 mb-2 rounded-xl border border-border bg-muted/50 px-3 py-2 [@media(max-height:900px)]:hidden">
                        <p className="text-[11px] font-semibold text-foreground flex items-center gap-1.5">
                            <Sparkles className="w-3 h-3 text-amber-500" /> Quick Tip
                        </p>
                        <p className="mt-1 text-[10px] leading-relaxed text-muted-foreground dark:text-slate-300">
                            Take one timed test daily and review your top 3 weak tags.
                        </p>
                    </div>
                    {!authLoading && !user ? (
                        // Visitors on public app-shell pages (/resources, /contact)
                        // were offered "Sign Out" although they were not signed in.
                        <Link
                            href={`/login?next=${encodeURIComponent(pathname || '/dashboard')}`}
                            onClick={() => setOpen(false)}
                            title="Sign in"
                            className="sidebar-link w-full"
                        >
                            <LogIn className="w-5 h-5 shrink-0" />
                            <span className="sidebar-label text-sm">Sign In</span>
                        </Link>
                    ) : (
                        <button
                            onClick={handleLogout}
                            aria-label="Sign out"
                            title="Sign out"
                            className="sidebar-link w-full text-destructive hover:text-destructive hover:bg-destructive/10"
                        >
                            <LogOut className="w-5 h-5 shrink-0" />
                            <span className="sidebar-label text-sm">Sign Out</span>
                        </button>
                    )}
                </div>
            </aside>
        </>
    );
}
