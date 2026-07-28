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
    'crackcms-editorial': {
        slug: 'crackcms-editorial',
        name: 'CrackCMS Editorial Team',
        credential: 'MBBS, MD, FRCP (clinicians)',
        role: 'Clinical Content Editors, CrackCMS',
        bio:
            'A practising physician panel that reviews every CrackCMS article for clinical accuracy, syllabus fit and exam relevance. We have between us sat UPSC CMS, NEET PG and INI-CET, and we write the way we wished someone had written for us.',
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
            'https://cracklabs.app/about',
            'https://cracklabs.app/editorial-policy',
        ],
    },
    'dr-aarav-mehta': {
        slug: 'dr-aarav-mehta',
        name: 'Dr. Aarav Mehta',
        credential: 'MBBS, MD (Internal Medicine)',
        role: 'Senior Editor — Medicine, CrackCMS',
        bio:
            'AIIMS-trained internist who runs the UPSC CMS medicine module. Interests include ECG teaching, acid-base interpretation, and making NEET PG recall stick. Believes 7-hour sleep is the single highest-yield revision tool a candidate owns.',
        expertise: ['Internal Medicine', 'ECG interpretation', 'Acid-base', 'UPSC CMS Medicine'],
        sameAs: ['https://cracklabs.app/authors/aarav-mehta'],
    },
};

/** Lookup helper. Falls back to the editorial team if slug is unknown. */
export function getAuthor(slug: string): AuthorProfile {
    return authors[slug] ?? authors['crackcms-editorial'];
}
