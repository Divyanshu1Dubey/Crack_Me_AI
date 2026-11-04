/**
 * blog.ts — blog post type, the static posts, and the database-backed posts
 * the public /blog pages render.
 *
 * Source of truth: the blog_engine database, edited at /admin/blog. Public
 * routes call loadBlogCatalog() / loadBlogPost() (server-side fetch with ISR,
 * BLOG_REVALIDATE_SECONDS). The static modules in src/content/blog are the
 * seed `manage.py seed_blogs` imports and the fallback `next build` renders
 * when the API is unreachable; the synchronous get*() helpers read them.
 */
import type { ReactNode } from 'react';
import {
    DEFAULT_LOCAL_API_URL,
    DEFAULT_PRODUCTION_API_URL,
    isKnownUnhealthyApiHost,
    isLocalhostApiUrl,
    normalizeApiBaseUrl,
} from '@/lib/apiBase';
import { countBlogWords, formatPostDate, readingMinutes, readingTimeLabel, slugifyHeading } from '@/lib/blogText';

import cmsLast5Days from '@/content/blog/upsc-cms-last-5-days-strategy';
import cmsNeetPgLastWeek from '@/content/blog/cms-and-neet-pg-last-week-shared-revision';
import cms2026Notification from '@/content/blog/upsc-cms-2026-official-notification-guide';
import neetPgVsUpscCms from '@/content/blog/neet-pg-vs-upsc-cms';

// August 2026 SEO expansion — 6 new posts covering syllabus, cutoff,
// strategy, comparative decision content, and a verified book shortlist.
// Each post emits Article + FAQ + BreadcrumbList JSON-LD; see the
// `BlogPostLayout` for the schema wiring.
import cmsSyllabusHighYield from '@/content/blog/upsc-cms-syllabus-high-yield-topics';
import cmsCutoff2024 from '@/content/blog/upsc-cms-2024-cutoff-marks-category-wise';
import cmsPrepStrategy6Month from '@/content/blog/upsc-cms-preparation-strategy-6-month-plan';
import neetPgCutoff2024 from '@/content/blog/neet-pg-2024-cutoff-category-wise';
import neetPgPrepStrategy from '@/content/blog/neet-pg-preparation-strategy-study-plans';
import neetPgVsIniCet from '@/content/blog/neet-pg-vs-ini-cet';
import iniCetCutoff2024 from '@/content/blog/ini-cet-2024-cutoff-closing-ranks';
import cmsVsNeetPgVsIniCet from '@/content/blog/cms-vs-neet-pg-vs-ini-cet';
import bestPgBooks from '@/content/blog/best-pg-medical-entrance-books';

// September 2026 expansion — 50 new posts: clinical concepts, subject prep,
// exam strategy, career guides, and more.
import ecgInterpretation from '@/content/blog/ecg-interpretation-upsc-cms-made-easy';
import antibioticResistance from '@/content/blog/antibiotic-resistance-upsc-cms-guide';
import acidBaseInterpretation from '@/content/blog/acid-base-interpretation-made-simple';
import cnsAnatomyMnemonics from '@/content/blog/cns-anatomy-upsc-cms-mnemonics';
import imageBasedQuestions from '@/content/blog/image-based-questions-cms-strategy';
import timeManagement from '@/content/blog/time-management-upsc-cms-paper';
import omrMistakes from '@/content/blog/omr-filling-mistakes-upsc-cms';
import oneLinerMedicine from '@/content/blog/one-liner-medicine-upsc-cms';
import instituteOfImportance from '@/content/blog/institute-of-importance-upsc-cms';
import jobProfileMedicalOfficer from '@/content/blog/job-profile-medical-officer-upsc-cms';
import deepDiveHypertension from '@/content/blog/deep-dive-systemic-hypertension';
import deepDiveDiabetes from '@/content/blog/deep-dive-diabetes-mellitus-type2';
import deepDiveTuberculosis from '@/content/blog/deep-dive-tuberculosis';
import deepDiveNeonatalResuscitation from '@/content/blog/deep-dive-neonatal-resuscitation';
import deepDiveGynaeOncology from '@/content/blog/deep-dive-gynecological-oncology';
import neetPgVsCmsSalary from '@/content/blog/neet-pg-vs-cms-salary-lifestyle';
import governmentDoctorCareerPath from '@/content/blog/government-doctor-career-path';
import upscCmsVsSsc from '@/content/blog/upsc-cms-vs-ssc-choosing-right-exam';
import medicalCoachingWorthIt from '@/content/blog/medical-coaching-for-upsc-cms-worth-it';
import bestTimeToStartPrep from '@/content/blog/best-time-to-start-upsc-cms-preparation';
import neetPgToppersRoutine from '@/content/blog/neet-pg-toppers-routine-breakdown';
import deselectingOptions from '@/content/blog/deselecting-options-upsc-cms-technique';
import anatomyHighYield from '@/content/blog/anatomy-high-yield-topics-upsc-cms';
import physiologyRevisionTricks from '@/content/blog/physiology-revision-tricks-mnemonics';
import biochemistryMnemonics from '@/content/blog/biochemistry-metabolic-pathways-mnemonics';
import pharmacologyClassifications from '@/content/blog/pharmacology-drug-classifications-cms';
import pathologyGrossHisto from '@/content/blog/pathology-gross-histo-upsc-cms';
import microbiologyMustKnow from '@/content/blog/microbiology-upsc-cms-must-know';
import forensicMedicineEssentials from '@/content/blog/forensic-medicine-upsc-cms-essentials';
import psmEpidemiologyStats from '@/content/blog/psm-epidemiology-stats-cms';
import orthopaedicsFractures from '@/content/blog/orthopaedics-cms-common-fractures';
import dermatologyVisualGuide from '@/content/blog/dermatology-upsc-cms-visual-guide';
import radiologyBasics from '@/content/blog/radiology-basics-cms-aspirants';
import anaesthesiaMcqs from '@/content/blog/anaesthesia-mcqs-upsc-cms';
import psychiatryCommonDisorders from '@/content/blog/psychiatry-upsc-cms-common-disorders';
import eyeDiseases from '@/content/blog/eye-diseases-upsc-cms-quick-guide';
import entHighYield from '@/content/blog/ent-upsc-cms-high-yield';
import nutritionOverlooked from '@/content/blog/nutrition-upsc-cms-overlooked-topics';
import nursingProcedures from '@/content/blog/nursing-procedure-upsc-cms';
import emergencyMedicineQuick from '@/content/blog/emergency-medicine-upsc-cms-quick-reference';
import clinicalExamSkills from '@/content/blog/clinical-exam-skills-upsc-cms';
import commonEmergenciesManagement from '@/content/blog/common-medical-emergencies-management';
import negativeMarkingStrategy from '@/content/blog/negative-marking-strategy-upsc-cms';
import mockTestAnalysis from '@/content/blog/mock-test-analysis-upsc-cms';
import memorizationTechniques from '@/content/blog/memorization-techniques-medical-aspirants';
import stressManagement from '@/content/blog/stress-management-medical-exams';
import sleepOptimization from '@/content/blog/sleep-optimization-exam-performance';
import paper1VsPaper2Strategy from '@/content/blog/upsc-cms-paper-1-vs-paper-2-strategy';
import commonlyConfusedTopics from '@/content/blog/commonly-confused-topics-upsc-cms';
import readingComprehension from '@/content/blog/reading-comprehension-upsc-cms-stems';
import flashcardsSpacedRepetition from '@/content/blog/flashcards-spaced-repetition-upsc-cms';

