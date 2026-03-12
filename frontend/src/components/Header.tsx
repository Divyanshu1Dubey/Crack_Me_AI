'use client';

import { useAuth } from '@/lib/auth';
import { authAPI, analyticsAPI } from '@/lib/api';
import { usePathname } from 'next/navigation';
import { useEffect, useState, useRef } from 'react';
import { Zap, Bell, Search } from 'lucide-react';
import { Avatar, AvatarFallback } from '@/components/ui/avatar';
import Link from 'next/link';
import ThemeToggle from '@/components/ThemeToggle';
import SearchDialog from '@/components/SearchDialog';

interface TokenInfo {
  available: number;
  is_admin: boolean;
}

interface Announcement {
  id: number;
  title: string;
  message: string;
  priority: string;
  created_at: string;
}

const pageTitles: Record<string, string> = {
  '/dashboard': 'Dashboard',
  '/questions': 'Question Bank',
  '/tests': 'Tests',
  '/ai-tutor': 'AI Tutor',
  '/simulator': 'CMS Simulator',
  '/generate': 'AI Questions',
  '/roadmap': 'Study Roadmap',
  '/resources': 'Resources',
  '/textbooks': 'Textbooks',
  '/trends': 'Exam Trends',
  '/upload': 'Upload & Train',
  '/analytics': 'Analytics',
  '/bookmarks': 'Bookmarks',
  '/feedback': 'Feedback',
  '/tokens': 'AI Tokens',
  '/settings': 'Settings',
  '/leaderboard': 'Leaderboard',
  '/flashcards': 'Flashcards',
  '/admin': 'Admin Panel',
};

