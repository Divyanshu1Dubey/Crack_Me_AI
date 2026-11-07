/**
 * Layout preferences (Settings > Customise): the order of the sidebar's sections and links, the
 * links a learner hides, the order and visibility of the dashboard widgets, the page the app
 * opens on, the question-bank tools a learner hides and the mode the question bank opens in.
 *
 * Customisation only reorders and hides. A hidden link moves to the sidebar's "More" group and a
 * hidden widget or tool can be turned back on in Settings, so every feature stays reachable. The
 * sidebar's Admin group is not customisable. The question bank's answer flow (options, Submit, the
 * answer and its explanation, navigation) is not a tool, "Flag Issue" is never hidden, and hiding a
 * tool unlocks nothing: premium gating stays on the server and in the pages.
 *
 * Pure (no React, no network, no DOM) so tests/unit can import it. The server keeps the choice per
 * user (GET / PATCH /api/auth/preferences/, backend/accounts/preferences.py) and accepts only the
 * ids below; tests/unit/preferences.test.ts checks that both sides list the same ids in the same
 * order. components/customize/preferencesStore.ts loads, caches and saves them.
 */

// ── Sidebar catalog ────────────────────────────────────────────────────────

export interface NavItemDef {
    /** Stable id, stored in the preferences (never change one; add a new id instead). */
    id: string;
    href: string;
    iconName: string;
    label: string;
    badge?: string;
    adminOnly?: boolean;
    requireTrack?: string[];
    /** Freemium gate (Task 10): if true, free users see a lock icon next to
     *  the label, and clicking opens the UpgradeModal. Premium + admin
     *  users see no lock and the link is fully clickable. */
    premium?: boolean;
    /** Display label used in the upgrade modal trigger — defaults to `label`. */
    premiumFeature?: string;
}

export interface NavSectionDef {
    id: string;
    title: string;
    items: NavItemDef[];
}

/** The student sections of the sidebar in their default order (the Admin group is separate). */
export const SIDEBAR_SECTIONS: readonly NavSectionDef[] = [
    {
        id: 'study',
        title: 'Study',
        items: [
            { id: 'dashboard', href: '/dashboard', iconName: 'dashboard-layout', label: 'Dashboard' },
            // Freemium: free users get a "Premium" badge next to Question Bank
            // but the link still routes — clicks inside the bank hit the
            // backend filter (Task 6) which restricts to 10 showcase items.
            { id: 'questions', href: '/questions', iconName: 'question-bank-book', label: 'Question Bank', premium: true, premiumFeature: 'Full PYQ practice' },
            { id: 'tests', href: '/tests', iconName: 'tests-check', label: 'Tests', premium: true, premiumFeature: 'Mock Tests' },
            { id: 'flashcards', href: '/flashcards', iconName: 'flashcards-cards', label: 'Flashcards', premium: true, premiumFeature: 'Flashcards' },
            { id: 'simulator', href: '/simulator', iconName: 'simulator-target', label: 'CMS Simulator', premium: true, premiumFeature: 'Mock Tests' },
            { id: 'mistake-notebook', href: '/mistake-notebook', iconName: 'book-open', label: 'Mistake Notebook' },
            { id: 'study-time', href: '/study-time', iconName: 'clock', label: 'Study Time' },
        ],
    },
    {
        id: 'ai-tools',
        title: 'AI Tools',
        items: [
            { id: 'ai-tutor', href: '/ai-tutor', iconName: 'ai-tutor-brain', label: 'AI Tutor', badge: 'AI', premium: true, premiumFeature: 'AI Tutor' },
            { id: 'generate', href: '/generate', iconName: 'ai-questions-creativity', label: 'Question Generator', badge: 'AI', premium: true, premiumFeature: 'AI Tutor' },
            // Same name as the page heading and the Header title.
            { id: 'roadmap', href: '/roadmap', iconName: 'study-roadmap-map', label: 'Study Roadmap', badge: 'AI', premium: true, premiumFeature: 'AI Tutor' },
        ],
    },
    {
        id: 'resources',
        title: 'Resources',
        items: [
            { id: 'resources', href: '/resources', iconName: 'resources-folder', label: 'Resources' },
            { id: 'textbooks', href: '/textbooks', iconName: 'textbooks-open-book', label: 'Textbooks' },
            { id: 'jobs', href: '/jobs', iconName: 'briefcase', label: 'Jobs Portal', requireTrack: ['cms'] },
            { id: 'trends', href: '/trends', iconName: 'trends-graph', label: 'Exam Trends' },
            { id: 'upload', href: '/upload', iconName: 'upload-train', label: 'Upload & Train', adminOnly: true },
        ],
    },
    {
        id: 'account',
        title: 'Account',
        items: [
            // Analytics is open to every signed-in user: no Deep Analytics
            // gate was ever built (no 402, no locked state on /analytics), so
            // a lock here only opened the upgrade modal on a free page (AN-08).
            { id: 'analytics', href: '/analytics', iconName: 'analytics-growth', label: 'Analytics' },
            { id: 'leaderboard', href: '/leaderboard', iconName: 'leaderboard-trophy', label: 'Leaderboard' },
            { id: 'bookmarks', href: '/bookmarks', iconName: 'bookmarks-ribbon', label: 'Bookmarks' },
            { id: 'subscription', href: '/subscription', iconName: 'subscription-gold', label: 'Subscription' },
            { id: 'feedback', href: '/feedback', iconName: 'feedback-chat', label: 'Feedback' },
            { id: 'contact', href: '/contact', iconName: 'contact-support', label: 'Contact Us' },
            { id: 'quests', href: '/quests', iconName: 'flame', label: 'Quests' },
            { id: 'topic-notes', href: '/topic-notes', iconName: 'file-text', label: 'Topic Notes' },
        ],
    },
];