// September 2026 expansion batch 2 — 50 more posts.
import surgerySuturing from '@/content/blog/surgery-suturing-techniques-upsc-cms';
import surgeryAnastomosis from '@/content/blog/surgery-anastomosis-types-cms';
import obgAntenatalCare from '@/content/blog/obg-antental-care-upsc-cms';
import contraceptionMethods from '@/content/blog/contraception-methods-upsc-cms';
import paedsImmunization from '@/content/blog/paediatrics-immunization-schedule-upsc-cms';
import paedsGrowthMilestones from '@/content/blog/paediatrics-growth-milestones-upsc-cms';
import psmNationalHealthPrograms from '@/content/blog/psm-national-health-programs-upsc-cms';
import surgeryBreastDiseases from '@/content/blog/surgery-breast-diseases-upsc-cms';
import surgeryThyroid from '@/content/blog/surgery-thyroid-upsc-cms';
import surgeryHerniaTypes from '@/content/blog/surgery-hernia-types-upsc-cms';
import obgLabourManagement from '@/content/blog/obg-labour-management-upsc-cms';
import obgGynaeDisorders from '@/content/blog/obg-gynaecology-common-disorders-upsc-cms';
import renalPhysiology from '@/content/blog/renal-physiology-upsc-cms';
import cardiacPhysiology from '@/content/blog/cardiac-physiology-upsc-cms';
import respiratoryPhysiology from '@/content/blog/respiratory-physiology-upsc-cms';
import cnsPhysiology from '@/content/blog/cns-physiology-upsc-cms';
import surgicalOncology from '@/content/blog/surgical-oncology-upsc-cms';
import urologyHighYield from '@/content/blog/urology-upsc-cms-high-yield';
import ophthalmologyGlaucoma from '@/content/blog/ophthalmology-glaucoma-upsc-cms';
import entHearingLoss from '@/content/blog/ent-hearing-loss-types-upsc-cms';
import orthoSpineInjuries from '@/content/blog/orthopaedics-spine-injuries-upsc-cms';
import giEndoscopy from '@/content/blog/gi-endoscopy-upsc-cms';
import clinicalCommunication from '@/content/blog/clinical-skills-communication-upsc-cms';
import dermatologyDrugEruptions from '@/content/blog/dermatology-drug-eruptions-leprosy-upsc-cms';
import medicineArrhythmias from '@/content/blog/medicine-arrhythmias-upsc-cms';
import medicineHeartFailure from '@/content/blog/medicine-heart-failure-upsc-cms';
import medicineValvular from '@/content/blog/medicine-valvular-heart-disease-upsc-cms';
import medicineCnsInfections from '@/content/blog/medicine-cns-infections-upsc-cms';
import medicineRheumatology from '@/content/blog/medicine-rheumatology-upsc-cms';
import medicineGastroenterology from '@/content/blog/medicine-gastroenterology-upsc-cms';
import medicineHaematology from '@/content/blog/medicine-haematology-upsc-cms';
import medicineNephrology from '@/content/blog/medicine-nephrology-upsc-cms';
import neetPgVsOtherExams from '@/content/blog/neet-pg-comedk-mss-nursing-exams-comparison';
import doctorBurnout from '@/content/blog/doctor-burnout-government-hospitals-upsc-cms';
import bloodPhysiology from '@/content/blog/physiology-blood-upsc-cms';
import neurologyStroke from '@/content/blog/neurology-stroke-upsc-cms';
import medicineEndocrinology from '@/content/blog/medicine-endocrinology-upsc-cms';
import medicineRespiratory from '@/content/blog/medicine-respiratory-upsc-cms';
import medicineCns from '@/content/blog/medicine-cns-upsc-cms';
import medicinePoisoning from '@/content/blog/medicine-poisoning-toxicology-upsc-cms';
import medicineSystemicSkin from '@/content/blog/medicine-dermatology-systemic-upsc-cms';
import surgeryAbdominal from '@/content/blog/surgery-abdominal-surgery-upsc-cms';
import medicineInfectiousDisease from '@/content/blog/medicine-infectious-disease-upsc-cms';
import pharmacologyCardiac from '@/content/blog/pharmacology-cardiac-drugs-upsc-cms';
import pharmacologyCns from '@/content/blog/pharmacology-cns-drugs-upsc-cms';
import obgObstetricEmergencies from '@/content/blog/obg-obstetric-emergencies-upsc-cms';
import obgGynaeOncology from '@/content/blog/obg-gynaecologic-oncology-upsc-cms';
import surgeryTumourMarkers from '@/content/blog/surgery-tumour-markers-upsc-cms';
import surgeryShock from '@/content/blog/surgery-shock-types-upsc-cms';
import anaesthesiaLocalRegional from '@/content/blog/anaesthesia-local-regional-upsc-cms';
import orthoArthritis from '@/content/blog/orthopaedics-arthritis-upsc-cms';
import orthoSoftTissue from '@/content/blog/orthopaedics-soft-tissue-upsc-cms';
import anaesthesiaObstetric from '@/content/blog/anaesthesia-obstetric-upsc-cms';
import radiologyChest from '@/content/blog/radiology-chest-xray-upsc-cms';
import radiologyAbdominal from '@/content/blog/radiology-abdominal-imaging-upsc-cms';
import pathologyGeneral from '@/content/blog/pathology-general-upsc-cms';
import pathologySystemic from '@/content/blog/pathology-systemic-upsc-cms';
import medicineRheumatologyAdvanced from '@/content/blog/medicine-rheumatology-advanced-upsc-cms';
import medicineCriticalCare from '@/content/blog/medicine-critical-care-upsc-cms';
import surgeryTrauma from '@/content/blog/surgery-trauma-upsc-cms';
import forensicToxicology from '@/content/blog/forensic-medicine-toxicology-upsc-cms';
import forensicIdentification from '@/content/blog/forensic-medicine-identification-upsc-cms';
import medicineHaemOncology from '@/content/blog/medicine-hematology-oncology-upsc-cms';
import psmBiostatistics from '@/content/blog/psm-biostatistics-formulas-upsc-cms';
import psmCommunityMedicine from '@/content/blog/psm-community-medicine-upsc-cms';

