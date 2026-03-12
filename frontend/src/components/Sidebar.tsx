/**
 * Sidebar.tsx — Main navigation sidebar for CrackCMS.
 * Grouped navigation, responsive (collapses on tablet, hidden on mobile).
 */
'use client';
import { useState, useEffect } from 'react';
import Link from 'next/link';
import { usePathname, useRouter } from 'next/navigation';
import { useAuth } from '@/lib/auth';
import {
    LayoutDashboard, BookOpen, FileText, Brain,
    BarChart3, GraduationCap, Bookmark, LogOut,
    Zap, Map, FolderOpen, Upload, Sparkles,
    Menu, X, TrendingUp, MessageSquare, Trophy,
    Shield, Layers
} from 'lucide-react';
import { Separator } from '@/components/ui/separator';

const navSections = [
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
            { href: '/roadmap', icon: Map, label: 'Study Roadmap' },
        ]
    },
    {
        title: 'Resources',
        items: [
            { href: '/resources', icon: FolderOpen, label: 'Resources' },
            { href: '/textbooks', icon: BookOpen, label: 'Textbooks' },
            { href: '/trends', icon: TrendingUp, label: 'Exam Trends' },
            { href: '/upload', icon: Upload, label: 'Upload & Train' },
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

    useEffect(() => { setOpen(false); }, [pathname]);
    useEffect(() => {
        const handler = (e: KeyboardEvent) => { if (e.key === 'Escape') setOpen(false); };
        window.addEventListener('keydown', handler);
        return () => window.removeEventListener('keydown', handler);
    }, []);

    const handleLogout = () => {
        logout();
        router.push('/');
    };

    const isAdmin = user?.role === 'admin';

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
                <div className="flex items-center gap-3 px-5 mb-4">
                    <div className="w-9 h-9 rounded-lg flex items-center justify-center bg-primary">
                        <Zap className="w-5 h-5 text-primary-foreground" />
                    </div>
                    <span className="sidebar-label text-lg font-bold gradient-text">CrackCMS</span>
                </div>

                <Separator className="mb-3" />

                {/* Nav Links */}
                <nav className="flex-1 overflow-y-auto overscroll-contain px-1" style={{ scrollbarWidth: 'thin' }}>
                    <div className="space-y-4">
                        {navSections.map((section) => (
                            <div key={section.title}>
                                <div className="section-title sidebar-section-title mb-2">{section.title}</div>
                                <div className="space-y-0.5">
                                    {section.items.map((item) => {
                                        const isActive = pathname === item.href || pathname?.startsWith(item.href + '/');
                                        return (
                                            <Link key={item.href} href={item.href} className={`sidebar-link ${isActive ? 'active' : ''}`}>
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
                                    <Link href="/admin" className={`sidebar-link ${pathname?.startsWith('/admin') ? 'active' : ''}`}>
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
                    <button onClick={handleLogout} className="sidebar-link w-full text-destructive hover:text-destructive hover:bg-destructive/10">
                        <LogOut className="w-[18px] h-[18px]" />
                        <span className="sidebar-label text-sm">Logout</span>
                    </button>
                </div>
            </div>
        </>
    );
}
