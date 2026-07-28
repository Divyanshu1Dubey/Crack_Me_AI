import type { MetadataRoute } from 'next';
import { siteUrl } from '@/lib/seo';
import { getAllCmsYears } from '@/lib/pyqYearData';
import { getAllCmsSubjects } from '@/lib/subjectHubData';
import { getAllCmsCutoffYears } from '@/lib/cutoffData';
import { getAllCmsBookSlugs } from '@/lib/bookDeepDiveData';
import { getAllCmsStrategySlugs } from '@/lib/strategyData';
import { getAllPosts, getAllCategories, getAllTags } from '@/lib/blog';

export default function sitemap(): MetadataRoute.Sitemap {
    const now = new Date();

    // Programmatic year-PYQ routes — keep in sync with PyqYearLandingLayout data.
    const yearRoutes = getAllCmsYears().map((year) => ({
        url: `${siteUrl}/cms/pyq/${year}`,
        lastModified: now,
        changeFrequency: 'monthly' as const,
        priority: 0.85,
    }));

    // Programmatic subject-hub routes
    const subjectRoutes = getAllCmsSubjects().map((slug) => ({
        url: `${siteUrl}/cms/subject/${slug}`,
        lastModified: now,
        changeFrequency: 'monthly' as const,
        priority: 0.85,
    }));

    // Programmatic cutoff routes
    const cutoffRoutes = getAllCmsCutoffYears().map((year) => ({
        url: `${siteUrl}/cms/cutoff/${year}`,
        lastModified: now,
        changeFrequency: 'yearly' as const,
        priority: 0.8,
    }));

    // Programmatic book deep-dive routes
    const bookRoutes = getAllCmsBookSlugs().map((slug) => ({
        url: `${siteUrl}/cms/books/${slug}`,
        lastModified: now,
        changeFrequency: 'monthly' as const,
        priority: 0.8,
    }));

    // Programmatic strategy routes
    const strategyRoutes = getAllCmsStrategySlugs().map((slug) => ({
        url: `${siteUrl}/cms/strategy/${slug}`,
        lastModified: now,
        changeFrequency: 'monthly' as const,
        priority: 0.8,
    }));

    // Comparison pages — high commercial intent, top-priority for indexing
    const comparisonRoutes = [
        { url: `${siteUrl}/cms/vs-neet-pg`, priority: 0.85 },
        { url: `${siteUrl}/cms/vs-ini-cet`, priority: 0.85 },
        { url: `${siteUrl}/neet-pg/vs-usmle`, priority: 0.85 },
        { url: `${siteUrl}/fmge/vs-next`, priority: 0.85 },
    ].map((r) => ({
        url: r.url,
        lastModified: now,
        changeFrequency: 'monthly' as const,
        priority: r.priority,
    }));

    // Index hubs for the new programmatic sections
    const hubRoutes = [
        { url: `${siteUrl}/cms/subject`, priority: 0.8 },
        { url: `${siteUrl}/cms/cutoff`, priority: 0.8 },
        { url: `${siteUrl}/cms/books`, priority: 0.8 },
        { url: `${siteUrl}/cms/strategy`, priority: 0.8 },
    ].map((r) => ({
        url: r.url,
        lastModified: now,
        changeFrequency: 'weekly' as const,
        priority: r.priority,
    }));

    // Blog hub + every post + category + author archive + RSS feed
    const blogRoutes = [
        {
            url: `${siteUrl}/blog`,
            lastModified: now,
            changeFrequency: 'weekly' as const,
            priority: 0.85,
        },
        {
            url: `${siteUrl}/blog/feed.xml`,
            lastModified: now,
            changeFrequency: 'daily' as const,
            priority: 0.5,
        },
        ...getAllPosts().map((p) => ({
            url: `${siteUrl}/blog/${p.slug}`,
            lastModified: new Date(p.dateModified),
            changeFrequency: 'weekly' as const,
            priority: 0.85,
        })),
        ...getAllCategories().map((c) => ({
            url: `${siteUrl}/blog/category/${c.slug}`,
            lastModified: now,
            changeFrequency: 'weekly' as const,
            priority: 0.7,
        })),
        ...getAllTags().map((t) => ({
            url: `${siteUrl}/blog/tag/${t.slug}`,
            lastModified: now,
            changeFrequency: 'weekly' as const,
            priority: 0.6,
        })),
        // Author archive pages — crawlable author profile nodes
        ...Array.from(
            new Set(
                getAllPosts().flatMap((p) => [p.authorId, p.reviewedBy].filter(Boolean) as string[]),
            ),
        ).map((slug) => ({
            url: `${siteUrl}/blog/author/${slug}`,
            lastModified: now,
            changeFrequency: 'monthly' as const,
            priority: 0.65,
        })),
    ];

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

    return [
        ...staticEntries,
        ...yearRoutes,
        ...subjectRoutes,
        ...cutoffRoutes,
        ...bookRoutes,
        ...strategyRoutes,
        ...comparisonRoutes,
        ...hubRoutes,
        ...blogRoutes,
    ];
}
