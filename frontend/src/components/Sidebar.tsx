/**
 * Sidebar.tsx — Main navigation sidebar for CrackCMS.
 * Grouped navigation, responsive (collapses on tablet, hidden on mobile).
 */
'use client';
import { useState, useEffect } from 'react';
import { useRef } from 'react';
import Link from 'next/link';
import { usePathname, useRouter } from 'next/navigation';
import { useAuth } from '@/lib/auth';
import {
    LayoutDashboard, BookOpen, FileText, Brain,
    BarChart3, GraduationCap, Bookmark, LogOut,
    Map, FolderOpen, Upload, Sparkles,
    Menu, X, TrendingUp, MessageSquare, Trophy,
    Shield, Layers, Stethoscope
} from 'lucide-react';
import { Separator } from '@/components/ui/separator';
import BrandMark from '@/components/BrandMark';

interface NavItem {
    href: string;
    icon: React.ComponentType<{ className?: string }>;
    label: string;
    adminOnly?: boolean;
}

interface NavSection {
    title: string;
    items: NavItem[];
}

const navSections: NavSection[] = [
    {
        title: 'Study',
        items: [
            { href: '/dashboard', icon: LayoutDashboard, label: 'Dashboard' },
            { href: '/questions', icon: BookOpen, label: 'Question Bank' },
            { href: '/tests', icon: FileText, label: 'Tests' },
            { href: '/flashcards', icon: Layers, label: 'Flashcards' },
            { href: '/simulator', icon: GraduationCap, label: 'CMS Simulator' },
        ]
    },
    {
        title: 'AI Tools',
        items: [
            { href: '/ai-tutor', icon: Brain, label: 'AI Tutor' },
            { href: '/generate', icon: Sparkles, label: 'AI Questions' },
            { href: '/roadmap', icon: Map, label: 'AI Study Plan' },
        ]
    },
    {
        title: 'Resources',
        items: [
            { href: '/resources', icon: FolderOpen, label: 'Resources' },
            { href: '/textbooks', icon: BookOpen, label: 'Textbooks' },
            { href: '/trends', icon: TrendingUp, label: 'Exam Trends' },
            { href: '/upload', icon: Upload, label: 'Upload & Train', adminOnly: true },
        ]
    },
    {
        title: 'Account',
        items: [
            { href: '/analytics', icon: BarChart3, label: 'Analytics' },
            { href: '/leaderboard', icon: Trophy, label: 'Leaderboard' },
            { href: '/bookmarks', icon: Bookmark, label: 'Bookmarks' },
            { href: '/feedback', icon: MessageSquare, label: 'Feedback' },
        ]
    },
];

export default function Sidebar() {
    const pathname = usePathname();
    const { user, logout } = useAuth();
    const router = useRouter();
    const [open, setOpen] = useState(false);
    const navRef = useRef<HTMLElement | null>(null);
    const SIDEBAR_SCROLL_KEY = 'crackcms_sidebar_scroll_top';

    useEffect(() => {
        const handler = (e: KeyboardEvent) => { if (e.key === 'Escape') setOpen(false); };
        window.addEventListener('keydown', handler);
        return () => window.removeEventListener('keydown', handler);
    }, []);

    useEffect(() => {
        if (typeof window === 'undefined') return;
        const nav = navRef.current;
        if (!nav) return;

        const saved = window.sessionStorage.getItem(SIDEBAR_SCROLL_KEY);
        if (saved) {
            const top = Number(saved);
            if (!Number.isNaN(top)) {
                nav.scrollTop = top;
            }
        }
    }, [pathname]);

    const saveSidebarScroll = () => {
        if (typeof window === 'undefined') return;
        const nav = navRef.current;
        if (!nav) return;
        window.sessionStorage.setItem(SIDEBAR_SCROLL_KEY, String(nav.scrollTop));
    };

    const handleLogout = () => {
        logout();
        router.push('/');
    };

    const isAdmin = user?.role === 'admin' || user?.is_admin;

    return (
        <>
            {/* Mobile menu button */}
            <button className="mobile-menu-btn" onClick={() => setOpen(!open)} aria-label="Toggle menu">
                {open ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
            </button>
            {/* Mobile overlay */}
            <div className={`sidebar-overlay ${open ? 'active' : ''}`} onClick={() => setOpen(false)} />

            <div className={`sidebar ${open ? 'open' : ''}`} style={{ display: 'flex', flexDirection: 'column' }}>
                {/* Logo */}
                <div className="px-4 pt-2 pb-3">
                    <div className="rounded-2xl border border-border bg-gradient-to-br from-primary/10 via-sky-500/10 to-teal-500/10 p-3">
                        <BrandMark href="/dashboard" className="min-w-0" />
                        <div className="sidebar-label mt-3 inline-flex items-center gap-1.5 rounded-full border border-border bg-background/70 px-2.5 py-1 text-[10px] font-semibold text-muted-foreground">
                            <Stethoscope className="w-3 h-3" />
                            Real Exam Workflow
                        </div>
                    </div>
                </div>

                <Separator className="mb-3" />

                {/* Nav Links */}
                <nav ref={navRef} onScroll={saveSidebarScroll} className="flex-1 overflow-y-auto overscroll-contain px-1" style={{ scrollbarWidth: 'thin' }}>
                    <div className="space-y-4">
                        {navSections.map((section) => (
                            <div key={section.title}>
                                <div className="section-title sidebar-section-title mb-2">{section.title}</div>
                                <div className="space-y-0.5">
                                    {section.items
                                        .filter(item => !item.adminOnly || isAdmin)
                                        .map((item) => {
                                        const isActive = pathname === item.href || pathname?.startsWith(item.href + '/');
                                        return (
                                            <Link key={item.href} href={item.href} onClick={() => { saveSidebarScroll(); setOpen(false); }} className={`sidebar-link ${isActive ? 'active' : ''}`}>
                                                <item.icon className="w-[18px] h-[18px] shrink-0" />
                                                <span className="sidebar-label text-sm">{item.label}</span>
                                            </Link>
                                        );
                                    })}
                                </div>
                            </div>
                        ))}

                        {/* Admin section */}
                        {isAdmin && (
                            <div>
                                <div className="section-title sidebar-section-title mb-2">Admin</div>
                                <div className="space-y-0.5">
                                    <Link href="/admin" onClick={() => { saveSidebarScroll(); setOpen(false); }} className={`sidebar-link ${pathname?.startsWith('/admin') ? 'active' : ''}`}>
                                        <Shield className="w-[18px] h-[18px] shrink-0" />
                                        <span className="sidebar-label text-sm">Admin Panel</span>
                                    </Link>
                                </div>
                            </div>
                        )}
                    </div>
                </nav>

                {/* Bottom — logout */}
                <div className="mt-auto px-2 pb-3 pt-2">
                    <Separator className="mb-3" />
                    <div className="sidebar-label mx-2 mb-2 rounded-xl border border-border bg-muted/50 px-3 py-2">
                        <p className="text-[11px] font-semibold text-foreground">Quick Tip</p>
                        <p className="mt-1 text-[10px] leading-relaxed text-muted-foreground">Take one timed test daily and review your top 3 weak tags.</p>
                    </div>
                    <button onClick={handleLogout} className="sidebar-link w-full text-destructive hover:text-destructive hover:bg-destructive/10">
                        <LogOut className="w-[18px] h-[18px]" />
                        <span className="sidebar-label text-sm">Sign Out</span>
                    </button>
                </div>
            </div>
        </>
    );
}
