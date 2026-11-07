/**
 * Sidebar.tsx — Production-grade primary navigation.
 *
 * Desktop:
 *   - 260px fixed sidebar, collapsible to hidden via top-left toggle.
 *   - Grouped sections (Study / AI Tools / Resources / Account) + admin.
 *     The learner's order and hidden links come from Settings > Customise
 *     (lib/preferences.ts); hidden links are listed under "More".
 *   - Active route highlighted with primary-tinted border + soft bg.
 *
 * Mobile (<768px):
 *   - Slide-in drawer with translucent backdrop + backdrop blur.
 *   - Sticky header inside drawer (logo + close button).
 *   - Footer pinned to bottom with quick tip + sign out.
 *   - Scroll position persists across route changes.
 */
'use client';
import { useState, useEffect, useMemo, useRef } from 'react';
import Link from 'next/link';
import dynamic from 'next/dynamic';
import { usePathname, useRouter } from 'next/navigation';
import { useAuth } from '@/lib/auth';
import { navigateAfterAuthChange } from '@/lib/authNavigation';
import { navItemAvailable, resolveNavHref, sidebarLayout, type NavItemDef } from '@/lib/preferences';
import { useUiPreferences } from '@/components/customize/usePreferences';
import { Menu, X, PanelLeftClose, PanelLeftOpen, ShieldAlert, FileQuestion, Megaphone, Briefcase, LogOut, LogIn, Sparkles, ChevronRight, ChevronDown, BarChart3, Lock, FileUp, Layers, ClipboardCheck, Newspaper, Ellipsis, SlidersHorizontal, Ticket, type LucideIcon } from 'lucide-react';
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

// The student sections and links (Study / AI Tools / Resources / Account),
// their ids and the exam-track player hrefs live in lib/preferences.ts: the
// learner may reorder sections and links and hide links (Settings >
// Customise, stored per user on the server). Hidden links stay reachable in
// the "More" group below. The Admin group (ADMIN_LINKS) is not customisable.

const TRACK_LABEL: Record<string, string> = {
    cms: 'UPSC CMS',
    neet_pg: 'NEET PG',
    usmle: 'USMLE',
    fmge: 'FMGE',
    ini_cet: 'INI-CET',
};

/** Keep the current page's link visible: on a 900px-tall screen the
 *  Account and Admin groups sit below the fold, so on /trends or /admin
 *  nothing highlighted was in view. Adjusts only the nav's own scroll
 *  (scrollIntoView could also scroll the page). A link inside the closed
 *  "More" group has no box and is left alone. */
function revealActiveLink(nav: HTMLElement): void {
    const active = nav.querySelector<HTMLElement>('[aria-current="page"]');
    if (!active || active.getClientRects().length === 0) return;
    const navBox = nav.getBoundingClientRect();
    const linkBox = active.getBoundingClientRect();
    if (linkBox.bottom > navBox.bottom) nav.scrollTop += linkBox.bottom - navBox.bottom + 12;
    else if (linkBox.top < navBox.top) nav.scrollTop -= navBox.top - linkBox.top + 12;
}

/** Admin tools. A link is active on its own route and its sub-routes
 *  (except the /admin dashboard, which would otherwise match every tool). */
