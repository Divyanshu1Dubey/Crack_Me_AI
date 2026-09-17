'use client';

import { siteName, siteUrl } from '@/lib/seo';

/**
 * Lightweight `<link rel="alternate">` block for hreflang + AI modes.
 *
 * hreflang tells Google which language/region variant to serve. We support
 * English (India primary, with US/GB fallbacks) and a `x-default` catch-all.
 *
 * AI-mode links tell Google, Perplexity, Bing Chat, etc. that an
 * AI-friendly summary / attribution policy exists at a known URL.
 */
export function HreflangAlternates({ path }: { path: string }) {
    const canonical = `${siteUrl}${path}`;

    return (
        <>
            {/* Human-language variants */}
            <link rel="alternate" hrefLang="en-IN" href={canonical} />
            <link rel="alternate" hrefLang="en-US" href={canonical} />
            <link rel="alternate" hrefLang="en-GB" href={canonical} />
            <link rel="alternate" hrefLang="x-default" href={canonical} />

            {/* AI / generative-engine hints — tell AI crawlers where to find
                structured, attribution-friendly versions of this page */}
            <link
                rel="alternate"
                type="text/plain"
                hrefLang="x-ai"
                href={`${siteUrl}/llms.txt`}
                title="AI-grade content summary for LLM indexing"
            />
        </>
    );
}
