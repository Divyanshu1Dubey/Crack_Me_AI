/**
 * Giscus (GitHub Discussions) comment settings. A plain module, not part of
 * the 'use client' CommentsGiscus file: BlogPostLayout is a Server Component,
 * and a value imported from a client module there is a client-reference
 * proxy (always truthy), so the "configured?" check must live here.
 *
 * TODO: enable comments by (1) creating the public `crackcms-blog` repo on
 * GitHub, (2) enabling Discussions on it, and (3) running giscus.app once to
 * fetch the repoId + categoryId for the General category.
 */
export const GISCUS_REPO = 'Divyanshu1Dubey/crackcms-blog';
export const GISCUS_REPO_ID = ''; // TODO: fill from giscus.app after repo setup
export const GISCUS_CATEGORY_ID = ''; // TODO: fill from giscus.app after repo setup
export const GISCUS_CATEGORY = 'General';

/** True once the IDs are filled in. Until then the comments section is not
 *  rendered at all (no "Comments are opening soon" placeholder). */
export const GISCUS_CONFIGURED = Boolean(GISCUS_REPO_ID && GISCUS_CATEGORY_ID);
