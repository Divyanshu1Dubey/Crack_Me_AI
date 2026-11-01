// /admin/ingestion/* layout — client-side admin role gate + app shell.
//
// UPSC CMS's existing /admin/* routes continue to work unchanged; this
// layout is OPT-IN for the new isolated NEET PG / INI-CET / FMGE /
// USMLE / PLAB ingestion admin only.
//
// We use the same client-side `useAuth()` helper that the rest of the
// admin pages use, then redirect non-admins to /login. The backend
// `IsIngestionAdmin` permission still gates every API endpoint as the
// authoritative RBAC layer.

'use client';

import { useEffect } from 'react';
import { useRouter, usePathname } from 'next/navigation';
import Sidebar from '@/components/Sidebar';
import Header from '@/components/Header';
import { useAuth } from '@/lib/auth';

export default function IngestionLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const { user, loading } = useAuth();
  const router = useRouter();
  const pathname = usePathname();
  const isAdmin = !!user && (user.role === 'admin' || user.is_admin);

  useEffect(() => {
    if (loading) return;
    if (!isAdmin) {
      router.replace(`/login?next=${encodeURIComponent(pathname || '/admin/ingestion')}`);
    }
  }, [isAdmin, loading, router, pathname]);

  // Non-admins never see the admin UI, not even while the redirect runs.
  if (loading || !isAdmin) {
    return (
      <div className="flex items-center justify-center min-h-[60vh] text-muted-foreground">
        Checking admin access…
      </div>
    );
  }

  // App shell: the same markup as the per-page pattern (Sidebar + Header),
  // so every ingestion page has the app navigation and the mobile menu.
  return (
    <div className="min-h-screen bg-background">
      <Sidebar />
      <div className="main-content">
        <Header />
        <div className="page-container ingestion-admin">{children}</div>
      </div>
    </div>
  );
}
