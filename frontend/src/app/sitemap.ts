import type { MetadataRoute } from 'next';
import { publicIndexableRoutes, siteUrl } from '@/lib/seo';

export default function sitemap(): MetadataRoute.Sitemap {
  const now = new Date();

  // Priority mapping for SEO weight
  const priorityMap: Record<string, number> = {
    '/': 1.0,
    '/register': 0.9,
    '/subscription': 0.85,
    '/resources': 0.8,
    '/login': 0.7,
    '/forgot-password': 0.3,
  };

  const changeFreqMap: Record<string, 'always' | 'hourly' | 'daily' | 'weekly' | 'monthly' | 'yearly' | 'never'> = {
    '/': 'daily',
    '/register': 'monthly',
    '/subscription': 'weekly',
    '/resources': 'weekly',
    '/login': 'monthly',
    '/forgot-password': 'yearly',
  };

  // Core pages from publicIndexableRoutes
  const corePages: MetadataRoute.Sitemap = publicIndexableRoutes.map((route) => ({
    url: `${siteUrl}${route}`,
    lastModified: now,
    changeFrequency: changeFreqMap[route] || 'weekly',
    priority: priorityMap[route] || 0.5,
  }));

  // SEO Landing pages — virtual keyword-rich URLs that all resolve to the homepage
  // These help Google index us for long-tail queries
  const seoLandingPages: MetadataRoute.Sitemap = [
    // UPSC CMS long-tail keywords
    { url: `${siteUrl}/#upsc-cms-preparation`, lastModified: now, changeFrequency: 'weekly', priority: 0.9 },
    { url: `${siteUrl}/#upsc-cms-pyq`, lastModified: now, changeFrequency: 'weekly', priority: 0.85 },
    { url: `${siteUrl}/#upsc-cms-mock-test`, lastModified: now, changeFrequency: 'weekly', priority: 0.85 },
    { url: `${siteUrl}/#upsc-cms-question-bank`, lastModified: now, changeFrequency: 'weekly', priority: 0.8 },
    // NEET PG long-tail keywords
    { url: `${siteUrl}/#neet-pg-preparation`, lastModified: now, changeFrequency: 'weekly', priority: 0.9 },
    { url: `${siteUrl}/#neet-pg-pyq`, lastModified: now, changeFrequency: 'weekly', priority: 0.85 },
    { url: `${siteUrl}/#neet-pg-mock-test`, lastModified: now, changeFrequency: 'weekly', priority: 0.85 },
    { url: `${siteUrl}/#neet-pg-question-bank`, lastModified: now, changeFrequency: 'weekly', priority: 0.8 },
    // Feature-specific
    { url: `${siteUrl}/#ai-medical-tutor`, lastModified: now, changeFrequency: 'monthly', priority: 0.7 },
    { url: `${siteUrl}/#medical-flashcards`, lastModified: now, changeFrequency: 'monthly', priority: 0.7 },
  ];

  return [...corePages, ...seoLandingPages];
}