export const SIDEBAR_SECTION_IDS: readonly string[] = SIDEBAR_SECTIONS.map((section) => section.id);
export const SIDEBAR_ITEM_IDS: readonly string[] = SIDEBAR_SECTIONS.flatMap((section) => section.items.map((item) => item.id));

const SECTION_BY_ID = new Map(SIDEBAR_SECTIONS.map((section) => [section.id, section]));
const ITEM_BY_ID = new Map(SIDEBAR_SECTIONS.flatMap((section) => section.items.map((item) => [item.id, item] as const)));

export function sidebarItem(id: string): NavItemDef | undefined {
    return ITEM_BY_ID.get(id);
}

/** Map generic /questions href → exam-specific dedicated player URL.
 *  Phase 9: each exam with image-rich recalls gets its own player route. */
export const EXAM_TRACK_PLAYER_HREF: Readonly<Record<string, string>> = {
    neet_pg: '/questions/neet-pg/practice',
    ini_cet: '/questions/inicet/practice',
};

/** The link's target for the exam track: /questions opens the track's own player (NEET PG, INI-CET). */
export function resolveNavHref(href: string, track: string): string {
    return href === '/questions' && EXAM_TRACK_PLAYER_HREF[track] ? EXAM_TRACK_PLAYER_HREF[track] : href;
}

/** Whether the sidebar offers `item` to this viewer at all (admin-only links, exam-track links). */
export function navItemAvailable(item: NavItemDef, viewer: { isAdmin: boolean; track: string }): boolean {
    return (!item.adminOnly || viewer.isAdmin) && (!item.requireTrack || item.requireTrack.includes(viewer.track));
}

// ── Dashboard catalog ──────────────────────────────────────────────────────

export const DASHBOARD_WIDGET_IDS = [
    'announcements', 'welcome', 'upgrade', 'stats', 'toolkit', 'today', 'calendar',
    'focus-subjects', 'momentum', 'mastery', 'streak',
] as const;
export type DashboardWidgetId = (typeof DASHBOARD_WIDGET_IDS)[number];

