// /admin/import-center/* layout — client-side admin role gate + nav shell.
//
// Reuses the same `useAuth()` gate as the rest of the admin tree; the
// backend `IsAdminUser` permission is the authoritative RBAC layer so a
// tampered token still gets a 403 from the API.

'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { useEffect } from 'react';
import { useRouter } from 'next/navigation';
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

  useEffect(() => {
    if (loading) return;
    const isAdmin = !!user && (user.role === 'admin' || user.is_admin);
    if (!isAdmin) {
      router.replace(`/login?next=${encodeURIComponent(pathname || '/admin/import-center')}`);
    }
  }, [user, loading, router, pathname]);

  if (loading || !user) {
    return (
      <div className="flex items-center justify-center min-h-[60vh] text-muted-foreground">
        Checking admin access…
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-background text-foreground">
      <header className="border-b border-border bg-card px-6 py-4">
        <h1 className="text-2xl font-bold">📥 Import Center</h1>
        <p className="text-sm text-muted-foreground">
          Upload DOCX, PDF, PPTX or ZIP. Preview, classify, publish, and generate mock tests.
        </p>
      </header>
      <nav className="flex gap-1 border-b border-border bg-card px-4">
        {TABS.map((tab) => {
          const active = tab.exact ? pathname === tab.href : pathname?.startsWith(tab.href);
          return (
            <Link
              key={tab.href}
              href={tab.href}
              className={`px-4 py-2 text-sm font-medium border-b-2 ${
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
      <main className="p-6">{children}</main>
    </div>
  );
}
