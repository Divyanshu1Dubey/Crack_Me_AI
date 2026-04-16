'use client';

import { useAuth } from '@/lib/auth';
import { authAPI, analyticsAPI } from '@/lib/api';
import { usePathname } from 'next/navigation';
import { useEffect, useState, useRef, useCallback } from 'react';
import useSWR from 'swr';
import { Zap, Bell, Search, CheckCheck, X, Clock, AlertTriangle, Info, Megaphone } from 'lucide-react';
import { Avatar, AvatarFallback } from '@/components/ui/avatar';
import Link from 'next/link';
import dynamic from 'next/dynamic';
import SearchDialog from '@/components/SearchDialog';
import BrandMark from '@/components/BrandMark';

const ThemeToggle = dynamic(() => import('@/components/ThemeToggle'), {
  ssr: false,
  loading: () => <div className="p-2 w-[34px] h-[34px]" />,
});

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
  '/roadmap': 'AI-Powered Study Plan',
  '/resources': 'CMS Study Hub',
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
  const { data: tokenRes } = useSWR(user ? '/auth/tokens/' : null, () => authAPI.getTokenBalance().then(r => r.data), { refreshInterval: 60000 });
  const tokenInfo = tokenRes as TokenInfo | undefined;
  const [searchOpen, setSearchOpen] = useState(false);
  const [notifications, setNotifications] = useState<Announcement[]>([]);
  const [notifOpen, setNotifOpen] = useState(false);
  const [readIds, setReadIds] = useState<Set<number>>(new Set());
  const [loading, setLoading] = useState(false);
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

  // Fetch data
  const fetchNotifications = useCallback(async () => {
    setLoading(true);
    try {
      const res = await analyticsAPI.getAnnouncements();
      setNotifications(Array.isArray(res.data) ? res.data : res.data?.results || []);
    } catch {
      // ignore
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (user) {
      fetchNotifications();
    }
  }, [user, fetchNotifications]);

  // Auto-refresh notifications every 5 minutes
  useEffect(() => {
    if (!user) return;
    const interval = setInterval(fetchNotifications, 5 * 60 * 1000);
    return () => clearInterval(interval);
  }, [user, fetchNotifications]);

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

  const saveReadIds = (ids: Set<number>) => {
    setReadIds(ids);
    if (typeof window !== 'undefined') {
      localStorage.setItem('read_notif_ids', JSON.stringify([...ids]));
    }
  };

  const markAsRead = (id: number) => {
    const newIds = new Set(readIds);
    newIds.add(id);
    saveReadIds(newIds);
  };

  const markAllRead = () => {
    const ids = new Set(notifications.map(n => n.id));
    saveReadIds(ids);
  };

  const dismissNotification = (id: number) => {
    markAsRead(id);
    setNotifications(prev => prev.filter(n => n.id !== id));
  };

  const unreadCount = notifications.filter(n => !readIds.has(n.id)).length;

  const getTitle = () => {
    if (!pathname) return 'CrackCMS';
    if (pathname.startsWith('/tests/')) return 'Test';
    return pageTitles[pathname] || 'CrackCMS';
  };

  const getPriorityIcon = (priority: string) => {
    switch (priority) {
      case 'urgent':
      case 'high':
        return <AlertTriangle className="w-4 h-4 text-destructive" />;
      case 'medium':
        return <Megaphone className="w-4 h-4 text-amber-500" />;
      default:
        return <Info className="w-4 h-4 text-blue-500" />;
    }
  };

  const getPriorityColor = (priority: string) => {
    switch (priority) {
      case 'urgent':
      case 'high':
        return 'border-l-destructive bg-destructive/5';
      case 'medium':
        return 'border-l-amber-500 bg-amber-500/5';
      default:
        return 'border-l-blue-500 bg-blue-500/5';
    }
  };

  const formatTime = (dateStr: string) => {
    const date = new Date(dateStr);
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffMins = Math.floor(diffMs / 60000);
    const diffHours = Math.floor(diffMs / 3600000);
    const diffDays = Math.floor(diffMs / 86400000);

    if (diffMins < 1) return 'Just now';
    if (diffMins < 60) return `${diffMins}m ago`;
    if (diffHours < 24) return `${diffHours}h ago`;
    if (diffDays < 7) return `${diffDays}d ago`;
    return date.toLocaleDateString();
  };

  return (
      <header className="sticky top-0 z-30 mb-4 flex h-16 items-center justify-between rounded-2xl border border-border/80 bg-card/80 px-4 shadow-sm backdrop-blur-xl md:px-6">
      {/* Left: Page title */}
      <div className="flex items-center gap-3 pl-12 md:pl-0">
        <div className="md:hidden">
          <BrandMark href="/dashboard" compact showTagline={false} />
        </div>
        <div className="hidden h-9 w-1 rounded-full bg-gradient-to-b from-cyan-500 to-teal-500 md:block" />
        <div className="hidden md:block">
          <p className="text-[11px] font-semibold uppercase tracking-[0.12em] text-muted-foreground">Workspace</p>
          <h1 className="text-base font-bold text-foreground md:text-lg">{getTitle()}</h1>
        </div>
      </div>

      {/* Right: Actions */}
      <div className="flex items-center gap-2 md:gap-3">
        {/* Search shortcut */}
        <button onClick={() => setSearchOpen(true)}
          className="hidden md:flex items-center gap-2 rounded-xl border border-border/80 bg-muted/70 px-3 py-1.5 text-sm text-muted-foreground transition-colors hover:bg-accent">
          <Search className="w-3.5 h-3.5" />
          <span>Search...</span>
          <kbd className="ml-2 rounded border border-border bg-background px-1.5 py-0.5 font-mono text-[10px]">Ctrl+K</kbd>
        </button>

        <button
          onClick={() => setSearchOpen(true)}
          className="rounded-xl border border-border/80 bg-muted/70 p-2 text-muted-foreground transition-colors hover:bg-accent md:hidden"
          aria-label="Open search"
        >
          <Search className="h-4 w-4" />
        </button>

        {/* Token balance */}
        {tokenInfo && (
          <Link href="/tokens" className="flex items-center gap-1.5 rounded-xl border border-amber-200 bg-amber-50 px-3 py-1.5 transition-colors hover:border-amber-300 dark:border-amber-500/20 dark:bg-amber-500/10 dark:hover:border-amber-500/30">
            <Zap className="w-3.5 h-3.5 text-amber-600 dark:text-amber-400" />
            <span className="text-sm font-semibold text-amber-700 dark:text-amber-400">
              {tokenInfo.is_admin ? 'Admin' : `${tokenInfo.available} Tokens`}
            </span>
          </Link>
        )}

        {/* Notifications */}
        <div className="relative" ref={notifRef}>
          <button onClick={() => setNotifOpen(!notifOpen)}
            className="relative rounded-xl border border-border/80 bg-muted/70 p-2 transition-colors hover:bg-accent">
            <Bell className="w-4.5 h-4.5 text-muted-foreground" />
            {unreadCount > 0 && (
              <span className="absolute -top-0.5 -right-0.5 w-4 h-4 rounded-full bg-destructive text-[9px] font-bold text-white flex items-center justify-center animate-pulse">
                {unreadCount > 9 ? '9+' : unreadCount}
              </span>
            )}
          </button>
          {notifOpen && (
            <div className="absolute right-0 top-full z-50 mt-2 w-[min(24rem,calc(100vw-2rem))] overflow-hidden rounded-2xl border border-border bg-card shadow-lg">
              <div className="px-4 py-3 border-b border-border flex items-center justify-between bg-muted/50">
                <div className="flex items-center gap-2">
                  <Bell className="w-4 h-4 text-primary" />
                  <span className="text-sm font-semibold text-foreground">Notifications</span>
                  {unreadCount > 0 && (
                    <span className="px-1.5 py-0.5 text-[10px] font-semibold bg-primary text-primary-foreground rounded-full">
                      {unreadCount} new
                    </span>
                  )}
                </div>
                {unreadCount > 0 && (
                  <button onClick={markAllRead} className="flex items-center gap-1 text-xs text-primary hover:underline">
                    <CheckCheck className="w-3 h-3" />
                    Mark all read
                  </button>
                )}
              </div>
              <div className="max-h-80 overflow-y-auto">
                {loading ? (
                  <div className="p-6 text-center">
                    <div className="w-5 h-5 border-2 border-primary border-t-transparent rounded-full animate-spin mx-auto" />
                  </div>
                ) : notifications.length === 0 ? (
                  <div className="p-8 text-center">
                    <Bell className="w-10 h-10 mx-auto text-muted-foreground/30 mb-2" />
                    <p className="text-sm text-muted-foreground">No notifications</p>
                    <p className="text-xs text-muted-foreground/60 mt-1">You&apos;re all caught up!</p>
                  </div>
                ) : (
                  <div className="divide-y divide-border">
                    {notifications.map(n => {
                      const isRead = readIds.has(n.id);
                      return (
                        <div
                          key={n.id}
                          className={`p-4 border-l-4 transition-colors hover:bg-accent/50 ${getPriorityColor(n.priority)} ${!isRead ? 'bg-primary/5' : ''}`}
                          onClick={() => markAsRead(n.id)}
                        >
                          <div className="flex items-start gap-3">
                            <div className="flex-shrink-0 mt-0.5">
                              {getPriorityIcon(n.priority)}
                            </div>
                            <div className="flex-1 min-w-0">
                              <div className="flex items-start justify-between gap-2">
                                <p className={`text-sm font-medium ${!isRead ? 'text-foreground' : 'text-muted-foreground'}`}>
                                  {n.title}
                                </p>
                                <button
                                  onClick={(e) => { e.stopPropagation(); dismissNotification(n.id); }}
                                  className="flex-shrink-0 p-1 rounded hover:bg-destructive/10 text-muted-foreground hover:text-destructive transition-colors"
                                  title="Dismiss"
                                >
                                  <X className="w-3 h-3" />
                                </button>
                              </div>
                              <p className="text-xs text-muted-foreground mt-1 line-clamp-2">{n.message}</p>
                              <div className="flex items-center gap-2 mt-2">
                                <Clock className="w-3 h-3 text-muted-foreground/60" />
                                <span className="text-[10px] text-muted-foreground/60">{formatTime(n.created_at)}</span>
                                {!isRead && (
                                  <span className="px-1.5 py-0.5 text-[9px] font-medium bg-primary/10 text-primary rounded">NEW</span>
                                )}
                              </div>
                            </div>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>
              {notifications.length > 0 && (
                <div className="px-4 py-2 border-t border-border bg-muted/30">
                  <p className="text-[10px] text-muted-foreground text-center">
                    Click a notification to mark it as read
                  </p>
                </div>
              )}
            </div>
          )}
        </div>

        {/* Theme */}
        <ThemeToggle />

        {/* User avatar */}
        <Link href="/settings">
          <Avatar className="h-9 w-9 cursor-pointer ring-2 ring-border transition-all hover:ring-primary">
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
