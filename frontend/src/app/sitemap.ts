import type { MetadataRoute } from 'next';
import { siteUrl } from '@/lib/seo';
import { getAllCmsYears } from '@/lib/pyqYearData';

export default function sitemap(): MetadataRoute.Sitemap {
    const now = new Date();

    // Programmatic year-PYQ routes — keep in sync with PyqYearLandingLayout data.
    const yearRoutes = getAllCmsYears().map((year) => ({
        url: `${siteUrl}/cms/pyq/${year}`,
        lastModified: now,
        changeFrequency: 'monthly' as const,
        priority: 0.85,
    }));

    // Priority policy:
    //   1.0  landing (root) — never overwrite
    //   0.95 exam landing hubs (high commercial + informational intent)
    //   0.9  guides + high-intent preparatory pages
    //   0.85 jobs + gov-doctor-jobs + company
    //   0.7  contact
    //   0.6-0.5 trust/legal
    //
    // changeFrequency is honest about what actually changes.
    const publicRoutes = [
        // Top-level
        { path: '/', priority: 1.0, changeFrequency: 'weekly' as const },
        { path: '/register', priority: 0.9, changeFrequency: 'monthly' as const },
        { path: '/subscription', priority: 0.85, changeFrequency: 'weekly' as const },
        { path: '/resources', priority: 0.8, changeFrequency: 'monthly' as const },

        // Company
        { path: '/about', priority: 0.85, changeFrequency: 'monthly' as const },
        { path: '/contact', priority: 0.7, changeFrequency: 'monthly' as const },
        { path: '/jobs', priority: 0.85, changeFrequency: 'daily' as const },

        // Exam landing pages — primary SEO targets
        { path: '/cms', priority: 0.95, changeFrequency: 'weekly' as const },
        { path: '/neet-pg', priority: 0.95, changeFrequency: 'weekly' as const },
        { path: '/ini-cet', priority: 0.95, changeFrequency: 'weekly' as const },
        { path: '/fmge', priority: 0.9, changeFrequency: 'weekly' as const },
        { path: '/usmle', priority: 0.9, changeFrequency: 'weekly' as const },
        { path: '/medical-officer', priority: 0.9, changeFrequency: 'weekly' as const },
        { path: '/government-doctor-jobs', priority: 0.85, changeFrequency: 'weekly' as const },

        // /exams microsites (already linked from landing)
        { path: '/exams', priority: 0.8, changeFrequency: 'weekly' as const },

        // Guides hub + canonical guides
        { path: '/guides', priority: 0.9, changeFrequency: 'weekly' as const },
        { path: '/guides/upsc-cms-complete-guide', priority: 0.9, changeFrequency: 'monthly' as const },
        { path: '/guides/neet-pg-complete-guide', priority: 0.9, changeFrequency: 'monthly' as const },
        { path: '/guides/ini-cet-complete-guide', priority: 0.85, changeFrequency: 'monthly' as const },
        { path: '/guides/fmge-complete-guide', priority: 0.85, changeFrequency: 'monthly' as const },
        { path: '/guides/usmle-step-1-guide', priority: 0.85, changeFrequency: 'monthly' as const },
        { path: '/guides/medical-officer-jobs', priority: 0.85, changeFrequency: 'monthly' as const },
        { path: '/guides/ai-in-medical-education', priority: 0.75, changeFrequency: 'monthly' as const },
        { path: '/guides/study-plan-builder', priority: 0.75, changeFrequency: 'monthly' as const },

        // Trust / legal / editorial / medical-review — explicit high-quality
        { path: '/privacy-policy', priority: 0.6, changeFrequency: 'yearly' as const },
        { path: '/terms', priority: 0.6, changeFrequency: 'yearly' as const },
        { path: '/refund-policy', priority: 0.5, changeFrequency: 'yearly' as const },
        { path: '/cookie-policy', priority: 0.5, changeFrequency: 'yearly' as const },
        { path: '/disclaimer', priority: 0.6, changeFrequency: 'yearly' as const },
        { path: '/editorial-policy', priority: 0.7, changeFrequency: 'yearly' as const },
        { path: '/medical-review-policy', priority: 0.7, changeFrequency: 'yearly' as const },

        // Programmatic PYQ hub
        { path: '/cms/pyq', priority: 0.85, changeFrequency: 'weekly' as const },
    ];

    const staticEntries = publicRoutes.map((r) => ({
        url: `${siteUrl}${r.path}`,
        lastModified: now,
        changeFrequency: r.changeFrequency,
        priority: r.priority,
    }));

    return [...staticEntries, ...yearRoutes];
}