/** Widgets that may be moved but never hidden: the free plan's upgrade row. */
export const DASHBOARD_ALWAYS_SHOWN_IDS: readonly DashboardWidgetId[] = ['upgrade'];

/** `full`: the page width. `main` / `side`: consecutive ones share a row on wide screens (8 + 4 columns). */
export type WidgetLayout = 'full' | 'main' | 'side';

export interface DashboardWidgetDef {
    label: string;
    description: string;
    layout: WidgetLayout;
}

export const DASHBOARD_WIDGETS: Readonly<Record<DashboardWidgetId, DashboardWidgetDef>> = {
    announcements: { label: 'Platform announcements', description: 'Notices from the CrackLabs team. They are also under the bell icon.', layout: 'full' },
    welcome: { label: 'Welcome card', description: "Next exam day, your streak, today's questions and accuracy.", layout: 'full' },
    upgrade: { label: 'Premium features', description: 'Shown on the free plan. You can move it but not hide it.', layout: 'full' },
    stats: { label: 'Progress summary', description: 'Tests completed, questions attempted, study time and XP.', layout: 'full' },
    toolkit: { label: 'AI prep toolkit', description: 'Shortcuts to the question generator, AI tutor, simulator and roadmap.', layout: 'full' },
    today: { label: "Today's focus", description: 'Questions, tests and minutes today, your daily goal and accuracy.', layout: 'main' },
    calendar: { label: 'Study activity calendar', description: 'Your practice over the last 16 weeks.', layout: 'main' },
    'focus-subjects': { label: 'Subjects to focus on', description: 'Your three weakest subjects.', layout: 'side' },
    momentum: { label: 'Campus momentum', description: 'A link to your weekly leaderboard rank.', layout: 'side' },
    mastery: { label: 'Question bank mastery', description: 'Solved questions by difficulty, year and subject.', layout: 'full' },
    streak: { label: 'Streak stats', description: 'Longest streak and total study days.', layout: 'full' },
};

export function widgetAlwaysShown(id: string): boolean {
    return (DASHBOARD_ALWAYS_SHOWN_IDS as readonly string[]).includes(id);
}

// ── Opening page ───────────────────────────────────────────────────────────

/** Pages the app may open on: sidebar links (their label and href come from the sidebar catalog). */
export const LANDING_PAGE_IDS = [
    'dashboard', 'questions', 'tests', 'flashcards', 'simulator', 'mistake-notebook',
    'ai-tutor', 'roadmap', 'analytics', 'bookmarks',
] as const;
export type LandingPageId = (typeof LANDING_PAGE_IDS)[number];
export const DEFAULT_LANDING_PAGE: LandingPageId = 'dashboard';

export function isLandingPageId(value: unknown): value is LandingPageId {
    return typeof value === 'string' && (LANDING_PAGE_IDS as readonly string[]).includes(value);
}

export function landingPageLabel(id: LandingPageId): string {
    return sidebarItem(id)?.label ?? id;
}

// ── Question bank catalog ──────────────────────────────────────────────────

/**
 * Tools a learner may switch off, in their default order: what is shown with a question in the
 * question bank (/questions, the NEET PG and INI-CET banks) and the full-screen year practice,
 * then the toolbar and panels of a practice session (/practice).
 */
export const QUESTION_BANK_TOOL_IDS = [
    'ai-analysis', 'mnemonic', 'textbook-reference', 'find-in-textbook', 'similar-pyqs', 'citations',
    'video', 'discussion', 'report', 'shortcuts',
    'review-flag', 'confidence', 'strike', 'time-spent', 'provenance', 'related-pyqs', 'related-topics',
] as const;
export type QuestionBankToolId = (typeof QUESTION_BANK_TOOL_IDS)[number];

