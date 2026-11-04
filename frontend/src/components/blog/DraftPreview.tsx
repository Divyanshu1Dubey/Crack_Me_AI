'use client';

import dynamic from 'next/dynamic';
import { usePathname } from 'next/navigation';
import { useEffect, useState, type ReactNode } from 'react';
import { Loader2 } from 'lucide-react';
import { useAuth } from '@/lib/auth';
import { blogAPI, type BlogPostAdmin } from '@/lib/blogAPI';
import { isBlogAdmin } from './BlogAdminBar';

// The article renderer loads only when an admin opens a draft.
const DraftArticle = dynamic(() => import('./DraftArticle'), { ssr: false });

const POST_PATH = /^\/blog\/([a-z0-9]+(?:-[a-z0-9]+)*)\/?$/;

/**
 * /blog/<slug> of an unpublished post is a 404 for everyone (the page is
 * rendered from the public API). For an admin this shows the draft instead,
 * fetched with their credentials (the API shows drafts to blog admins only).
 * `children`: the 404 page, shown to everyone else.
 */
export default function DraftPreview({ children }: { children: ReactNode }) {
    const pathname = usePathname() ?? '';
    const { user } = useAuth();
    const admin = isBlogAdmin(user);
    const slug = POST_PATH.exec(pathname)?.[1] ?? '';
    const [draft, setDraft] = useState<BlogPostAdmin | null>(null);
    const [checking, setChecking] = useState(false);

    useEffect(() => {
        if (!admin || !slug) return;
        let current = true;
        setChecking(true);
        blogAPI.getBySlug(slug)
            .then((res) => { if (current) setDraft(res.data); })
            .catch(() => { if (current) setDraft(null); })
            .finally(() => { if (current) setChecking(false); });
        return () => { current = false; };
    }, [admin, slug]);

    if (admin && draft) return <DraftArticle post={draft} />;
    return (
        <>
            {admin && checking ? (
                <p className="flex items-center justify-center gap-2 pt-6 text-sm text-muted-foreground" role="status">
                    <Loader2 className="h-4 w-4 animate-spin" /> Looking for a draft at this address…
                </p>
            ) : null}
            {children}
        </>
    );
}