export default function Header() {
  const pathname = usePathname();
  const { user } = useAuth();
  const [tokenInfo, setTokenInfo] = useState<TokenInfo | null>(null);
  const [searchOpen, setSearchOpen] = useState(false);
  const [notifications, setNotifications] = useState<Announcement[]>([]);
  const [notifOpen, setNotifOpen] = useState(false);
  const [readIds, setReadIds] = useState<Set<number>>(new Set());
  const notifRef = useRef<HTMLDivElement>(null);

  // Ctrl+K / Cmd+K to open search
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
        e.preventDefault();
        setSearchOpen(true);
      }
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, []);

  useEffect(() => {
    if (user) {
      authAPI.getTokenBalance()
        .then(res => setTokenInfo(res.data))
        .catch(() => {});
      analyticsAPI.getAnnouncements()
        .then(res => setNotifications(Array.isArray(res.data) ? res.data : res.data?.results || []))
        .catch(() => {});
    }
  }, [user, pathname]);

  // Load read notification IDs from localStorage
  useEffect(() => {
    if (typeof window !== 'undefined') {
      const stored = localStorage.getItem('read_notif_ids');
      if (stored) {
        try { setReadIds(new Set(JSON.parse(stored))); } catch { /* ignore */ }
      }
    }
  }, []);

  // Close notification dropdown on outside click
  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (notifRef.current && !notifRef.current.contains(e.target as Node)) {
        setNotifOpen(false);
      }
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, []);

  const markAllRead = () => {
    const ids = new Set(notifications.map(n => n.id));
    setReadIds(ids);
    if (typeof window !== 'undefined') {
      localStorage.setItem('read_notif_ids', JSON.stringify([...ids]));
    }
  };

  const unreadCount = notifications.filter(n => !readIds.has(n.id)).length;

  const getTitle = () => {
    if (!pathname) return 'CrackCMS';
    if (pathname.startsWith('/tests/')) return 'Test';
    return pageTitles[pathname] || 'CrackCMS';
  };

  return (
    <header className="sticky top-0 z-30 flex h-14 items-center justify-between border-b border-border bg-background/95 backdrop-blur-sm px-6">
      {/* Left: Page title */}
      <div className="flex items-center gap-3 ml-0 md:ml-0 pl-12 md:pl-0">
        <h1 className="text-lg font-semibold text-foreground">{getTitle()}</h1>
      </div>

      {/* Right: Actions */}
      <div className="flex items-center gap-3">
        {/* Search shortcut */}
        <button onClick={() => setSearchOpen(true)}
          className="hidden md:flex items-center gap-2 px-3 py-1.5 text-sm text-muted-foreground bg-muted rounded-lg hover:bg-accent transition-colors">
          <Search className="w-3.5 h-3.5" />
          <span>Search...</span>
          <kbd className="ml-2 text-[10px] bg-background px-1.5 py-0.5 rounded border border-border font-mono">Ctrl+K</kbd>
        </button>

        {/* Token balance */}
        {tokenInfo && (
          <Link href="/tokens" className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-amber-50 dark:bg-amber-500/10 border border-amber-200 dark:border-amber-500/20 hover:border-amber-300 dark:hover:border-amber-500/30 transition-colors">
            <Zap className="w-3.5 h-3.5 text-amber-600 dark:text-amber-400" />
            <span className="text-sm font-semibold text-amber-700 dark:text-amber-400">
              {tokenInfo.is_admin ? '∞' : tokenInfo.available}
            </span>
          </Link>
        )}

        {/* Notifications */}
        <div className="relative" ref={notifRef}>
          <button onClick={() => { setNotifOpen(!notifOpen); if (!notifOpen) markAllRead(); }}
            className="relative p-2 rounded-lg hover:bg-accent transition-colors">
            <Bell className="w-4.5 h-4.5 text-muted-foreground" />
            {unreadCount > 0 && (
              <span className="absolute -top-0.5 -right-0.5 w-4 h-4 rounded-full bg-destructive text-[9px] font-bold text-white flex items-center justify-center">
                {unreadCount > 9 ? '9+' : unreadCount}
              </span>
            )}
          </button>
          {notifOpen && (
            <div className="absolute right-0 top-full mt-2 w-80 bg-card border border-border rounded-xl shadow-lg z-50 overflow-hidden">
              <div className="px-4 py-3 border-b border-border flex items-center justify-between">
                <span className="text-sm font-semibold text-foreground">Notifications</span>
                {notifications.length > 0 && (
                  <button onClick={markAllRead} className="text-[10px] text-primary hover:underline">Mark all read</button>
                )}
              </div>
              <div className="max-h-64 overflow-y-auto">
                {notifications.length === 0 ? (
                  <div className="p-6 text-center text-sm text-muted-foreground">No notifications</div>
                ) : (
                  notifications.map(n => (
                    <div key={n.id} className={`px-4 py-3 border-b border-border last:border-0 ${!readIds.has(n.id) ? 'bg-primary/5' : ''}`}>
                      <div className="flex items-start gap-2">
                        <span className={`mt-1 w-2 h-2 rounded-full shrink-0 ${n.priority === 'high' ? 'bg-destructive' : n.priority === 'medium' ? 'bg-amber-500' : 'bg-emerald-500'}`} />
                        <div>
                          <p className="text-sm font-medium text-foreground">{n.title}</p>
                          <p className="text-xs text-muted-foreground mt-0.5 line-clamp-2">{n.message}</p>
                        </div>
                      </div>
                    </div>
                  ))
                )}
              </div>
            </div>
          )}
        </div>

        {/* Theme */}
        <ThemeToggle />

        {/* User avatar */}
        <Link href="/settings">
          <Avatar className="h-8 w-8 cursor-pointer ring-2 ring-border hover:ring-primary transition-all">
            <AvatarFallback className="text-xs font-semibold bg-primary/10 text-primary">
              {user?.first_name?.[0] || user?.username?.[0] || 'U'}
            </AvatarFallback>
          </Avatar>
        </Link>
      </div>

      <SearchDialog open={searchOpen} onClose={() => setSearchOpen(false)} />
    </header>
  );
}