/**
 * EEAT-grade blog post shape.
 *
 * The shape was rebuilt specifically to support Google's March-2024 +
 * August-2024 core updates that reward experience + authoritativeness
 * + transparency. Each meaningful signal is captured explicitly:
 *
 *   - `authorId`     → resolves to an AuthorProfile and is emitted as a
 *                      `Person` JSON-LD node (with `knowsAbout[]`,
 *                      `worksFor`, `sameAs`) on every post.
 *   - `reviewedBy`   → a separate, named reviewer profile with their
 *                      own Person block. Distinguishes writer from
 *                      reviewer — required for YMYL medical content.
 *   - `references`   → first-class source list rendered at the bottom
 *                      of every post and emitted as `citation[]` in the
 *                      Article JSON-LD.
 *   - `toc`          → ship an explicit Table of Contents; the post
 *                      layout renders it AND emits `speakable` for
 *                      Google Assistant + voice assistants.
 *   - `difficulty`   → "beginner" / "intermediate" / "advanced" → used
 *                      to filter, badge and summarise.
 *   - `revisionLog`  → appended to the bottom of every post so readers
 *                      can audit whether the content is fresh.
 *   - `updatedAt`    → distinct from `dateModified` — `updatedAt` is
 *                      editorial copy refresh; `dateModified` is the
 *                      last touched timestamp surfaced in JSON-LD.
 */
export interface BlogPost {
    /** URL slug, e.g. `upsc-cms-last-5-days-strategy` */
    slug: string;
    /** SEO title — used as `<title>` and `og:title`. Should be ≤ 60 chars
     *  to avoid Google truncation; the layout will append the site
     *  template automatically. */
    title: string;
    /** SEO description — used as meta description and `og:description`.
     *  Keep ≤ 160 chars. */
    description: string;
    /** Short excerpt — shown on cards + meta. ≤ 180 chars. */
    excerpt: string;
    /** Path to cover image under /public. Optional. */
    coverImage?: string;
    /** Primary category (used for /blog/category/<slug> hub pages). */
    category: string;
    /** Subcategory — used for the visual pill set in the hero. */
    subcategory?: string;
    /** Free-form tags shown as chips; power search + related-posts. */
    tags: string[];
    /** Difficulty — "beginner" | "intermediate" | "advanced" */
    difficulty: 'beginner' | 'intermediate' | 'advanced';
    /** Author slug (must exist in src/content/authors.ts). */
    authorId: string;
    /** Optional separate clinical reviewer. */
    reviewedBy?: string;
    /** Human-readable author byline (legacy field — derives from authorId). */
    author: string;
    /** Author role / credential. */
    authorRole: string;
    /** ISO date string. */
    datePublished: string;
    /** ISO date string — content refreshed on this date. */
    dateModified: string;
    /** ISO date string — last editorial copy refresh (drives "Updated on …"). */
    updatedAt: string;
    /** Reading time as stored: the seed's metadata in the static posts, the
     *  body-derived value from the API. Display postReadingStats(post). */
    readingTime: string;
    /** Word count as stored: the seed's metadata in the static posts (mostly
     *  wrong), the body-derived count from the API. Display postReadingStats(post). */
    wordCount?: number;
    /** Inline CTA shown above the fold. Use helpful framing
     *  ("Practise 50 matched PYQs" — not "Sign up now!"). */
    primaryCta: {
        label: string;
        href: string;
        eventName?: string;
        eventParams?: Record<string, unknown>;
    };
    /** Related exam / topic paths surfaced as secondary CTAs. */
    relatedExamPaths?: string[];
    /** FAQ items — also emitted as FAQPage JSON-LD. */
    faqs: { q: string; a: string }[];
    /** Stable Table of Contents — headings the layout wires up to scroll-spy
     *  AND emits as `speakable[]` for Google Assistant. If empty, the
     *  layout auto-builds one from `body` h2s. */
    toc: { id: string; label: string }[];
    /** Medical / official references — rendered at the bottom of every
     *  post AND emitted as `citation[]` in Article JSON-LD. */
    references: { label: string; url?: string; published?: string }[];
    /** Revision log (oldest → newest). Surfaced in the post footer. */
    revisionLog?: { date: string; note: string }[];
    /** Full markdown body. */
    body: string;
    /** Optional React snippet shown at the very top of the post. */
    prelude?: ReactNode;
    /** Optional React snippet shown at the very bottom (after FAQ + CTA). */
    outro?: ReactNode;
    /** "Pinned" / "Trending" flags surfaced on the hub cards. */
    pinned?: boolean;
    trending?: boolean;
}

/**
 * The static posts, in registration order: the seed of the blog database and
 * the build-time fallback (see "Static posts" below). The public pages read
 * the database.
 */