/** Tools that are never hidden: "Flag Issue" is how wrong answer keys get reported. */
export const QUESTION_BANK_ALWAYS_SHOWN_IDS: readonly QuestionBankToolId[] = ['report'];

/** `bank`: the question bank and the full-screen year practice. `session`: a practice session (/practice). */
export type QuestionBankToolGroup = 'bank' | 'session';

export interface QuestionBankToolDef {
    label: string;
    description: string;
    group: QuestionBankToolGroup;
}

export const QUESTION_BANK_TOOLS: Readonly<Record<QuestionBankToolId, QuestionBankToolDef>> = {
    'ai-analysis': { label: 'AI analysis', description: 'The "Generate AI Analysis" button and the analysis it writes.', group: 'bank' },
    mnemonic: { label: 'Memory trick', description: 'The mnemonic saved with the question.', group: 'bank' },
    'textbook-reference': { label: 'Textbook reference', description: 'The book, chapter and page saved with the question.', group: 'bank' },
    'find-in-textbook': { label: 'Find in Textbook', description: 'Look up the textbook page that covers the topic.', group: 'bank' },
    'similar-pyqs': { label: 'Similar PYQs', description: 'Other past questions on the same topic.', group: 'bank' },
    citations: { label: 'Textbook citations', description: 'Reviewed textbook passages that support the answer.', group: 'bank' },
    video: { label: 'AI video explanation', description: 'Shown when the question has a video.', group: 'bank' },
    discussion: { label: 'Discussion', description: "Students' comments on the question.", group: 'bank' },
    report: { label: 'Flag Issue', description: 'Report a wrong answer key or a typo. Always shown.', group: 'bank' },
    shortcuts: { label: 'Keyboard shortcut hints', description: 'The A–D, N and P reminder under the question.', group: 'bank' },
    'review-flag': { label: 'Flag for review', description: 'Mark a question to come back to.', group: 'session' },
    confidence: { label: 'Confidence rating', description: 'Rate how sure you were, from 1 to 5.', group: 'session' },
    strike: { label: 'Strike out options', description: 'Cross out the options you have ruled out.', group: 'session' },
    'time-spent': { label: 'Time spent', description: 'How long you have spent on the question.', group: 'session' },
    provenance: { label: 'Provenance', description: 'Where the question comes from.', group: 'session' },
    'related-pyqs': { label: 'Related PYQs', description: 'Past questions linked to this one.', group: 'session' },
    'related-topics': { label: 'Related topics', description: 'Topics linked to this question.', group: 'session' },
};

export interface QuestionBankToolGroupDef {
    id: QuestionBankToolGroup;
    title: string;
    description: string;
    /** Where the tools show, for the switches' names ("Show Discussion in the question bank"). */
    where: string;
}

export const QUESTION_BANK_TOOL_GROUPS: readonly QuestionBankToolGroupDef[] = [
    {
        id: 'bank',
        title: 'Question bank',
        description: 'Shown with a question in the question bank and in full-screen year practice.',
        where: 'in the question bank',
    },
    {
        id: 'session',
        title: 'Practice sessions',
        description: 'The toolbar and panels of a practice session (Random, Weak topics, Timed mock and the other modes).',
        where: 'in practice sessions',
    },
];

/** The tools of one group, in catalog order. */
export function questionBankToolIds(group: QuestionBankToolGroup): QuestionBankToolId[] {
    return QUESTION_BANK_TOOL_IDS.filter((id) => QUESTION_BANK_TOOLS[id].group === group);
}

export function toolAlwaysShown(id: string): boolean {
    return (QUESTION_BANK_ALWAYS_SHOWN_IDS as readonly string[]).includes(id);
}

/** The question bank's modes: practice shows the answer when an option is picked, exam waits for Submit. */
export const STUDY_MODE_IDS = ['practice', 'exam'] as const;
export type StudyMode = (typeof STUDY_MODE_IDS)[number];
export const DEFAULT_STUDY_MODE: StudyMode = 'practice';

