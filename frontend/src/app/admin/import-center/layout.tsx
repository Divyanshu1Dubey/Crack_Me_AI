// /admin/import-center/* layout — client-side admin role gate + app shell + tab nav.
//
// Reuses the same `useAuth()` gate as the rest of the admin tree; the
// backend `IsAdminUser` permission is the authoritative RBAC layer so a
// tampered token still gets a 403 from the API.

'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { useEffect } from 'react';
import { useRouter } from 'next/navigation';
import AppShell from '@/components/AppShell';
import { useAuth } from '@/lib/auth';

const TABS = [
  { href: '/admin/import-center', label: 'Dashboard', exact: true },
  { href: '/admin/import-center/upload', label: 'Upload' },
  { href: '/admin/import-center/batches', label: 'Batches' },
  { href: '/admin/import-center/review', label: 'Review Queue' },
  { href: '/admin/import-center/search', label: 'Search' },
];

export default function ImportCenterLayout({ children }: { children: React.ReactNode }) {
  const { user, loading } = useAuth();
  const router = useRouter();
  const pathname = usePathname();
  const isAdmin = !!user && (user.role === 'admin' || user.is_admin);

  useEffect(() => {
    if (loading) return;
    if (!isAdmin) {
      router.replace(`/login?next=${encodeURIComponent(pathname || '/admin/import-center')}`);
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

  // The shared app shell (Sidebar + Header, contract C6) around the Import
  // Center header card and tab nav. Fixed overlays inside it cover the
  // viewport: .main-content has no layout containment any more.
  return (
    <AppShell>
      <div className="text-foreground">
        <div className="overflow-hidden rounded-xl border border-border bg-card">
          <header className="px-4 py-4 sm:px-6">
            <Link href="/admin" className="text-xs text-muted-foreground hover:text-foreground">
              ← Admin dashboard
            </Link>
            <h1 className="mt-1 text-2xl font-bold">📥 Import Center</h1>
            <p className="text-sm text-muted-foreground">
              Upload DOCX, PDF, PPTX or ZIP. Preview, classify, publish, and generate mock tests.
            </p>
          </header>
          {/* Scrolls sideways on narrow screens instead of clipping the last tab. */}
          <nav
            aria-label="Import Center sections"
            className="flex gap-1 overflow-x-auto border-t border-border px-2 sm:px-4 [scrollbar-width:none]"
          >
            {TABS.map((tab) => {
              const active = tab.exact ? pathname === tab.href : pathname?.startsWith(tab.href);
              return (
                <Link
                  key={tab.href}
                  href={tab.href}
                  aria-current={active ? 'page' : undefined}
                  // Plain border-colour utilities apply now that the default
                  // `* { border-color }` rule sits in @layer base (globals.css).
                  className={`shrink-0 whitespace-nowrap border-b-2 px-4 py-2 text-sm font-medium ${
                    active
                      ? 'border-primary text-primary'
                      : 'border-transparent text-muted-foreground hover:text-foreground'
                  }`}
                >
                  {tab.label}
                </Link>
              );
            })}
          </nav>
        </div>
        <div className="pt-6">{children}</div>
      </div>
    </AppShell>
  );
}