const registeredPosts: BlogPost[] = [
    // Original 4 posts.
    cms2026Notification,
    cmsLast5Days,
    cmsNeetPgLastWeek,
    neetPgVsUpscCms,
    // August 2026 expansion — 6 new posts.
    cmsSyllabusHighYield,
    cmsCutoff2024,
    cmsPrepStrategy6Month,
    neetPgCutoff2024,
    neetPgPrepStrategy,
    neetPgVsIniCet,
    iniCetCutoff2024,
    cmsVsNeetPgVsIniCet,
    bestPgBooks,
    // September 2026 expansion — 50 new posts.
    ecgInterpretation,
    antibioticResistance,
    acidBaseInterpretation,
    cnsAnatomyMnemonics,
    imageBasedQuestions,
    timeManagement,
    omrMistakes,
    oneLinerMedicine,
    instituteOfImportance,
    jobProfileMedicalOfficer,
    deepDiveHypertension,
    deepDiveDiabetes,
    deepDiveTuberculosis,
    deepDiveNeonatalResuscitation,
    deepDiveGynaeOncology,
    neetPgVsCmsSalary,
    governmentDoctorCareerPath,
    upscCmsVsSsc,
    medicalCoachingWorthIt,
    bestTimeToStartPrep,
    neetPgToppersRoutine,
    deselectingOptions,
    anatomyHighYield,
    physiologyRevisionTricks,
    biochemistryMnemonics,
    pharmacologyClassifications,
    pathologyGrossHisto,
    microbiologyMustKnow,
    forensicMedicineEssentials,
    psmEpidemiologyStats,
    orthopaedicsFractures,
    dermatologyVisualGuide,
    radiologyBasics,
    anaesthesiaMcqs,
    psychiatryCommonDisorders,
    eyeDiseases,
    entHighYield,
    nutritionOverlooked,
    nursingProcedures,
    emergencyMedicineQuick,
    clinicalExamSkills,
    commonEmergenciesManagement,
    negativeMarkingStrategy,
    mockTestAnalysis,
    memorizationTechniques,
    stressManagement,
    sleepOptimization,
    paper1VsPaper2Strategy,
    commonlyConfusedTopics,
    readingComprehension,
    flashcardsSpacedRepetition,
    // September 2026 batch 2 — 50 more posts.
    surgerySuturing,
    surgeryAnastomosis,
    obgAntenatalCare,
    contraceptionMethods,
    paedsImmunization,
    paedsGrowthMilestones,
    psmNationalHealthPrograms,
    surgeryBreastDiseases,
    surgeryThyroid,
    surgeryHerniaTypes,
    obgLabourManagement,
    obgGynaeDisorders,
    renalPhysiology,
    cardiacPhysiology,
    respiratoryPhysiology,
    cnsPhysiology,
    surgicalOncology,
    urologyHighYield,
    ophthalmologyGlaucoma,
    entHearingLoss,
    orthoSpineInjuries,
    giEndoscopy,
    clinicalCommunication,
    dermatologyDrugEruptions,
    medicineArrhythmias,
    medicineHeartFailure,
    medicineValvular,
    medicineCnsInfections,
    medicineRheumatology,
    medicineGastroenterology,
    medicineHaematology,
    medicineNephrology,
    neetPgVsOtherExams,
    doctorBurnout,
    bloodPhysiology,
    neurologyStroke,
    medicineEndocrinology,
    medicineRespiratory,
    medicineCns,
    medicinePoisoning,
    medicineSystemicSkin,
    surgeryAbdominal,
    medicineInfectiousDisease,
    pharmacologyCardiac,
    pharmacologyCns,
    obgObstetricEmergencies,
    obgGynaeOncology,
    surgeryTumourMarkers,
    surgeryShock,
    anaesthesiaLocalRegional,
    orthoArthritis,
    orthoSoftTissue,
    anaesthesiaObstetric,
    radiologyChest,
    radiologyAbdominal,
    pathologyGeneral,
    pathologySystemic,
    medicineRheumatologyAdvanced,
    medicineCriticalCare,
    surgeryTrauma,
    forensicToxicology,
    forensicIdentification,
    medicineHaemOncology,
    psmBiostatistics,
    psmCommunityMedicine,
];

// Newest first. Posts published on the same day keep the order the site has
// always shown them in (the most recently registered first); the old in-place
// sort got that from a comparator that never returned 0.
const posts: BlogPost[] = registeredPosts
    .map((post, index) => ({ post, index }))
    .sort((a, b) => compareDesc(a.post.datePublished, b.post.datePublished) || b.index - a.index)
    .map(({ post }) => post);

function compareDesc(a: string, b: string): number {
    if (a === b) return 0;
    return a < b ? 1 : -1;
}

// ── Static posts ────────────────────────────────────────────────────────────
//
// The public blog renders the posts in the database (blog_engine, edited at
// /admin/blog) through loadBlogCatalog / loadBlogPost below. The static
// modules registered above are what `manage.py seed_blogs` imports
// (backend/blog_engine/seed_data/static_posts.json, kept in step by
// tests/unit/blog-seed-snapshot.test.ts) and what `next build` renders when the
// API cannot be reached. The synchronous helpers below read the static posts.

/** The static posts, newest first. */
export function getAllPosts(): BlogPost[] {
    return posts;
}

/** A static post by slug, or undefined. */
export function getPostBySlug(slug: string): BlogPost | undefined {
    return posts.find((p) => p.slug === slug);
}

/**
 * Social / structured-data image for a post: the generated 1200×630 card
 * from app/blog/[slug]/opengraph-image.tsx. The `coverImage` paths in the
 * content files (/blog/og/<x>-cover.png) were never added to /public, so
 * every twitter:image, Article JSON-LD image and RSS enclosure that used
 * them was a 404.
 */
export function postSocialImagePath(post: Pick<BlogPost, 'slug'>): string {
    return `/blog/${post.slug}/opengraph-image`;
}

/** All static post slugs. */
export function getAllPostSlugs(): string[] {
    return posts.map((p) => p.slug);
}

/** Catalog a post page attached with linkRelatedPosts (see getRelatedPosts). */
const relatedCatalogs = new WeakMap<BlogPost, BlogPost[]>();

/**
 * Let getRelatedPosts(post) pick related posts from `catalog` (the published
 * posts in the database) instead of the static posts. BlogPostLayout calls
 * getRelatedPosts(post, 2) itself; the post page links the live catalog to the
 * post object it renders.
 */
