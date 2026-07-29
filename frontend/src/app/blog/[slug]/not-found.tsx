import Link from 'next/link';
import { ArrowLeft } from 'lucide-react';

export default function BlogPostNotFound() {
    return (
        <div className="min-h-screen bg-background text-foreground">
            <div className="mx-auto max-w-3xl px-4 py-20 sm:px-6 sm:py-28 text-center">
                <p className="text-sm font-bold uppercase tracking-wider text-primary">404</p>
                <h1 className="mt-3 text-4xl font-black tracking-tight sm:text-5xl">
                    That post hasn&apos;t been published yet.
                </h1>
                <p className="mt-4 text-base text-muted-foreground">
                    The link you followed may be broken, or the post may still be in editorial review.
                </p>
                <div className="mt-7 flex flex-wrap items-center justify-center gap-2">
                    <Link
                        href="/blog"
                        className="inline-flex items-center gap-2 rounded-xl bg-primary px-5 py-2.5 text-sm font-bold text-primary-foreground hover:opacity-95"
                    >
                        <ArrowLeft className="h-4 w-4" /> Back to the blog
                    </Link>
                    <Link
                        href="/"
                        className="rounded-xl border border-border bg-card px-5 py-2.5 text-sm font-bold text-foreground hover:bg-muted"
                    >
                        Home
                    </Link>
                </div>
            </div>
        </div>
    );
}
