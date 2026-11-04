'use client';

import Link from 'next/link';
import { Pencil } from 'lucide-react';
import { useAuth } from '@/lib/auth';

/** Blog admins are the backend profile's admins (role / is_admin), never auth user_metadata. */
export function isBlogAdmin(user: { role?: string; is_admin?: boolean } | null | undefined): boolean {
    return !!user && (user.role === 'admin' || !!user.is_admin);
}

/**
 * "Edit post" on a published post, for admins only: opens /admin/blog on this
 * post. Rendered client-side from the signed-in profile, so the static page
 * stays the same for everyone and nothing shows for visitors. The API checks
 * the role again on every write.
 */
export default function BlogAdminBar({ slug }: { slug: string }) {
    const { user } = useAuth();
    if (!isBlogAdmin(user)) return null;
    return (
        <Link
            href={`/admin/blog?edit=${encodeURIComponent(slug)}`}
            className="inline-flex items-center gap-1.5 rounded-full border border-primary/40 bg-primary/10 px-3 py-1.5 text-xs font-bold text-primary transition-colors hover:bg-primary/15"
        >
            <Pencil className="h-3.5 w-3.5" aria-hidden="true" /> Edit post
        </Link>
    );
}
