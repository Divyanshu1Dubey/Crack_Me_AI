import type { Metadata } from "next";
import { siteName, siteUrl, defaultOgImage } from "@/lib/seo";

/**
 * Build a canonical absolute URL for a given path. Strips trailing slashes
 * (except the root), normalises multiple slashes, and returns a stable string
 * suitable for `alternates.canonical`, `openGraph.url`, and JSON-LD `@id`.
 */
export function buildCanonical(path: string): string {
    if (!path || path === "/") return `${siteUrl}/`;
    const cleaned = `/${String(path).replace(/^\/+/, "").replace(/\/+$/, "")}`;
    return `${siteUrl}${cleaned}`;
}

/**
 * Default OG image URL (absolute). Uses the brand logo shipped with the app.
 */
export function buildOgImage(path = defaultOgImage): string {
    if (/^https?:\/\//.test(path)) return path;
    return `${siteUrl}${path.startsWith("/") ? "" : "/"}${path}`;
}

/**
 * Factory for a standard page-level Next.js Metadata object.
 * Use for any public route. Title auto-uses the global template from layout.
 */
export function buildPageMetadata({
    title,
    description,
    path,
    image = defaultOgImage,
    type = "website",
    keywords,
    noindex = false,
}: {
    title: string;
    description: string;
    path: string;
    image?: string;
    type?: "website" | "article" | "profile" | "book";
    keywords?: string[];
    noindex?: boolean;
}): Metadata {
    const canonical = buildCanonical(path);
    const ogImage = buildOgImage(image);
    return {
        title,
        description,
        keywords,
        alternates: {
            canonical,
            languages: { "en-IN": canonical },
        },
        openGraph: {
            type,
            url: canonical,
            title,
            description,
            siteName,
            images: [
                {
                    url: ogImage,
                    width: 1200,
                    height: 630,
                    alt: `${title} — ${siteName}`,
                },
            ],
            locale: "en_IN",
        },
        twitter: {
            card: "summary_large_image",
            title,
            description,
            images: [ogImage],
        },
        robots: noindex
            ? { index: false, follow: false }
            : {
                  index: true,
                  follow: true,
                  googleBot: {
                      index: true,
                      follow: true,
                      "max-image-preview": "large",
                      "max-snippet": -1,
                      "max-video-preview": -1,
                  },
              },
    };
}

/**
 * JSON-LD helpers — emitting safe, validatable schema.org payloads for the
 * most common rich result types. All helpers return plain JS objects; pass
 * them into the <StructuredData /> component (or dangerouslySetInnerHTML).
 */

export function orgSchema() {
    return {
        "@context": "https://schema.org",
        "@type": "Organization",
        "@id": `${siteUrl}/#organization`,
        name: siteName,
        url: siteUrl,
        logo: {
            "@type": "ImageObject",
            url: `${siteUrl}/cms-circle-logo.png`,
            width: 512,
            height: 512,
        },
        description:
            "AI-powered medical exam preparation platform for UPSC CMS, NEET PG, INI-CET, FMGE, USMLE and Medical Officer recruitment.",
        sameAs: [
            "https://github.com/Divyanshu1Dubey/Crack_Me_AI",
            "https://twitter.com/cracklabs",
            "https://linkedin.com/company/cracklabs",
        ],
        contactPoint: {
            "@type": "ContactPoint",
            contactType: "customer support",
            email: "hello@cracklabs.app",
            availableLanguage: ["English", "Hindi"],
        },
    };
}

export function websiteSchema() {
    return {
        "@context": "https://schema.org",
        "@type": "WebSite",
        "@id": `${siteUrl}/#website`,
        name: siteName,
        url: siteUrl,
        inLanguage: "en-IN",
        publisher: { "@id": `${siteUrl}/#organization` },
        potentialAction: {
            "@type": "SearchAction",
            target: {
                "@type": "EntryPoint",
                urlTemplate: `${siteUrl}/questions?search={search_term_string}`,
            },
            "query-input": "required name=search_term_string",
        },
    };
}

export function breadcrumbSchema(items: { name: string; path: string }[]) {
    return {
        "@context": "https://schema.org",
        "@type": "BreadcrumbList",
        itemListElement: items.map((it, i) => ({
            "@type": "ListItem",
            position: i + 1,
            name: it.name,
            item: buildCanonical(it.path),
        })),
    };
}

export function faqSchema(items: { q: string; a: string }[]) {
    return {
        "@context": "https://schema.org",
        "@type": "FAQPage",
        mainEntity: items.map((f) => ({
            "@type": "Question",
            name: f.q,
            acceptedAnswer: { "@type": "Answer", text: f.a },
        })),
    };
}

export function articleSchema({
    headline,
    description,
    path,
    datePublished,
    dateModified,
    authorName,
    image,
}: {
    headline: string;
    description: string;
    path: string;
    datePublished: string;
    dateModified: string;
    authorName: string;
    image?: string;
}) {
    return {
        "@context": "https://schema.org",
        "@type": "Article",
        headline,
        description,
        image: buildOgImage(image),
        datePublished,
        dateModified,
        inLanguage: "en-IN",
        author: { "@type": "Person", name: authorName },
        publisher: {
            "@type": "Organization",
            name: siteName,
            url: siteUrl,
            logo: { "@type": "ImageObject", url: `${siteUrl}/cms-circle-logo.png` },
        },
        mainEntityOfPage: {
            "@type": "WebPage",
            "@id": buildCanonical(path),
        },
    };
}

export function softwareAppSchema() {
    return {
        "@context": "https://schema.org",
        "@type": "SoftwareApplication",
        name: "CrackCMS UPSC CMS Preparation App",
        operatingSystem: "Web, Android, iOS",
        applicationCategory: "EducationalApplication",
        url: siteUrl,
        description:
            "AI-powered UPSC CMS and medical exam preparation with PYQs, mock tests, flashcards, textbooks and analytics.",
        offers: {
            "@type": "Offer",
            price: "0",
            priceCurrency: "INR",
            description: "Free tier available with premium medical exam preparation plans.",
        },
        aggregateRating: {
            "@type": "AggregateRating",
            ratingValue: "4.8",
            ratingCount: "1250",
            bestRating: "5",
            worstRating: "1",
        },
    };
}

export function howToSchema({
    name,
    description,
    steps,
    path,
}: {
    name: string;
    description: string;
    steps: { name: string; text: string }[];
    path: string;
}) {
    return {
        "@context": "https://schema.org",
        "@type": "HowTo",
        name,
        description,
        inLanguage: "en-IN",
        url: buildCanonical(path),
        step: steps.map((s, i) => ({
            "@type": "HowToStep",
            position: i + 1,
            name: s.name,
            text: s.text,
        })),
    };
}

/** Combine multiple JSON-LD node payloads under @graph */
export function graphSchema(nodes: object[]) {
    return {
        "@context": "https://schema.org",
        "@graph": nodes,
    };
}