/** The names the question bank's mode switch uses. */
export const STUDY_MODE_LABELS: Readonly<Record<StudyMode, string>> = {
    practice: 'Practice Mode',
    exam: 'Exam Mode',
};

export function isStudyMode(value: unknown): value is StudyMode {
    return typeof value === 'string' && (STUDY_MODE_IDS as readonly string[]).includes(value);
}

// ── Stored shape ───────────────────────────────────────────────────────────

export interface SidebarPreferences {
    /** Section ids in the learner's order (ids it does not name follow, in default order). */
    sections?: string[];
    /** Link ids in the learner's order; a link never leaves its section. */
    items?: string[];
    /** Link ids moved to the "More" group. */
    hidden?: string[];
}

export interface DashboardPreferences {
    order?: string[];
    hidden?: string[];
}

export interface QuestionBankPreferences {
    /** Tool ids the learner switched off (never "Flag Issue"). */
    hidden?: string[];
    /** The mode the question bank opens in; absent: practice. */
    study_mode?: StudyMode;
}

/** Only what the learner changed; `{}` is the default layout. */
export interface UiPreferences {
    sidebar?: SidebarPreferences;
    dashboard?: DashboardPreferences;
    landing_page?: LandingPageId;
    question_bank?: QuestionBankPreferences;
}

/** A PATCH body: each named key replaces the stored one, `null` removes it (back to the default). */
export type UiPreferencesPatch = { [K in keyof UiPreferences]?: UiPreferences[K] | null };

export const RESET_PATCH: UiPreferencesPatch = { sidebar: null, dashboard: null, landing_page: null, question_bank: null };

// ── Ordering helpers ───────────────────────────────────────────────────────

/**
 * `defaults` in the saved order: the saved ids first (unknown and repeated ones dropped), then the
 * ids the saved order does not mention (e.g. added in a later release), in their default order.
 */
export function applyOrder<T extends string>(defaults: readonly T[], saved?: readonly unknown[] | null): T[] {
    const known = new Set<string>(defaults);
    const seen = new Set<string>();
    const out: T[] = [];
    for (const id of saved ?? []) {
        if (typeof id === 'string' && known.has(id) && !seen.has(id)) {
            seen.add(id);
            out.push(id as T);
        }
    }
    for (const id of defaults) {
        if (!seen.has(id)) out.push(id);
    }
    return out;
}

/** `ids` without the hidden ones. */
export function withoutHidden<T extends string>(ids: readonly T[], hidden?: readonly unknown[] | null): T[] {
    if (!hidden || hidden.length === 0) return [...ids];
    const drop = new Set(hidden.filter((id): id is string => typeof id === 'string'));
    return ids.filter((id) => !drop.has(id));
}

/**
 * `order` with `id` one step up (-1) or down (+1). With `among`, a step skips the ids outside it
 * (the ones the learner does not see), so a link never jumps out of its section. Unchanged when
 * `id` is unknown or already first / last.
 */
export function moveId<T extends string>(order: readonly T[], id: T, direction: -1 | 1, among?: readonly T[]): T[] {
    const next = [...order];
    const from = next.indexOf(id);
    if (from < 0) return next;
    const scope = among ? new Set<string>(among) : null;
    let to = from + direction;
    while (to >= 0 && to < next.length && scope && !scope.has(next[to])) to += direction;
    if (to < 0 || to >= next.length) return next;
    [next[from], next[to]] = [next[to], next[from]];
    return next;
}

function sameOrder(a: readonly string[], b: readonly string[]): boolean {
    return a.length === b.length && a.every((id, i) => id === b[i]);
}

// ── Sidebar ────────────────────────────────────────────────────────────────

/** Section ids in the learner's order. */
export function sidebarSectionOrder(prefs?: SidebarPreferences | null): string[] {
    return applyOrder(SIDEBAR_SECTION_IDS, prefs?.sections);
}

