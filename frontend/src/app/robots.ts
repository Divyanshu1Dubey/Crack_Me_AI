import type { MetadataRoute } from 'next';
import { privateNoIndexPrefixes, siteUrl } from '@/lib/seo';

export default function robots(): MetadataRoute.Robots {
    return {
        rules: [
            {
                userAgent: '*',
                allow: '/',
                disallow: [
                    ...privateNoIndexPrefixes,
                    '/api/',
                    '/_next/',
                    '/auth/',
                    '/admin/',
                    '/reset-password',
                    '/forgot-password',
                ],
            },
            {
                userAgent: 'Googlebot',
                allow: '/',
                disallow: privateNoIndexPrefixes,
            },
            {
                userAgent: 'Bingbot',
                allow: '/',
                disallow: privateNoIndexPrefixes,
            },
            // Major AI crawlers — explicit allow so CrackCMS content is
            // cited in ChatGPT, Claude, Perplexity, Gemini, Google AI Mode.
            // Question bank and dashboard pages stay blocked to prevent
            // scraping of licensed question content.
            {
                userAgent: ['GPTBot', 'ChatGPT-User', 'OAI-SearchBot', 'Claude-Web', 'ClaudeBot', 'PerplexityBot', 'Perplexity-User', 'Google-Extended', 'Applebot-Extended', 'cohere-ai'],
                allow: ['/', '/cms', '/neet-pg', '/ini-cet', '/fmge', '/usmle', '/medical-officer', '/government-doctor-jobs', '/guides', '/about', '/contact', '/subscription', '/register', '/resources', '/jobs', '/privacy-policy', '/terms', '/refund-policy', '/cookie-policy', '/disclaimer', '/editorial-policy', '/medical-review-policy'],
                disallow: ['/api/', '/admin/', '/dashboard/', '/questions/', '/tests/', '/analytics/', '/simulator/', '/ai-tutor/', '/tokens/', '/bookmarks/', '/flashcards/', '/generate/', '/roadmap/', '/textbooks/', '/upload/', '/trends/', '/leaderboard/', '/feedback/', '/settings/', '/auth/'],
            },
        ],
        sitemap: `${siteUrl}/sitemap.xml`,
        host: siteUrl,
    };
}
