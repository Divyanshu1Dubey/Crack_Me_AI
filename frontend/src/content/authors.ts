import type { ReactNode } from 'react';

/**
 * An author profile that ships with the blog.
 *
 * Build the matching `Person` JSON-LD via `authorSchema(this)` below so
 * each post emits a real `author: { '@type': 'Person', name, url,
 * jobTitle, knowsAbout, worksFor }` block — required for Google's
 * Product Review Update + EEAT signals.
 */
export interface AuthorProfile {
    /** URL slug used at `/blog/author/<slug>` if/when an author archive
     *  page exists. */
    slug: string;
    /** Display name. */
    name: string;
    /** Professional credential, e.g. "MBBS, MD (Internal Medicine)". */
    credential: string;
    /** Short, credible bio (≤ 240 chars). Renders on bylines + author pages. */
    bio: string;
    /** Current role. */
    role: string;
    /** Areas of clinical / editorial expertise. Used in `knowsAbout[]` JSON-LD. */
    expertise: string[];
    /** Public profile URLs (LinkedIn, institution page, ORCID, etc.). */
    sameAs: string[];
    /** Optional React snippet shown beneath the byline on post pages. */
    bioComponent?: ReactNode;
}

export const authors: Record<string, AuthorProfile> = {
    // The only author profile. It carries no credential we cannot show. A
    // named, credentialed author is added here only once the owner has
    // confirmed the person is real, consents, has a verifiable credential and
    // is listed on /about.
    'crackcms-editorial': {
        slug: 'crackcms-editorial',
        name: 'CrackCMS Editorial Team',
        credential: 'Editorial team — CrackCMS',
        role: 'Clinical Content Editors, CrackCMS',
        bio:
            'The CrackCMS editorial team reviews every article for clinical accuracy, syllabus fit and exam relevance, following our editorial and medical-review policies, and writes the way we wished someone had written for us.',
        expertise: [
            'UPSC CMS',
            'NEET PG',
            'INI-CET',
            'Internal Medicine',
            'Surgery',
            'OBG',
            'Paediatrics',
            'PSM',
        ],
        sameAs: [
            'https://www.cracklabs.app/about',
            'https://www.cracklabs.app/editorial-policy',
        ],
    },
};

/**
 * Author archive slugs that no longer have a profile, mapped to the profile
 * now credited with their posts. 'dr-aarav-mehta' (an MBBS, MD byline on
 * 105 posts) could not be verified as a real, consenting clinician, so those
 * posts are credited to the editorial team and the old archive URL redirects.
 */
export const RETIRED_AUTHOR_SLUGS: Record<string, string> = {
    'dr-aarav-mehta': 'crackcms-editorial',
};

/** Lookup helper. Falls back to the editorial team if slug is unknown. */
export function getAuthor(slug: string): AuthorProfile {
    return authors[slug] ?? authors['crackcms-editorial'];
}