/** The links of one section in the learner's order (hidden ones included). */
export function sectionItemOrder(sectionId: string, prefs?: SidebarPreferences | null): string[] {
    const section = SECTION_BY_ID.get(sectionId);
    return section ? applyOrder(section.items.map((item) => item.id), prefs?.items) : [];
}

/** Every link id, section by section (sections in default order), each section in the learner's order. */
export function sidebarItemOrder(prefs?: SidebarPreferences | null): string[] {
    return SIDEBAR_SECTION_IDS.flatMap((sectionId) => sectionItemOrder(sectionId, prefs));
}

export function sidebarHidden(prefs?: SidebarPreferences | null): Set<string> {
    return new Set(SIDEBAR_ITEM_IDS.filter((id) => prefs?.hidden?.includes(id)));
}

export interface SidebarLayout {
    /** Sections in the learner's order, each with its visible links in the learner's order. */
    sections: NavSectionDef[];
    /** Hidden links for the "More" group: by section, then by link, in the learner's order. */
    more: NavItemDef[];
}

export function sidebarLayout(prefs?: SidebarPreferences | null): SidebarLayout {
    const hidden = sidebarHidden(prefs);
    const sections: NavSectionDef[] = [];
    const more: NavItemDef[] = [];
    for (const sectionId of sidebarSectionOrder(prefs)) {
        const section = SECTION_BY_ID.get(sectionId);
        if (!section) continue;
        const items = sectionItemOrder(sectionId, prefs)
            .map((id) => ITEM_BY_ID.get(id))
            .filter((item): item is NavItemDef => item !== undefined);
        sections.push({ ...section, items: items.filter((item) => !hidden.has(item.id)) });
        more.push(...items.filter((item) => hidden.has(item.id)));
    }
    return { sections, more };
}

/** The sidebar preference to save: only the parts that differ from the default, or null (= the default). */
export function compactSidebar(
    sections: readonly string[],
    items: readonly string[],
    hidden: Iterable<string>,
): SidebarPreferences | null {
    const out: SidebarPreferences = {};
    const sectionOrder = applyOrder(SIDEBAR_SECTION_IDS, sections);
    const itemOrder = sidebarItemOrder({ items: [...items] });
    if (!sameOrder(sectionOrder, SIDEBAR_SECTION_IDS)) out.sections = sectionOrder;
    if (!sameOrder(itemOrder, SIDEBAR_ITEM_IDS)) out.items = itemOrder;
    const hiddenSet = new Set(hidden);
    const hiddenIds = SIDEBAR_ITEM_IDS.filter((id) => hiddenSet.has(id));
    if (hiddenIds.length) out.hidden = hiddenIds;
    return Object.keys(out).length ? out : null;
}

// ── Dashboard ──────────────────────────────────────────────────────────────

export function dashboardOrder(prefs?: DashboardPreferences | null): DashboardWidgetId[] {
    return applyOrder(DASHBOARD_WIDGET_IDS, prefs?.order);
}

/** Hidden widget ids (never the ones that are always shown). */
export function dashboardHidden(prefs?: DashboardPreferences | null): Set<DashboardWidgetId> {
    return new Set(DASHBOARD_WIDGET_IDS.filter((id) => !widgetAlwaysShown(id) && prefs?.hidden?.includes(id)));
}

/** Widgets to show, in order. `exclude`: widgets this viewer never gets (the upgrade row on a plan). */
export function visibleDashboardWidgets(
    prefs?: DashboardPreferences | null,
    exclude: readonly string[] = [],
): DashboardWidgetId[] {
    const hidden = dashboardHidden(prefs);
    return dashboardOrder(prefs).filter((id) => !hidden.has(id) && !exclude.includes(id));
}

