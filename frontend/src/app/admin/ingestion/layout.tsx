// /admin/ingestion/* layout — client-side admin role gate.
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
import { useAuth } from '@/lib/auth';

export default function IngestionLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const { user, loading } = useAuth();
  const router = useRouter();
  const pathname = usePathname();

  useEffect(() => {
    if (loading) return;
    const isAdmin = !!user && (user.role === 'admin' || user.is_admin);
    if (!isAdmin) {
      router.replace(`/login?next=${encodeURIComponent(pathname || '/admin/ingestion')}`);
    }
  }, [user, loading, router, pathname]);

  if (loading || !user) {
    return (
      <div className="flex items-center justify-center min-h-[60vh] text-muted-foreground">
        Checking admin access…
      </div>
    );
  }

  return <div className="ingestion-admin">{children}</div>;
}