const ADMIN_LINKS: { href: string; label: string; icon: LucideIcon; exact?: boolean }[] = [
    { href: '/admin', label: 'Admin Dashboard', icon: ShieldAlert, exact: true },
    { href: '/admin/analytics-dashboard', label: 'Analytics Dashboard', icon: BarChart3 },
    { href: '/admin/questions-editor', label: 'Questions Editor', icon: FileQuestion },
    { href: '/admin/review-queue', label: 'Answer-Key Review', icon: ClipboardCheck },
    { href: '/admin/announcements', label: 'Announcements', icon: Megaphone },
    { href: '/admin/blog', label: 'Blog', icon: Newspaper },
    { href: '/admin/coupons', label: 'Coupon Codes', icon: Ticket },
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
    const { prefs } = useUiPreferences();
    const router = useRouter();
    const [open, setOpen] = useState(false);
    // The "More" group (hidden links) starts closed.
    const [moreOpen, setMoreOpen] = useState(false);
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
        revealActiveLink(nav);
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
            // Full page load: drop the router cache built while signed in (lib/authNavigation.ts).
            navigateAfterAuthChange('/');
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

    // The learner's order; hidden links go to "More". Admin-only and
    // exam-track links are filtered as before, in both places, and a section
    // left without links is not shown.
    const layout = useMemo(() => sidebarLayout(prefs.sidebar), [prefs.sidebar]);
    const viewer = { isAdmin: !!isAdmin, track: effectiveTrack };
    const sections = layout.sections
        .map((section) => ({ ...section, items: section.items.filter((item) => navItemAvailable(item, viewer)) }))
        .filter((section) => section.items.length > 0);
    const moreItems = layout.more.filter((item) => navItemAvailable(item, viewer));

    const isItemActive = (item: NavItemDef) => {
        // Resolve /questions for tracks with a dedicated player (NEET PG +
        // INI-CET) so users land on the new player instead of the
        // (UPSC-CMS-style) bank.
        const resolvedHref = resolveNavHref(item.href, effectiveTrack);
        return pathname === resolvedHref
            || pathname?.startsWith(resolvedHref + '/')
            || (resolvedHref === '/questions' && (pathname === '/questions' || pathname?.startsWith('/questions/')));
    };
    // On a page whose link is hidden, open "More" so the current page shows.
    const moreHasActive = moreItems.some(isItemActive);
    useEffect(() => {
        if (moreHasActive) setMoreOpen(true);
    }, [moreHasActive]);
    // Once "More" is open, bring that link into view (it had no box while closed).
    useEffect(() => {
        if (moreOpen && moreHasActive && navRef.current) revealActiveLink(navRef.current);
    }, [moreOpen, moreHasActive]);

    useEffect(() => {
        if (typeof document === 'undefined') return;
        document.body.style.overflow = open ? 'hidden' : '';
        return () => {
            document.body.style.overflow = '';
        };
    }, [open]);

    const renderNavLink = (item: NavItemDef) => {
        const resolvedHref = resolveNavHref(item.href, effectiveTrack);
        const isActive = isItemActive(item);
        // Freemium (Task 10): free users see a small
        // "Premium" pill next to the label, but the link
        // is still clickable — visibility of premium
        // features is part of the conversion funnel.
        // The page itself enforces the gate; the
        // api.ts interceptor opens the UpgradeModal.
        const showLock = !isPremium && item.premium === true;
        const handleClick = () => {
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
                key={item.id}
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
                {/* No chevron next to the lock or the AI badge: either
                    one plus the chevron clipped "Question Generator"
                    to "Question Genera..." on its own page. */}
                {isActive && !showLock && !item.badge && <ChevronRight className="sidebar-label w-3.5 h-3.5 shrink-0 opacity-70" />}
            </Link>
        );
    };

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
                        {sections.map((section) => (
                            <div key={section.id}>
                                <div className="section-title sidebar-section-title mb-1.5">{section.title}</div>
                                <div className="space-y-0.5">
                                    {section.items.map(renderNavLink)}
                                </div>
                            </div>
                        ))}

                        {/* More: the links the learner hid (Settings > Customise).
                            Same links, locks and exam-track rules as above. */}
                        {moreItems.length > 0 && (
                            <div>
                                <button
                                    type="button"
                                    onClick={() => setMoreOpen((value) => !value)}
                                    aria-expanded={moreOpen}
                                    aria-controls="sidebar-more-links"
                                    title={`More (${moreItems.length} hidden ${moreItems.length === 1 ? 'link' : 'links'})`}
                                    className="sidebar-link w-full"
                                >
                                    <Ellipsis className="w-5 h-5 shrink-0" aria-hidden="true" />
                                    <span className="sidebar-label text-sm flex-1 text-left">More</span>
                                    <span className="sidebar-label shrink-0 rounded-full bg-muted px-1.5 py-0.5 text-[10px] font-semibold text-muted-foreground" aria-hidden="true">
                                        {moreItems.length}
                                    </span>
                                    <ChevronDown
                                        className={`sidebar-label w-3.5 h-3.5 shrink-0 transition-transform ${moreOpen ? 'rotate-180' : ''}`}
                                        aria-hidden="true"
                                    />
                                </button>
                                <div id="sidebar-more-links" hidden={!moreOpen} className="mt-0.5 space-y-0.5">
                                    {moreItems.map(renderNavLink)}
                                    <Link
                                        href="/settings#customise"
                                        onClick={() => { saveSidebarScroll(); setOpen(false); }}
                                        prefetch={false}
                                        title="Customise the sidebar"
                                        className="sidebar-link"
                                    >
                                        <SlidersHorizontal className="w-5 h-5 shrink-0" aria-hidden="true" />
                                        <span className="sidebar-label text-sm">Customise sidebar</span>
                                    </Link>
                                </div>
                            </div>
                        )}

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
                        // Red text/hover from the utilities: .sidebar-link sits in
                        // @layer components (globals.css), so they now apply; the
                        // unlayered rule used to turn Sign Out grey.
                        <button
                            onClick={handleLogout}
                            aria-label="Sign out"
                            title="Sign out"
                            className="sidebar-link w-full text-destructive hover:text-destructive hover:bg-destructive/10 hover:border-destructive/25"
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