/** Hidden widgets this viewer would otherwise see. */
export function hiddenDashboardWidgets(
    prefs?: DashboardPreferences | null,
    exclude: readonly string[] = [],
): DashboardWidgetId[] {
    const hidden = dashboardHidden(prefs);
    return dashboardOrder(prefs).filter((id) => hidden.has(id) && !exclude.includes(id));
}

export interface PlacedWidget {
    id: DashboardWidgetId;
    /** Position inside its block: the order on narrow screens, where the columns stack. */
    position: number;
}

export type DashboardBlock =
    | { kind: 'single'; id: DashboardWidgetId }
    | { kind: 'columns'; main: PlacedWidget[]; side: PlacedWidget[] };

/**
 * The dashboard as blocks, top to bottom. A run of consecutive `main` / `side` widgets that has
 * both kinds becomes a two-column block (main column left, side column right on wide screens, the
 * run's own order on phones); every other widget is a block of its own, the full width.
 */
export function dashboardBlocks(
    prefs?: DashboardPreferences | null,
    exclude: readonly string[] = [],
): DashboardBlock[] {
    const blocks: DashboardBlock[] = [];
    let run: DashboardWidgetId[] = [];
    const flush = () => {
        const main = run.filter((id) => DASHBOARD_WIDGETS[id].layout === 'main');
        const side = run.filter((id) => DASHBOARD_WIDGETS[id].layout === 'side');
        if (main.length && side.length) {
            const place = (id: DashboardWidgetId): PlacedWidget => ({ id, position: run.indexOf(id) });
            blocks.push({ kind: 'columns', main: main.map(place), side: side.map(place) });
        } else {
            for (const id of run) blocks.push({ kind: 'single', id });
        }
        run = [];
    };
    for (const id of visibleDashboardWidgets(prefs, exclude)) {
        if (DASHBOARD_WIDGETS[id].layout === 'full') {
            flush();
            blocks.push({ kind: 'single', id });
        } else {
            run.push(id);
        }
    }
    flush();
    return blocks;
}

/** The dashboard preference to save: only the parts that differ from the default, or null. */
export function compactDashboard(order: readonly string[], hidden: Iterable<string>): DashboardPreferences | null {
    const out: DashboardPreferences = {};
    const ordered = applyOrder(DASHBOARD_WIDGET_IDS, order);
    if (!sameOrder(ordered, DASHBOARD_WIDGET_IDS)) out.order = ordered;
    const hiddenSet = new Set(hidden);
    const hiddenIds = DASHBOARD_WIDGET_IDS.filter((id) => hiddenSet.has(id) && !widgetAlwaysShown(id));
    if (hiddenIds.length) out.hidden = hiddenIds;
    return Object.keys(out).length ? out : null;
}

// ── Opening page ───────────────────────────────────────────────────────────

export function landingPageOf(prefs?: UiPreferences | null): LandingPageId {
    const page = prefs?.landing_page;
    return isLandingPageId(page) ? page : DEFAULT_LANDING_PAGE;
}

/** Where the opening page lives for this exam track. */
export function landingHref(id: LandingPageId, track: string): string {
    return resolveNavHref(sidebarItem(id)?.href ?? '/dashboard', track);
}

// ── Question bank ──────────────────────────────────────────────────────────

/** Hidden tool ids (never the ones that are always shown). */
export function questionBankHidden(prefs?: QuestionBankPreferences | null): Set<QuestionBankToolId> {
    return new Set(QUESTION_BANK_TOOL_IDS.filter((id) => !toolAlwaysShown(id) && prefs?.hidden?.includes(id)));
}

/** The mode the question bank opens in. */
export function studyModeOf(prefs?: QuestionBankPreferences | null): StudyMode {
    const mode = prefs?.study_mode;
    return isStudyMode(mode) ? mode : DEFAULT_STUDY_MODE;
}