export function linkRelatedPosts(post: BlogPost, catalog: BlogPost[]): BlogPost {
    relatedCatalogs.set(post, catalog);
    return post;
}

/** Up to N related posts that share ≥ 1 tag with the source post. */
export function getRelatedPosts(source: BlogPost, n = 2): BlogPost[] {
    return relatedPostsFrom(relatedCatalogs.get(source) ?? posts, source, n);
}

/** All unique static categories with at least one post. */
export function getAllCategories(): { name: string; slug: string; count: number }[] {
    return categoriesOf(posts);
}

/** Static posts in a category, newest first. */
export function getPostsByCategory(categorySlug: string): BlogPost[] {
    return postsInCategory(posts, categorySlug);
}

/**
 * Static posts with a given tag, newest first. Matches on the same slug
 * transform the tag pages and tag chips use (tagToSlug), so tags with hyphens
 * or symbols ("INI-CET", "High-Yield", "X-ray", "ACC/AHA") resolve too.
 */
export function getPostsByTag(tagSlug: string): BlogPost[] {
    return postsWithTag(posts, tagSlug);
}

/**
 * Tag archives with fewer posts than this are thin pages: they stay
 * reachable from tag chips but are marked noindex and left out of the
 * sitemap.
 */
export const MIN_INDEXABLE_TAG_POSTS = 3;

/** All unique static tags with their post counts (see tagsOf). */
export function getAllTags(): { name: string; slug: string; count: number }[] {
    return tagsOf(posts);
}

/** Look up a static tag (merged across spellings) by its slug. */
export function getTagBySlug(tagSlug: string): { name: string; slug: string; count: number } | undefined {
    return tagOf(posts, tagSlug);
}

/** Turn a category or tag display name into a URL-safe slug. */
export function categoryToSlug(name: string): string {
    return name
        .toLowerCase()
        .replace(/&/g, 'and')
        .replace(/[^a-z0-9]+/g, '-')
        .replace(/(^-|-$)/g, '');
}

/** Tags have a stricter transform — drop leading "and " etc. */
export function tagToSlug(name: string): string {
    return categoryToSlug(name);
}

/** Find the top `n` trending posts (pinned first, then newest). */
export function getFeaturedPosts(n = 4): BlogPost[] {
    const pinned = posts.filter((p) => p.pinned);
    const rest = posts.filter((p) => !p.pinned).slice(0, Math.max(0, n - pinned.length));
    return [...pinned, ...rest].slice(0, n);
}

/** Word count of a markdown body: the site's one rule (lib/blogText countBlogWords). */
export const countWords = countBlogWords;

export { formatPostDate, slugifyHeading };

export interface ReadingStats {
    words: number;
    minutes: number;
    /** "N min" */
    label: string;
}

/**
 * Word count and reading time a card or the post header shows. A post with
 * its body (the post page, the static posts) is counted here; a catalog row
 * (no body) carries the count the API computed from the body
 * (blog_engine.text_stats, the same rule). The posts' own `readingTime` /
 * `wordCount` fields are the seed's metadata and are never shown: most
 * claimed about 2,000 words for a ~100-word body.
 */
export function postReadingStats(post: Pick<BlogPost, 'body' | 'wordCount'>): ReadingStats {
    const words = post.body?.trim()
        ? countBlogWords(post.body)
        : typeof post.wordCount === 'number' && post.wordCount >= 0 ? post.wordCount : 0;
    return { words, minutes: readingMinutes(words), label: readingTimeLabel(words) };
}

/**
 * What a post card shows, as plain data: client components (the /blog
 * explorer) receive this instead of BlogPost so they never import this
 * module, which bundles every static post.
 */
export interface BlogCardData {
    slug: string;
    title: string;
    excerpt: string;
    category: string;
    author: string;
    /** ISO date the card shows (last update, else publication). */
    date: string;
    readingLabel: string;
    tags: string[];
    coverImage?: string;
    pinned?: boolean;
}

export function toCardData(post: BlogPost): BlogCardData {
    const cover = post.coverImage ? resolveBlogMediaUrl(post.coverImage) : '';
    return {
        slug: post.slug,
        title: post.title,
        excerpt: post.excerpt,
        category: post.category,
        author: post.author,
        date: post.dateModified || post.datePublished,
        readingLabel: postReadingStats(post).label,
        tags: post.tags.slice(0, 8),
        ...(cover ? { coverImage: cover } : {}),
        ...(post.pinned ? { pinned: true } : {}),
    };
}

/** Origin uploaded blog images (/api/blog/images/...) are served from: the API's. */
export function blogImageOrigin(env: BlogApiEnv = currentBlogApiEnv()): string {
    try {
        return new URL(blogApiBaseUrl(env)).origin;
    } catch {
        return '';
    }
}

/** A cover / media path as the browser loads it: /api/... paths point at the API origin. */
export function resolveBlogMediaUrl(src: string, env: BlogApiEnv = currentBlogApiEnv()): string {
    const value = safeLinkTarget(src);
    if (value.startsWith('/api/')) {
        const origin = blogImageOrigin(env);
        return origin ? `${origin}${value}` : value;
    }
    return value;
}

/** Auto-build a Table of Contents from a markdown body
 *  (h2 / h3 only). Returns stable ids so anchors survive SSG. */
