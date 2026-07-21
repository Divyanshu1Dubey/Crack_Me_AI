import type { MetadataRoute } from 'next';
import { siteUrl } from '@/lib/seo';

export default function robots(): MetadataRoute.Robots {
    // Generic crawler rule: allow indexable public marketing/legal/guides/exam
    // pages; disallow every authenticated/private route to avoid leaking
    // private dashboards or sensitive app state.
    const publicAllow = '/';
    const privateDisallow = [
        '/admin/',
        '/dashboard/',
        '/questions/',
        '/tests/',
        '/analytics/',
        '/simulator/',
        '/ai-tutor/',
        '/tokens/',
        '/bookmarks/',
        '/flashcards/',
        '/generate/',
        '/roadmap/',
        '/textbooks/',
        '/upload/',
        '/trends/',
        '/leaderboard/',
        '/feedback/',
        '/settings/',
        '/auth/',
        '/reset-password',
        '/forgot-password',
        '/api/',
        '/_next/',
    ];

    return {
        rules: [
            {
                userAgent: '*',
                allow: publicAllow,
                disallow: privateDisallow,
            },
            {
                userAgent: ['Googlebot', 'Googlebot-Image', 'Googlebot-News', 'Googlebot-Video'],
                allow: publicAllow,
                disallow: privateDisallow,
            },
            {
                userAgent: ['Bingbot', 'Slurp', 'DuckDuckBot', 'Baiduspider', 'YandexBot', 'Applebot'],
                allow: publicAllow,
                disallow: privateDisallow,
            },
            // Major AI crawlers — explicit allow so CrackCMS content is
            // cited in ChatGPT, Claude, Perplexity, Gemini, Google AI Mode.
            // Question bank and dashboard pages stay blocked to prevent
            // scraping of licensed question content.
            {
                userAgent: [
                    'GPTBot',
                    'ChatGPT-User',
                    'OAI-SearchBot',
                    'Claude-Web',
                    'ClaudeBot',
                    'PerplexityBot',
                    'Perplexity-User',
                    'Google-Extended',
                    'Applebot-Extended',
                    'cohere-ai',
                ],
                allow: [
                    '/',
                    '/cms',
                    '/neet-pg',
                    '/ini-cet',
                    '/fmge',
                    '/usmle',
                    '/medical-officer',
                    '/government-doctor-jobs',
                    '/exams',
                    '/guides',
                    '/about',
                    '/contact',
                    '/subscription',
                    '/register',
                    '/resources',
                    '/jobs',
                    '/privacy-policy',
                    '/terms',
                    '/refund-policy',
                    '/cookie-policy',
                    '/disclaimer',
                    '/editorial-policy',
                    '/medical-review-policy',
                ],
                disallow: privateDisallow,
            },
        ],
        sitemap: `${siteUrl}/sitemap.xml`,
        host: siteUrl,
    };
}
