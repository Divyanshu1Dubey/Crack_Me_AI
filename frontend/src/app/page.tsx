import type { Metadata } from 'next';
import LandingPage from './_landing/LandingPage';
import { defaultOgImage, defaultOgImageSize, siteDescription, siteName, siteTitle, siteUrl } from '@/lib/seo';
import { jsonLdString, softwareAppSchema } from '@/lib/metadata';

/**
 * Homepage. The interactive landing UI is a client component
 * (_landing/LandingPage.tsx); this server wrapper owns the homepage-only
 * metadata and structured data. The canonical and og:url used to live in the
 * root layout, which leaked them to every page without its own metadata.
 */
export const metadata: Metadata = {
    alternates: {
        canonical: '/',
        languages: { 'en-IN': '/', 'x-default': '/' },
    },
    openGraph: {
        type: 'website',
        url: '/',
        title: siteTitle,
        description: siteDescription,
        siteName,
        images: [{ url: defaultOgImage, ...defaultOgImageSize, alt: 'CrackCMS UPSC CMS Preparation Platform' }],
    },
};

// Homepage-specific nodes only (Organization + WebSite come from the root
// layout). No FAQPage: the homepage shows no FAQ, and FAQ markup must match
// visible content.
const homeJsonLd = {
    '@context': 'https://schema.org',
    '@graph': [
        {
            '@type': 'WebPage',
            '@id': `${siteUrl}/#webpage`,
            url: `${siteUrl}/`,
            name: siteTitle,
            description: siteDescription,
            isPartOf: { '@id': `${siteUrl}/#website` },
            about: { '@id': `${siteUrl}/#organization` },
            inLanguage: 'en-IN',
        },
        softwareAppSchema(),
    ],
};

export default function HomePage() {
    return (
        <>
            <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: jsonLdString(homeJsonLd) }} />
            <LandingPage />
        </>
    );
}