export function buildAutoToc(markdown: string): { id: string; label: string; level: 2 | 3 }[] {
    const lines = markdown.split(/\r?\n/);
    const out: { id: string; label: string; level: 2 | 3 }[] = [];
    let inCode = false;
    for (const line of lines) {
        if (line.startsWith('```')) { inCode = !inCode; continue; }
        if (inCode) continue;
        const m = /^(#{2,3})\s+(.+?)\s*$/.exec(line);
        if (!m) continue;
        const level = m[1].length as 2 | 3;
        const label = m[2].replace(/[`*_]/g, '').trim();
        out.push({ id: slugifyHeading(label), label, level });
    }
    return out;
}

// ── Helpers over any list of posts (static or from the database) ────────────

/** Unique categories of `list` with their post counts, largest first. */
export function categoriesOf(list: BlogPost[]): { name: string; slug: string; count: number }[] {
    const map = new Map<string, number>();
    list.forEach((p) => {
        if (p.category) map.set(p.category, (map.get(p.category) ?? 0) + 1);
    });
    return Array.from(map.entries())
        .map(([name, count]) => ({ name, slug: categoryToSlug(name), count }))
        .filter((c) => c.slug)
        .sort((a, b) => b.count - a.count);
}

/** Posts of `list` in a category (by category slug), in list order. */
export function postsInCategory(list: BlogPost[], categorySlug: string): BlogPost[] {
    return list.filter((p) => categoryToSlug(p.category) === categorySlug);
}

/** Posts of `list` carrying a tag (any spelling with the same tag slug), in list order. */
export function postsWithTag(list: BlogPost[], tagSlug: string): BlogPost[] {
    const wanted = tagToSlug(tagSlug);
    return list.filter((p) => p.tags.some((t) => tagToSlug(t) === wanted));
}

/**
 * Unique tags of `list` with their post counts. Tags that differ only in case,
 * spacing or punctuation ("High-Yield Topics" / "high yield topics") share one
 * slug and are merged into a single entry; the first spelling seen is used as
 * the display name. A post is counted once per tag slug.
 */
export function tagsOf(list: BlogPost[]): { name: string; slug: string; count: number }[] {
    const map = new Map<string, { name: string; count: number }>();
    list.forEach((p) => {
        const seen = new Set<string>();
        p.tags.forEach((t) => {
            const slug = tagToSlug(t);
            if (!slug || seen.has(slug)) return;
            seen.add(slug);
            const entry = map.get(slug);
            if (entry) entry.count += 1;
            else map.set(slug, { name: t, count: 1 });
        });
    });
    return Array.from(map.entries())
        .map(([slug, { name, count }]) => ({ name, slug, count }))
        .sort((a, b) => b.count - a.count);
}

/** A tag of `list` (merged across spellings) by its slug. */
export function tagOf(list: BlogPost[], tagSlug: string): { name: string; slug: string; count: number } | undefined {
    const wanted = tagToSlug(tagSlug);
    return tagsOf(list).find((t) => t.slug === wanted);
}

/** Up to N posts of `list` sharing ≥ 1 tag with `source`, most shared tags first. */
export function relatedPostsFrom(list: BlogPost[], source: BlogPost, n = 2): BlogPost[] {
    const sourceTags = new Set(source.tags.map((t) => t.toLowerCase()));
    return list
        .filter((p) => p.slug !== source.slug)
        .map((p) => ({ post: p, shared: p.tags.reduce((acc, t) => acc + (sourceTags.has(t.toLowerCase()) ? 1 : 0), 0) }))
        .filter((s) => s.shared > 0)
        .sort((a, b) => b.shared - a.shared)
        .slice(0, n)
        .map((s) => s.post);
}

/** Author and reviewer profile slugs credited in `list` (first seen first). */
export function authorSlugsOf(list: BlogPost[]): string[] {
    const slugs = new Set<string>();
    for (const p of list) {
        if (p.authorId) slugs.add(p.authorId);
        if (p.reviewedBy) slugs.add(p.reviewedBy);
    }
    return Array.from(slugs);
}

/** dateModified (else datePublished) as a Date; `fallback` when neither parses. */
export function postLastModified(post: Pick<BlogPost, 'dateModified' | 'datePublished'>, fallback: Date): Date {
    for (const value of [post.dateModified, post.datePublished]) {
        const d = new Date(value || '');
        if (!isNaN(d.getTime())) return d;
    }
    return fallback;
}

// ── Database records ────────────────────────────────────────────────────────

/** primary_cta as blog_engine stores it (the seed and older rows use snake_case keys). */
export interface BlogCtaRecord {
    label?: string;
    href?: string;
    event_name?: string;
    event_params?: Record<string, unknown>;
}

/**
 * A post as blog_engine stores it (BlogPostSerializer fields) and as
 * backend/blog_engine/seed_data/static_posts.json lists the static posts.
 */
export interface BlogPostRecord {
    slug: string;
    title: string;
    description: string;
    excerpt: string;
    cover_image: string;
    category: string;
    subcategory: string;
    tags: string[];
    difficulty: BlogPost['difficulty'];
    author_id: string;
    reviewed_by: string;
    author: string;
    author_role: string;
    date_published: string;
    date_modified: string;
    updated_at: string;
    reading_time: string;
    word_count: number | null;
    primary_cta: BlogCtaRecord;
    related_exam_paths: string[];
    faqs: { q: string; a: string }[];
    toc: { id: string; label: string }[];
    references: { label: string; url?: string; published?: string }[];
    revision_log: { date: string; note: string }[];
    body: string;
    prelude: string;
    outro: string;
    pinned: boolean;
    trending: boolean;
}

/** CTA shown when a post has none (or an unusable one). */
export const DEFAULT_PRIMARY_CTA: BlogPost['primaryCta'] = {
    label: 'Practise UPSC CMS PYQs',
    href: '/questions?exam=cms',
};

/** prelude / outro are stored as markdown text; a React element cannot be. */
function snippetText(value: unknown, field: string, slug: string): string {
    if (value === undefined || value === null) return '';
    if (typeof value === 'string') return value;
    throw new Error(`${slug}: ${field} is not text, so it cannot be stored in the database; write it as markdown`);
}

/** The record seed_blogs imports for a static post. Throws for a non-text prelude/outro. */
export function postToRecord(post: BlogPost): BlogPostRecord {
    const cta = post.primaryCta;
    return {
        slug: post.slug,
        title: post.title,
        description: post.description,
        excerpt: post.excerpt,
        cover_image: post.coverImage ?? '',
        category: post.category,
        subcategory: post.subcategory ?? '',
        tags: [...post.tags],
        difficulty: post.difficulty,
        author_id: post.authorId,
        reviewed_by: post.reviewedBy ?? '',
        author: post.author,
        author_role: post.authorRole,
        date_published: post.datePublished,
        date_modified: post.dateModified ?? '',
        updated_at: post.updatedAt ?? '',
        reading_time: post.readingTime,
        word_count: post.wordCount ?? null,
        primary_cta: {
            label: cta.label,
            href: cta.href,
            ...(cta.eventName ? { event_name: cta.eventName } : {}),
            ...(cta.eventParams ? { event_params: { ...cta.eventParams } } : {}),
        },
        related_exam_paths: [...(post.relatedExamPaths ?? [])],
        faqs: post.faqs.map(({ q, a }) => ({ q, a })),
        toc: post.toc.map(({ id, label }) => ({ id, label })),
        references: post.references.map(({ label, url, published }) => ({
            label,
            ...(url ? { url } : {}),
            ...(published ? { published } : {}),
        })),
        revision_log: (post.revisionLog ?? []).map(({ date, note }) => ({ date, note })),
        body: post.body,
        prelude: snippetText(post.prelude, 'prelude', post.slug),
        outro: snippetText(post.outro, 'outro', post.slug),
        pinned: post.pinned === true,
        trending: post.trending === true,
    };
}

const DIFFICULTIES: ReadonlySet<string> = new Set(['beginner', 'intermediate', 'advanced']);

function text(value: unknown): string {
    return typeof value === 'string' ? value : '';
}

function textList(value: unknown): string[] {
    return Array.isArray(value) ? value.filter((v): v is string => typeof v === 'string' && v.trim() !== '') : [];
}

function objectList(value: unknown): Record<string, unknown>[] {
    return Array.isArray(value)
        ? value.filter((v): v is Record<string, unknown> => !!v && typeof v === 'object' && !Array.isArray(v))
        : [];
}

function plainObject(value: unknown): Record<string, unknown> | undefined {
    return value && typeof value === 'object' && !Array.isArray(value) ? (value as Record<string, unknown>) : undefined;
}

/** An internal path (not protocol-relative) or an http(s) URL; '' for anything else (javascript:, data:, ...). */
export function safeLinkTarget(href: string): string {
    const value = href.trim();
    if (value.startsWith('/') && !value.startsWith('//')) return value;
    return /^https?:\/\/[^\s]+$/i.test(value) ? value : '';
}

function ctaFromRecord(value: unknown): BlogPost['primaryCta'] {
    const cta = plainObject(value) ?? {};
    const label = text(cta.label).trim();
    const href = safeLinkTarget(text(cta.href));
    if (!label || !href) return { ...DEFAULT_PRIMARY_CTA };
    const eventName = text(cta.event_name ?? cta.eventName).trim();
    const eventParams = plainObject(cta.event_params ?? cta.eventParams);
    return {
        label,
        href,
        ...(eventName ? { eventName } : {}),
        ...(eventParams ? { eventParams } : {}),
    };
}

/**
 * A post from an API record, or null when the record is not a usable public
 * post: no slug / title, or a draft (`is_published: false` — drafts are never
 * rendered, whatever the API returned). Partial records (the catalog has no
 * body), both CTA key spellings and malformed list items are tolerated; link
 * targets other than internal paths and http(s) URLs are dropped.
 */
export function postFromRecord(input: unknown): BlogPost | null {
    const r = plainObject(input);
    if (!r) return null;
    const slug = text(r.slug).trim();
    const title = text(r.title).trim();
    if (!slug || !title || r.is_published === false) return null;
    const difficulty = text(r.difficulty);
    const datePublished = text(r.date_published);
    const dateModified = text(r.date_modified) || datePublished;
    const relatedExamPaths = textList(r.related_exam_paths).filter((p) => safeLinkTarget(p).startsWith('/'));
    const revisionLog = objectList(r.revision_log)
        .map((e) => ({ date: text(e.date), note: text(e.note) }))
        .filter((e) => e.note);
    return {
        slug,
        title,
        description: text(r.description),
        excerpt: text(r.excerpt),
        coverImage: safeLinkTarget(text(r.cover_image)) || undefined,
        category: text(r.category),
        subcategory: text(r.subcategory) || undefined,
        tags: textList(r.tags),
        difficulty: DIFFICULTIES.has(difficulty) ? (difficulty as BlogPost['difficulty']) : 'intermediate',
        authorId: text(r.author_id) || 'crackcms-editorial',
        reviewedBy: text(r.reviewed_by) || undefined,
        author: text(r.author),
        authorRole: text(r.author_role),
        datePublished,
        dateModified,
        updatedAt: text(r.updated_at) || dateModified,
        readingTime: text(r.reading_time),
        wordCount: typeof r.word_count === 'number' && Number.isFinite(r.word_count) ? r.word_count : undefined,
        primaryCta: ctaFromRecord(r.primary_cta),
        relatedExamPaths: relatedExamPaths.length ? relatedExamPaths : undefined,
        faqs: objectList(r.faqs)
            .map((f) => ({ q: text(f.q), a: text(f.a) }))
            .filter((f) => f.q && f.a),
        toc: objectList(r.toc)
            .map((t) => ({ id: text(t.id), label: text(t.label) }))
            .filter((t) => t.id && t.label),
        references: objectList(r.references)
            .map((ref) => {
                const url = safeLinkTarget(text(ref.url));
                const published = text(ref.published);
                return { label: text(ref.label), ...(url ? { url } : {}), ...(published ? { published } : {}) };
            })
            .filter((ref) => ref.label),
        revisionLog: revisionLog.length ? revisionLog : undefined,
        body: text(r.body),
        prelude: text(r.prelude) || undefined,
        outro: text(r.outro) || undefined,
        pinned: r.pinned === true,
        trending: r.trending === true,
    };
}

// ── Live posts (the database) ───────────────────────────────────────────────

/**
 * ISR window, in seconds, of every public blog route and of its API reads. A
 * post created, edited, unpublished or deleted at /admin/blog shows on the
 * site within about twice this time: a regenerated page may still use the
 * previous API response while Next.js refreshes it in the background (a new
 * slug renders on its first request). Route files repeat the literal
 * (`export const revalidate = 300`): Next.js only reads a statically
 * analysable number there.
 */
export const BLOG_REVALIDATE_SECONDS = 300;

/** Per-request timeout of a blog API read. */
const BLOG_API_TIMEOUT_MS = 10_000;

export interface BlogApiEnv {
    BLOG_API_URL?: string;
    NEXT_PUBLIC_API_URL?: string;
    NODE_ENV?: string;
    VERCEL?: string;
}

function currentBlogApiEnv(): BlogApiEnv {
    return {
        BLOG_API_URL: process.env.BLOG_API_URL,
        NEXT_PUBLIC_API_URL: process.env.NEXT_PUBLIC_API_URL,
        NODE_ENV: process.env.NODE_ENV,
        VERCEL: process.env.VERCEL,
    };
}

/**
 * Absolute API base the server reads the blog from: BLOG_API_URL (server-only
 * override), else NEXT_PUBLIC_API_URL, else the production API in a production
 * build and the local backend otherwise. Relative values (the local
 * /api/proxy), retired hosts (lib/apiBase.ts) and a localhost URL on Vercel
 * are skipped.
 */
export function blogApiBaseUrl(env: BlogApiEnv = currentBlogApiEnv()): string {
    for (const raw of [env.BLOG_API_URL, env.NEXT_PUBLIC_API_URL]) {
        const configured = (raw || '').trim();
        if (!/^https?:\/\//i.test(configured)) continue;
        const normalized = normalizeApiBaseUrl(configured);
        if (isKnownUnhealthyApiHost(normalized)) continue;
        if (env.VERCEL && isLocalhostApiUrl(normalized)) continue;
        return normalized;
    }
    return env.NODE_ENV === 'production' ? DEFAULT_PRODUCTION_API_URL : DEFAULT_LOCAL_API_URL;
}

export type BlogFailurePolicy = 'fallback' | 'throw';

/**
 * What a failed blog API read does. During `next build`, in development and in
 * tests the static posts are used, so a build never fails on the API. A
 * production server throws instead: ISR then keeps serving the page it last
 * generated from the database, rather than swapping in static copies (which
 * would bring back posts unpublished or deleted in the admin).
 */
export function blogFailurePolicy(
    env: { NODE_ENV?: string; NEXT_PHASE?: string } = { NODE_ENV: process.env.NODE_ENV, NEXT_PHASE: process.env.NEXT_PHASE },
): BlogFailurePolicy {
    if (env.NEXT_PHASE === 'phase-production-build') return 'fallback';
    return env.NODE_ENV === 'production' ? 'throw' : 'fallback';
}

/** BLOG_SOURCE=static: never call the API (hermetic tests and builds). */
function staticSourceForced(): boolean {
    return (process.env.BLOG_SOURCE || '').trim().toLowerCase() === 'static';
}

function isBuildPhase(): boolean {
    return process.env.NEXT_PHASE === 'phase-production-build';
}

// Set during `next build` once the API failed: this build worker renders the
// remaining pages from the static posts straight away instead of waiting for
// a timeout on every page.
let apiFailedDuringBuild = false;
let fallbackWarned = false;

async function blogApiGet(path: string): Promise<{ status: number; data: unknown }> {
    const init = {
        headers: { Accept: 'application/json', 'User-Agent': 'cracklabs-web-blog (Next.js server)' },
        signal: AbortSignal.timeout(BLOG_API_TIMEOUT_MS),
        next: { revalidate: BLOG_REVALIDATE_SECONDS, tags: ['blog'] },
    };
    const res = await fetch(`${blogApiBaseUrl()}${path}`, init as RequestInit);
    if (res.status === 404) return { status: 404, data: null };
    if (!res.ok) throw new Error(`the blog API answered ${res.status} for ${path}`);
    return { status: res.status, data: await res.json() };
}

/** `value` read from the API (`live`), or the static fallback. */
async function readLive<T>(what: string, load: () => Promise<T>, fallback: () => T): Promise<{ value: T; live: boolean }> {
    if (staticSourceForced()) return { value: fallback(), live: false };
    const building = isBuildPhase();
    if (building && apiFailedDuringBuild) return { value: fallback(), live: false };
    try {
        try {
            return { value: await load(), live: true };
        } catch (first) {
            if (!building) throw first;
            return { value: await load(), live: true }; // one retry during a build
        }
    } catch (err) {
        if (blogFailurePolicy() === 'throw') throw err;
        if (building) apiFailedDuringBuild = true;
        if (!fallbackWarned) {
            fallbackWarned = true;
            const reason = err instanceof Error ? err.message : String(err);
            console.warn(`[blog] Could not read ${what} from ${blogApiBaseUrl()} (${reason}); using the static posts.`);
        }
        return { value: fallback(), live: false };
    }
}

function readCatalog() {
    return readLive(
        'the post list',
        async () => {
            const { data } = await blogApiGet('/blog/posts/catalog/');
            const rows = Array.isArray(data) ? data : plainObject(data)?.results;
            if (!Array.isArray(rows)) throw new Error('the blog catalog is missing');
            return rows.map(postFromRecord).filter((p): p is BlogPost => p !== null);
        },
        getAllPosts,
    );
}

/**
 * Every published post, newest first, without bodies: what cards, hubs,
 * related posts, the feed and the sitemap need (GET /api/blog/posts/catalog/).
 */
export async function loadBlogCatalog(): Promise<BlogPost[]> {
    return (await readCatalog()).value;
}

const LOOKUP_SLUG = /^[A-Za-z0-9_-]{1,200}$/;

/**
 * One published post with its body (GET /api/blog/posts/by-slug/<slug>/), or
 * null when there is none: never published, a draft, or deleted.
 *
 * Where failures fall back (a build, development) a post comes from the same
 * source as the post list: when the list is the static one (API unreachable,
 * or an older backend without the catalog), so is the post, and no database
 * row (an old seed's placeholder or summary) is mixed into the static pages.
 * The catalog read is a cached fetch the page makes anyway.
 */
export async function loadBlogPost(slug: string): Promise<BlogPost | null> {
    if (!LOOKUP_SLUG.test(slug)) return null;
    const staticPost = () => getPostBySlug(slug) ?? null;
    if (!staticSourceForced() && blogFailurePolicy() === 'fallback' && !(await readCatalog()).live) {
        return staticPost();
    }
    return (await readLive(
        `the post ${slug}`,
        async () => {
            const { status, data } = await blogApiGet(`/blog/posts/by-slug/${encodeURIComponent(slug)}/`);
            return status === 404 ? null : postFromRecord(data);
        },
        staticPost,
    )).value;
}
