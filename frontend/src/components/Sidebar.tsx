/**
 * Sidebar.tsx — Main navigation sidebar for CrackCMS.
 * Features: Logo, user card, AI token balance widget, nav links,
 * theme toggle, settings, and logout. Responsive with mobile hamburger menu.
 * Token balance auto-refreshes on every page navigation.
 */
'use client';
import { useState, useEffect } from 'react';
import Link from 'next/link';
import { usePathname, useRouter } from 'next/navigation';
import { useAuth } from '@/lib/auth';
import { authAPI } from '@/lib/api';
import {
    LayoutDashboard, BookOpen, FileText, Brain,
    BarChart3, GraduationCap, Bookmark, LogOut,
    Zap, Settings, Map, FolderOpen, Upload, Sparkles,
    Menu, X, TrendingUp, Coins, MessageSquare
} from 'lucide-react';
import ThemeToggle from '@/components/ThemeToggle';

const navItems = [
    { href: '/dashboard', icon: LayoutDashboard, label: 'Dashboard' },
    { href: '/questions', icon: BookOpen, label: 'Question Bank' },
    { href: '/tests', icon: FileText, label: 'Tests' },
    { href: '/ai-tutor', icon: Brain, label: 'AI Tutor' },
    { href: '/simulator', icon: GraduationCap, label: 'CMS Simulator' },
    { href: '/generate', icon: Sparkles, label: 'AI Questions' },
    { href: '/roadmap', icon: Map, label: 'Study Roadmap' },
    { href: '/resources', icon: FolderOpen, label: 'Resources' },
    { href: '/textbooks', icon: BookOpen, label: 'Textbooks' },
    { href: '/trends', icon: TrendingUp, label: 'Exam Trends' },
    { href: '/upload', icon: Upload, label: 'Upload & Train' },
    { href: '/analytics', icon: BarChart3, label: 'Analytics' },
    { href: '/bookmarks', icon: Bookmark, label: 'Bookmarks' },
    { href: '/feedback', icon: MessageSquare, label: 'Feedback' },
    { href: '/tokens', icon: Coins, label: 'AI Tokens' },
];

interface TokenInfo {
    available: number;
    purchased_tokens: number;
    feedback_credits: number;
    daily_limit: number;
    weekly_limit: number;
    is_admin: boolean;
}

export default function Sidebar() {
    const pathname = usePathname();
    const { user, logout } = useAuth();
    const router = useRouter();
    const [open, setOpen] = useState(false);
    const [tokenInfo, setTokenInfo] = useState<TokenInfo | null>(null);

    useEffect(() => { setOpen(false); }, [pathname]);
    useEffect(() => {
        const handler = (e: KeyboardEvent) => { if (e.key === 'Escape') setOpen(false); };
        window.addEventListener('keydown', handler);
        return () => window.removeEventListener('keydown', handler);
    }, []);

    // Fetch token balance
    useEffect(() => {
        if (user) {
            authAPI.getTokenBalance()
                .then(res => setTokenInfo(res.data))
                .catch(() => {});
        }
    }, [user, pathname]);

    const handleLogout = () => {
        logout();
        router.push('/');
    };

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
                <div className="flex items-center gap-3 px-6 mb-4">
                    <div className="w-10 h-10 rounded-xl flex items-center justify-center" style={{ background: 'var(--gradient-primary)' }}>
                        <Zap className="w-6 h-6 text-white" />
                    </div>
                    <span className="text-lg font-bold gradient-text">CrackCMS</span>
                </div>

                {/* User */}
                <div className="px-6 mb-3">
                    <div className="glass-card p-3">
                        <div className="flex items-center gap-3">
                            <div className="w-9 h-9 rounded-lg flex items-center justify-center text-sm font-bold" style={{ background: 'var(--gradient-primary)' }}>
                                {user?.first_name?.[0] || user?.username?.[0] || 'U'}
                            </div>
                            <div>
                                <div className="text-sm font-medium">{user?.first_name || user?.username}</div>
                                <div className="text-xs" style={{ color: 'var(--text-secondary)' }}>UPSC CMS 2026</div>
                            </div>
                        </div>
                    </div>
                </div>

                {/* Token Balance Widget */}
                {tokenInfo && (
                    <div className="px-6 mb-2">
                        <Link href="/tokens" className="block">
                            <div className="token-balance-widget">
                                <div className="flex items-center justify-between">
                                    <div className="flex items-center gap-2">
                                        <Zap className="w-4 h-4" style={{ color: '#f59e0b' }} />
                                        <span className="text-xs font-bold" style={{ color: '#f59e0b' }}>AI Tokens</span>
                                    </div>
                                    {tokenInfo.is_admin && (
                                        <span className="text-[10px] font-bold px-1.5 py-0.5 rounded" style={{ background: 'rgba(139,92,246,0.15)', color: '#8b5cf6' }}>ADMIN</span>
                                    )}
                                </div>
                                <div className="flex items-baseline gap-1 mt-1">
                                    <span className="text-lg font-bold" style={{ color: tokenInfo.is_admin ? '#8b5cf6' : tokenInfo.available > 5 ? '#10b981' : tokenInfo.available > 0 ? '#f59e0b' : '#ef4444' }}>
                                        {tokenInfo.is_admin ? '∞' : tokenInfo.available}
                                    </span>
                                    {!tokenInfo.is_admin && (
                                        <span className="text-[10px]" style={{ color: 'var(--text-secondary)' }}>tokens left</span>
                                    )}
                                </div>
                                {!tokenInfo.is_admin && tokenInfo.available <= 3 && (
                                    <div className="text-[10px] mt-1 font-medium" style={{ color: '#ef4444' }}>
                                        Running low — tap to buy more
                                    </div>
                                )}
                            </div>
                        </Link>
                    </div>
                )}

                {/* Nav Links */}
                <nav className="space-y-1 overflow-y-auto flex-1 min-h-0">
                    {navItems.map((item) => {
                        const isActive = pathname === item.href || pathname?.startsWith(item.href + '/');
                        return (
                            <Link key={item.href} href={item.href} className={`sidebar-link ${isActive ? 'active' : ''}`}>
                                <item.icon className="w-5 h-5" />
                                <span className="text-sm font-medium">{item.label}</span>
                            </Link>
                        );
                    })}
                </nav>

                {/* Bottom — settings, theme, logout (always visible) */}
                <div className="mt-auto px-4 pb-3 pt-2 border-t" style={{ borderColor: 'var(--glass-border)' }}>
                    <Link href="/settings" className={`sidebar-link ${pathname === '/settings' ? 'active' : ''}`} style={{ padding: '8px 24px' }}>
                        <Settings className="w-5 h-5" />
                        <span className="text-sm font-medium">Settings</span>
                    </Link>
                    <div className="px-2 my-2">
                        <ThemeToggle />
                    </div>
                    <button onClick={handleLogout} className="sidebar-link w-full" style={{ color: '#ef4444', padding: '8px 24px' }}>
                        <LogOut className="w-5 h-5" />
                        <span className="text-sm">Logout</span>
                    </button>
                </div>
            </div>
        </>
    );
}
