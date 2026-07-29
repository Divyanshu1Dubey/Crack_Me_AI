import { ImageResponse } from 'next/og';
import { getAllPostSlugs, getPostBySlug } from '@/lib/blog';

// Use the Node runtime (default) instead of `edge` — Next.js requires us to
// pick one, and Node lets `generateStaticParams` co-exist (edge forbids it).
export const alt = 'CrackCMS Blog post';
export const size = { width: 1200, height: 630 };
export const contentType = 'image/png';

/**
 * Per-post dynamic Open Graph image (1200×630) using Next.js's
 * `ImageResponse`. Renders the post title + category + author over a
 * gradient background. Optimised for the Facebook / LinkedIn / Twitter
 * link-preview canvas.
 */
export default async function PostOgImage({
    params,
}: {
    params: Promise<{ slug: string }>;
}) {
    const { slug } = await params;
    const post = getPostBySlug(slug);

    const title = post?.title ?? 'CrackCMS Blog';
    const category = post?.category ?? 'Exam Strategy';
    const author = post?.author ?? 'CrackCMS Editorial';
    const readTime = post?.readingTime ?? '';

    return new ImageResponse(
        (
            <div
                style={{
                    width: '100%',
                    height: '100%',
                    display: 'flex',
                    flexDirection: 'column',
                    background:
                        'linear-gradient(135deg, #1d4ed8 0%, #1e40af 40%, #0f172a 100%)',
                    color: 'white',
                    padding: '72px',
                    fontFamily: 'sans-serif',
                }}
            >
                {/* Brand */}
                <div style={{ display: 'flex', alignItems: 'center', gap: 16, fontSize: 28, fontWeight: 700 }}>
                    <div
                        style={{
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'center',
                            width: 56,
                            height: 56,
                            borderRadius: 16,
                            background: 'rgba(255,255,255,0.18)',
                            fontSize: 32,
                        }}
                    >
                        ⚕
                    </div>
                    <span>CrackCMS Blog</span>
                </div>

                {/* Category chip */}
                <div
                    style={{
                        marginTop: 56,
                        display: 'flex',
                        alignItems: 'center',
                        gap: 8,
                        alignSelf: 'flex-start',
                        padding: '12px 20px',
                        borderRadius: 999,
                        background: 'rgba(255,255,255,0.16)',
                        fontSize: 24,
                        fontWeight: 700,
                        letterSpacing: 1.5,
                        textTransform: 'uppercase',
                    }}
                >
                    {category}
                </div>

                {/* Title */}
                <div
                    style={{
                        marginTop: 32,
                        fontSize: 64,
                        fontWeight: 800,
                        lineHeight: 1.1,
                        letterSpacing: '-0.02em',
                        display: 'flex',
                    }}
                >
                    {title.length > 110 ? `${title.slice(0, 107)}…` : title}
                </div>

                {/* Spacer */}
                <div style={{ flex: 1 }} />

                {/* Footer */}
                <div
                    style={{
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'space-between',
                        fontSize: 22,
                        opacity: 0.92,
                    }}
                >
                    <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                        <span style={{ fontWeight: 700 }}>{author}</span>
                        {readTime ? <span>· {readTime} read</span> : null}
                    </div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8, fontWeight: 700 }}>
                        cracklabs.app
                    </div>
                </div>
            </div>
        ),
        { ...size }
    );
}

// Pre-render all known slugs at build time.
export function generateStaticParams() {
    return getAllPostSlugs().map((slug) => ({ slug }));
}
