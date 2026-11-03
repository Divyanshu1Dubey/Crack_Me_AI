import type { Metadata } from "next";
import { siteName, siteUrl, defaultOgImage } from "@/lib/seo";
import { CMS_PYQ_COUNT, CMS_PYQ_YEARS } from "@/lib/bankStats";

/** The square source logo (1254×1254) — used for Organization/publisher logos. */
const LOGO_PATH = "/cms-circle-logo.png";

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
 * Drop a trailing brand suffix ("… | CrackCMS", "… — CrackCMS",
 * "… — CrackCMS by CrackLabs AI") from a page title. The root layout's
 * title template already appends " | CrackCMS", so titles that carried their
 * own suffix rendered as "… | CrackCMS | CrackCMS".
 */
export function stripBrandSuffix(title: string): string {
    return title.replace(/\s*[|—–-]\s*(CrackCMS(?:\s+by\s+CrackLabs AI)?|CrackLabs AI)\s*$/i, "").trim();
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
        title: stripBrandSuffix(title),
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
                    // The raw logo is a 1254×1254 square; the default image
                    // and the blog covers are 1200×630 OG renders.
                    width: image === LOGO_PATH ? 1254 : 1200,
                    height: image === LOGO_PATH ? 1254 : 630,
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
            // Actual pixel size of the shipped file.
            width: 1254,
            height: 1254,
        },
        description:
            `CrackCMS is a study platform for MBBS graduates preparing for UPSC CMS and NEET PG, organised around ${CMS_PYQ_COUNT} UPSC CMS previous-year questions (${CMS_PYQ_YEARS}) with AI explanations, mock tests and analytics.`,
        sameAs: [
            "https://github.com/Divyanshu1Dubey/Crack_Me_AI",
            "https://twitter.com/cracklabs",
            "https://linkedin.com/company/cracklabs",
        ],
        contactPoint: {
            "@type": "ContactPoint",
            contactType: "customer support",
            email: "crackwith.ai@gmail.com",
            telephone: "+91-9601981524",
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
        // No SearchAction: the site has no public search-results URL that
        // reads a query parameter (/questions ignores ?search= and is login-only).
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
    authorUrl,
    reviewedByName,
    reviewedByCredential,
    citations,
    speakable,
    medicalPageType = false,
}: {
    headline: string;
    description: string;
    path: string;
    datePublished: string;
    dateModified: string;
    authorName: string;
    image?: string;
    authorUrl?: string;
    reviewedByName?: string;
    reviewedByCredential?: string;
    citations?: { label: string; url?: string; published?: string }[];
    speakable?: string[];
    /** If true, emits @type `MedicalWebPage` (extends `WebPage` with
     *  medical-specialty metadata) instead of plain `Article`. Use for
     *  medical content that cites references. */
    medicalPageType?: boolean;
}) {
    const baseAuthor = {
        "@type": "Person",
        name: authorName,
        ...(authorUrl ? { url: authorUrl } : {}),
    };

    const schema: Record<string, unknown> = {
        "@context": "https://schema.org",
        "@type": medicalPageType ? "MedicalWebPage" : "Article",
        headline,
        description,
        image: buildOgImage(image),
        datePublished,
        dateModified,
        inLanguage: "en-IN",
        author: baseAuthor,
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

    if (reviewedByName) {
        schema.reviewedBy = {
            "@type": "Person",
            name: reviewedByName,
            ...(reviewedByCredential ? { hasCredential: reviewedByCredential } : {}),
        };
    }

    if (citations && citations.length > 0) {
        schema.citation = citations.map((c) => ({
            "@type": "CreativeWork",
            name: c.label,
            ...(c.url ? { url: c.url } : {}),
            ...(c.published ? { datePublished: c.published } : {}),
        }));
    }

    if (speakable && speakable.length > 0) {
        schema.speakable = {
            "@type": "SpeakableSpecification",
            xpath: speakable,
        };
    }

    return schema;
}

/**
 * `Person` JSON-LD for an author / reviewer profile. Reused by the
 * Article schema's `author` / `reviewedBy` blocks and emitted
 * independently on author archive pages.
 */
export function personSchema({
    name,
    credential,
    role,
    bio,
    expertise,
    sameAs,
    url,
}: {
    name: string;
    credential?: string;
    role?: string;
    bio?: string;
    expertise?: string[];
    sameAs?: string[];
    url?: string;
}) {
    return {
        "@context": "https://schema.org",
        "@type": "Person",
        name,
        ...(credential ? { hasCredential: credential } : {}),
        ...(role ? { jobTitle: role } : {}),
        ...(bio ? { description: bio } : {}),
        ...(expertise && expertise.length > 0 ? { knowsAbout: expertise } : {}),
        ...(sameAs && sameAs.length > 0 ? { sameAs } : {}),
        ...(url ? { url } : {}),
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
        // No aggregateRating: there are no collected user reviews to back one,
        // and self-awarded ratings break Google's structured-data policy.
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

/**
 * Serialise a JSON-LD payload for a plain `<script type="application/ld+json"
 * dangerouslySetInnerHTML>` tag. Use a plain script (not next/script with
 * strategy="beforeInteractive"): in the App Router that strategy only queues
 * the payload for the client bootstrap, so the structured data is missing
 * from the server HTML that crawlers read. `<` is escaped so a value
 * containing "</script>" cannot end the tag early.
 */
export function jsonLdString(data: unknown): string {
    return JSON.stringify(data).replace(/</g, "\\u003c");
}

/** Combine multiple JSON-LD node payloads under @graph */
export function graphSchema(nodes: object[]) {
    return {
        "@context": "https://schema.org",
        "@graph": nodes,
    };
}

// ─── AEO / GEO Schemas ──────────────────────────────────────────────────────
// Structured data types optimised for AI search engines (SGE, Perplexity,
// Claude Web, Bing Chat) and traditional rich results. Use alongside the
// existing Article / FAQPage / Course schemas.

/**
 * `DefinedTerm` — ideal for medical-glossary pages. AI engines surface
 * definitions directly in their answers (Perplexity, Google AI Overview).
 */
export function glossaryTermSchema({
    term,
    definition,
    source,
    relatedTerms,
}: {
    term: string;
    definition: string;
    source?: string;
    relatedTerms?: string[];
}) {
    return {
        "@context": "https://schema.org",
        "@type": "DefinedTerm",
        name: term,
        description: definition,
        inLanguage: "en-IN",
        ...(source ? { "url": source } : {}),
        ...(relatedTerms && relatedTerms.length > 0
            ? { "relatedLink": relatedTerms.map(t => `${siteUrl}/glossary?term=${encodeURIComponent(t)}`) }
            : {}),
    };
}

/**
 * `QAPage` — for question + answer content. Google's "People Also Ask"
 * and AI Overviews pull from this type.
 */
export function qaPageSchema({
    question,
    answer,
    answerDetail,
    sourceUrl,
    reviewedBy,
}: {
    question: string;
    answer: string;
    answerDetail?: string;
    sourceUrl?: string;
    reviewedBy?: { name: string; credential?: string };
}) {
    const schema: Record<string, unknown> = {
        "@context": "https://schema.org",
        "@type": "QAPage",
        mainEntity: {
            "@type": "Question",
            name: question,
            acceptedAnswer: {
                "@type": "Answer",
                text: answer,
                ...(answerDetail ? { "description": answerDetail } : {}),
                ...(sourceUrl ? { "url": sourceUrl } : {}),
                ...(reviewedBy
                    ? {
                          author: {
                              "@type": "Person",
                              name: reviewedBy.name,
                              ...(reviewedBy.credential ? { hasCredential: reviewedBy.credential } : {}),
                          },
                      }
                    : {}),
            },
        },
    };
    return schema;
}

/**
 * `MedicalWebPage` extended with `about` → `MedicalCondition` — helps
 * AI engines understand the medical topic coverage and surface the page
 * for condition-specific queries.
 */
export function medicalWebPageSchema({
    title,
    description,
    path,
    condition,
    reviewedBy,
    lastReviewed,
}: {
    title: string;
    description: string;
    path: string;
    condition?: string;
    reviewedBy?: { name: string; credential?: string };
    lastReviewed?: string;
}) {
    const schema: Record<string, unknown> = {
        "@context": "https://schema.org",
        "@type": "MedicalWebPage",
        "@id": buildCanonical(path),
        name: title,
        description,
        url: buildCanonical(path),
        inLanguage: "en-IN",
        publisher: { "@id": `${siteUrl}/#organization` },
        isPartOf: { "@id": `${siteUrl}/#website` },
    };
    if (condition) {
        schema.about = {
            "@type": "MedicalCondition",
            name: condition,
        };
    }
    if (reviewedBy) {
        schema.reviewedBy = {
            "@type": "Person",
            name: reviewedBy.name,
            ...(reviewedBy.credential ? { hasCredential: reviewedBy.credential } : {}),
        };
    }
    if (lastReviewed) {
        schema.dateReviewed = lastReviewed;
    }
    return schema;
}

/**
 * `CriticReview` — for content a named, verifiable reviewer has reviewed.
 * Signals E-E-A-T to AI search engines.
 */
export function criticReviewSchema({
    itemReviewed,
    reviewBody,
    reviewerName,
    reviewerCredential,
    reviewRating,
}: {
    itemReviewed: string;
    reviewBody: string;
    reviewerName: string;
    reviewerCredential?: string;
    reviewRating?: number; // 1-5
}) {
    return {
        "@context": "https://schema.org",
        "@type": "CriticReview",
        itemReviewed: {
            "@type": "Thing",
            name: itemReviewed,
        },
        reviewBody,
        author: {
            "@type": "Person",
            name: reviewerName,
            ...(reviewerCredential ? { hasCredential: reviewerCredential } : {}),
        },
        reviewRating: reviewRating
            ? {
                  "@type": "Rating",
                  ratingValue: reviewRating,
                  bestRating: 5,
                  worstRating: 1,
              }
            : undefined,
    };
}
