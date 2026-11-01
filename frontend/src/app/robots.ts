import type { MetadataRoute } from 'next';
import { privateNoIndexPrefixes, siteUrl } from '@/lib/seo';

/**
 * robots.txt — served from this route (the old static public/robots.txt and
 * public/sitemap.xml shadowed it and were removed).
 *
 * Rules:
 *  - Disallow prefixes have NO trailing slash, so "/dashboard" blocks both
 *    /dashboard and /dashboard/... (a "/dashboard/" rule does not match the
 *    real URL /dashboard).
 *  - /_next/ is NOT blocked: Google needs the JS/CSS chunks and /_next/image
 *    to render pages.
 *  - Every user-agent appears in exactly one group. A crawler obeys only the
 *    most specific group that names it, so each group carries the full rule
 *    set.
 */

/** Search engines and AI answer engines we explicitly welcome. */
const NAMED_CRAWLERS = [
    'Googlebot',
    'Googlebot-Image',
    'Googlebot-News',
    'Googlebot-Video',
    'Google-Extended',
    'Bingbot',
    'Slurp',
    'DuckDuckBot',
    'DuckAssistBot',
    'Baiduspider',
    'YandexBot',
    'Applebot',
    'Applebot-Extended',
    'GPTBot',
    'ChatGPT-User',
    'OAI-SearchBot',
    'ClaudeBot',
    'Claude-Web',
    'Claude-User',
    'Claude-SearchBot',
    'PerplexityBot',
    'Perplexity-User',
    'cohere-ai',
    'cohere-training-crawler',
    'CCBot',
    'Diffbot',
    'PetalBot',
];

export default function robots(): MetadataRoute.Robots {
    // Private / login-only app routes (question bank, dashboards, admin, API).
    const disallow = [...privateNoIndexPrefixes];

    return {
        rules: [
            { userAgent: '*', allow: '/', disallow },
            { userAgent: NAMED_CRAWLERS, allow: '/', disallow },
        ],
        sitemap: `${siteUrl}/sitemap.xml`,
        host: siteUrl,
    };
}