/** The question-bank preference to save: only what differs from the default, or null (= the default). */
export function compactQuestionBank(hidden: Iterable<string>, studyMode: string): QuestionBankPreferences | null {
    const out: QuestionBankPreferences = {};
    const hiddenSet = new Set(hidden);
    const hiddenIds = QUESTION_BANK_TOOL_IDS.filter((id) => hiddenSet.has(id) && !toolAlwaysShown(id));
    if (hiddenIds.length) out.hidden = hiddenIds;
    if (isStudyMode(studyMode) && studyMode !== DEFAULT_STUDY_MODE) out.study_mode = studyMode;
    return Object.keys(out).length ? out : null;
}

// ── Whole preferences ──────────────────────────────────────────────────────

function cleanIds(value: unknown, allowed: readonly string[], never: readonly string[] = []): string[] {
    if (!Array.isArray(value)) return [];
    const out: string[] = [];
    for (const id of value) {
        if (typeof id === 'string' && allowed.includes(id) && !never.includes(id) && !out.includes(id)) out.push(id);
    }
    return out;
}

/**
 * Preferences from the server or this browser's copy, without anything this build does not know
 * (unknown keys, unknown or repeated ids, wrong types). Never throws; junk gives `{}`.
 */
export function sanitizePreferences(raw: unknown): UiPreferences {
    if (!raw || typeof raw !== 'object' || Array.isArray(raw)) return {};
    const source = raw as Record<string, unknown>;
    const out: UiPreferences = {};

    const sidebar = source.sidebar;
    if (sidebar && typeof sidebar === 'object' && !Array.isArray(sidebar)) {
        const s = sidebar as Record<string, unknown>;
        const part: SidebarPreferences = {};
        const sections = cleanIds(s.sections, SIDEBAR_SECTION_IDS);
        const items = cleanIds(s.items, SIDEBAR_ITEM_IDS);
        const hidden = cleanIds(s.hidden, SIDEBAR_ITEM_IDS);
        if (sections.length) part.sections = sections;
        if (items.length) part.items = items;
        if (hidden.length) part.hidden = hidden;
        if (Object.keys(part).length) out.sidebar = part;
    }

    const dashboard = source.dashboard;
    if (dashboard && typeof dashboard === 'object' && !Array.isArray(dashboard)) {
        const d = dashboard as Record<string, unknown>;
        const part: DashboardPreferences = {};
        const order = cleanIds(d.order, DASHBOARD_WIDGET_IDS);
        const hidden = cleanIds(d.hidden, DASHBOARD_WIDGET_IDS, DASHBOARD_ALWAYS_SHOWN_IDS);
        if (order.length) part.order = order;
        if (hidden.length) part.hidden = hidden;
        if (Object.keys(part).length) out.dashboard = part;
    }

    if (isLandingPageId(source.landing_page)) out.landing_page = source.landing_page;

    const questionBank = source.question_bank;
    if (questionBank && typeof questionBank === 'object' && !Array.isArray(questionBank)) {
        const q = questionBank as Record<string, unknown>;
        const part: QuestionBankPreferences = {};
        const hidden = cleanIds(q.hidden, QUESTION_BANK_TOOL_IDS, QUESTION_BANK_ALWAYS_SHOWN_IDS);
        if (hidden.length) part.hidden = hidden;
        if (isStudyMode(q.study_mode)) part.study_mode = q.study_mode;
        if (Object.keys(part).length) out.question_bank = part;
    }
    return out;
}

/** `prefs` with each key of `patch` replaced (`null` removes it), like the server's PATCH. */
export function applyPreferencesPatch(prefs: UiPreferences, patch: UiPreferencesPatch): UiPreferences {
    const next: Record<string, unknown> = { ...prefs };
    for (const [key, value] of Object.entries(patch)) {
        if (value === undefined) continue; // not sent (JSON drops it), so the server keeps the key
        if (value === null) delete next[key];
        else next[key] = value;
    }
    return sanitizePreferences(next);
}
