/**
 * Layout preferences (Settings > Customise), checked on the pure helpers of src/lib/preferences.ts,
 * the preferences store (a capturing axios adapter, fake browser globals, no network) and the page
 * sources:
 *  - order: saved ids first, unknown / repeated ids dropped, ids the saved order does not name
 *    (new in a later release) appended in default order; moves stay inside the visible scope;
 *  - visibility: hidden links go to the sidebar's "More" group (nothing disappears), hidden widgets
 *    are left out, the free plan's upgrade row is never hidden; defaults when nothing is saved;
 *  - the dashboard's two-column rows; the opening page and its exam-track href;
 *  - the question bank: every tool shows and practice mode by default, "Flag Issue" is never
 *    hidden, the answer flow is no tool, only what differs from the default is stored, and the
 *    question bank / practice pages read the choices (the toolbar's Reveal is the page's reveal);
 *  - the ids match the backend allow-lists (backend/accounts/preferences.py), in the same order;
 *  - the store: defaults when signed out, this browser's copy first and the server's answer next,
 *    one PATCH per burst of changes, back to the saved layout when a save fails, reset.
 *
 * Run (from frontend/):
 *   node --import ./tests/unit/register-ts-alias.mjs --test tests/unit/preferences.test.ts
 */
import { test, beforeEach } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { installFakeBrowser } from './fake-browser.ts';
import {
    DASHBOARD_ALWAYS_SHOWN_IDS,
    DASHBOARD_WIDGETS,
    DASHBOARD_WIDGET_IDS,
    DEFAULT_STUDY_MODE,
    LANDING_PAGE_IDS,
    QUESTION_BANK_ALWAYS_SHOWN_IDS,
    QUESTION_BANK_TOOLS,
    QUESTION_BANK_TOOL_GROUPS,
    QUESTION_BANK_TOOL_IDS,
    RESET_PATCH,
    SIDEBAR_ITEM_IDS,
    SIDEBAR_SECTIONS,
    SIDEBAR_SECTION_IDS,
    STUDY_MODE_IDS,
    STUDY_MODE_LABELS,
    applyOrder,
    applyPreferencesPatch,
    compactDashboard,
    compactQuestionBank,
    compactSidebar,
    dashboardBlocks,
    hiddenDashboardWidgets,
    isStudyMode,
    landingHref,
    landingPageOf,
    moveId,
    navItemAvailable,
    questionBankHidden,
    questionBankToolIds,
    resolveNavHref,
    sanitizePreferences,
    sectionItemOrder,
    sidebarItem,
    sidebarItemOrder,
    sidebarLayout,
    studyModeOf,
    toolAlwaysShown,
    visibleDashboardWidgets,
    withoutHidden,
    type DashboardBlock,
} from '../../src/lib/preferences.ts';

const read = (relative: string) => readFileSync(fileURLToPath(new URL(relative, import.meta.url)), 'utf8');

// ── Ordering helpers ───────────────────────────────────────────────────────

test('applyOrder: saved ids first, unknown / repeated / non-string dropped, new ids appended in default order', () => {
    const defaults = ['a', 'b', 'c', 'd'] as const;
    assert.deepEqual(applyOrder(defaults, ['c', 'a']), ['c', 'a', 'b', 'd']);
    assert.deepEqual(applyOrder(defaults, ['d', 'gone', 'd', 3, null, 'b']), ['d', 'b', 'a', 'c']);
    assert.deepEqual(applyOrder(defaults, []), ['a', 'b', 'c', 'd']);
    assert.deepEqual(applyOrder(defaults, null), ['a', 'b', 'c', 'd']);
    assert.deepEqual(applyOrder(defaults, undefined), ['a', 'b', 'c', 'd']);
    // A saved order from before 'd' existed: 'd' goes last.
    assert.deepEqual(applyOrder(defaults, ['c', 'b', 'a']), ['c', 'b', 'a', 'd']);
});

test('withoutHidden drops the hidden ids and keeps the order', () => {
    assert.deepEqual(withoutHidden(['a', 'b', 'c'], ['b', 'zzz', 7]), ['a', 'c']);
    assert.deepEqual(withoutHidden(['a', 'b'], null), ['a', 'b']);
    assert.deepEqual(withoutHidden(['a', 'b'], []), ['a', 'b']);
});

test('moveId: one step, unchanged at the ends or for an unknown id, skipping ids outside the scope', () => {
    const order = ['a', 'b', 'c', 'd'];
    assert.deepEqual(moveId(order, 'c', -1), ['a', 'c', 'b', 'd']);
    assert.deepEqual(moveId(order, 'c', 1), ['a', 'b', 'd', 'c']);
    assert.deepEqual(moveId(order, 'a', -1), order);
    assert.deepEqual(moveId(order, 'd', 1), order);
    assert.deepEqual(moveId(order, 'x', 1), order);
    // 'b' is not shown to this learner: 'c' swaps with 'a'.
    assert.deepEqual(moveId(order, 'c', -1, ['a', 'c', 'd']), ['c', 'b', 'a', 'd']);
    // Nothing visible above: unchanged.
    assert.deepEqual(moveId(order, 'b', -1, ['b', 'c']), order);
    assert.notEqual(moveId(order, 'a', -1), order); // a copy, the input is not mutated
});

test('a link moves only inside its section', () => {
    const flat = sidebarItemOrder(null);
    const study = sectionItemOrder('study', null);
    // The last Study link cannot move down into AI Tools.
    const last = study[study.length - 1];
    assert.deepEqual(moveId(flat, last, 1, study), flat);
    const moved = moveId(flat, 'tests', -1, study);
    assert.deepEqual(sectionItemOrder('study', { items: moved }).slice(0, 3), ['dashboard', 'tests', 'questions']);
    assert.deepEqual(sectionItemOrder('ai-tools', { items: moved }), sectionItemOrder('ai-tools', null));
});

// ── Sidebar ────────────────────────────────────────────────────────────────

test('sidebarLayout: the defaults are the catalog, nothing under More', () => {
    for (const prefs of [undefined, null, {}]) {
        const layout = sidebarLayout(prefs);
        assert.deepEqual(layout.sections.map((s) => s.id), [...SIDEBAR_SECTION_IDS]);
        assert.deepEqual(layout.sections.flatMap((s) => s.items.map((i) => i.id)), [...SIDEBAR_ITEM_IDS]);
        assert.deepEqual(layout.more, []);
    }
});

test('sidebarLayout: section and link order applied, hidden links listed under More, nothing lost', () => {
    const layout = sidebarLayout({
        sections: ['account', 'study'],
        items: ['quests', 'analytics', 'tests', 'dashboard', 'retired-link'],
        hidden: ['leaderboard', 'tests', 'textbooks', 'unknown'],
    });
    assert.deepEqual(layout.sections.map((s) => s.id), ['account', 'study', 'ai-tools', 'resources']);
    const account = layout.sections[0].items.map((i) => i.id);
    assert.deepEqual(account.slice(0, 2), ['quests', 'analytics']);
    assert.ok(!account.includes('leaderboard'));
    const study = layout.sections[1].items.map((i) => i.id);
    assert.deepEqual(study.slice(0, 2), ['dashboard', 'questions']); // 'tests' is hidden
    // More: by section (learner's order), then by link.
    assert.deepEqual(layout.more.map((i) => i.id), ['leaderboard', 'tests', 'textbooks']);
    // Every link is either in a section or under More, exactly once.
    const everywhere = [...layout.sections.flatMap((s) => s.items), ...layout.more].map((i) => i.id).sort();
    assert.deepEqual(everywhere, [...SIDEBAR_ITEM_IDS].sort());
});

test('admin-only and exam-track links follow the same rules as before', () => {
    const upload = sidebarItem('upload')!;
    const jobs = sidebarItem('jobs')!;
    assert.equal(navItemAvailable(upload, { isAdmin: false, track: 'cms' }), false);
    assert.equal(navItemAvailable(upload, { isAdmin: true, track: 'cms' }), true);
    assert.equal(navItemAvailable(jobs, { isAdmin: false, track: 'cms' }), true);
    assert.equal(navItemAvailable(jobs, { isAdmin: false, track: 'neet_pg' }), false);
    assert.equal(resolveNavHref('/questions', 'neet_pg'), '/questions/neet-pg/practice');
    assert.equal(resolveNavHref('/questions', 'ini_cet'), '/questions/inicet/practice');
    assert.equal(resolveNavHref('/questions', 'cms'), '/questions');
    assert.equal(resolveNavHref('/tests', 'neet_pg'), '/tests');
    // The paywall flags stay on the catalog.
    assert.equal(sidebarItem('questions')?.premium, true);
    assert.equal(sidebarItem('analytics')?.premium, undefined);
});

test('compactSidebar stores only what differs from the default', () => {
    assert.equal(compactSidebar(SIDEBAR_SECTION_IDS, SIDEBAR_ITEM_IDS, []), null);
    assert.equal(compactSidebar([], [], new Set()), null);
    const items = moveId(sidebarItemOrder(null), 'tests', -1, sectionItemOrder('study', null));
    assert.deepEqual(compactSidebar(SIDEBAR_SECTION_IDS, items, ['quests', 'jobs']), {
        items: sidebarItemOrder({ items }),
        hidden: ['jobs', 'quests'], // catalog order
    });
    assert.deepEqual(compactSidebar(['account'], SIDEBAR_ITEM_IDS, []), {
        sections: ['account', 'study', 'ai-tools', 'resources'],
    });
});

// ── Dashboard ──────────────────────────────────────────────────────────────

const describeBlocks = (blocks: DashboardBlock[]) => blocks.map((block) => (block.kind === 'single'
    ? block.id
    : `[${block.main.map((w) => `${w.id}@${w.position}`).join(',')} | ${block.side.map((w) => `${w.id}@${w.position}`).join(',')}]`));

test('dashboardBlocks: the default layout (main + side columns between the full-width widgets)', () => {
    assert.deepEqual(describeBlocks(dashboardBlocks(null)), [
        'announcements', 'welcome', 'upgrade', 'stats', 'toolkit',
        '[today@0,calendar@1 | focus-subjects@2,momentum@3]',
        'mastery', 'streak',
    ]);
    // A plan holder never gets the upgrade row.
    assert.ok(!describeBlocks(dashboardBlocks(null, ['upgrade'])).includes('upgrade'));
});

test('dashboardBlocks: order, hidden widgets and runs without one kind', () => {
    const order = ['momentum', 'today', 'mastery', 'calendar', 'focus-subjects'];
    assert.deepEqual(describeBlocks(dashboardBlocks({ order })).slice(0, 3), [
        '[today@1 | momentum@0]', // the phone order keeps momentum first
        'mastery',
        '[calendar@0 | focus-subjects@1]',
    ]);
    // Side widgets hidden: the main ones are full width.
    assert.deepEqual(
        describeBlocks(dashboardBlocks({ hidden: ['focus-subjects', 'momentum'] })).slice(5, 7),
        ['today', 'calendar'],
    );
    const everything = [...DASHBOARD_WIDGET_IDS];
    assert.deepEqual(dashboardBlocks({ hidden: everything }).map((b) => (b.kind === 'single' ? b.id : 'cols')), ['upgrade']);
    assert.deepEqual(dashboardBlocks({ hidden: everything }, ['upgrade']), []);
});

test('the upgrade row can be moved but never hidden', () => {
    assert.deepEqual([...DASHBOARD_ALWAYS_SHOWN_IDS], ['upgrade']);
    const prefs = { order: ['streak', 'upgrade'], hidden: ['upgrade', 'toolkit'] };
    const visible = visibleDashboardWidgets(prefs);
    assert.deepEqual(visible.slice(0, 2), ['streak', 'upgrade']);
    assert.ok(!visible.includes('toolkit'));
    assert.deepEqual(hiddenDashboardWidgets(prefs), ['toolkit']);
    assert.deepEqual(compactDashboard(DASHBOARD_WIDGET_IDS, ['upgrade', 'toolkit']), { hidden: ['toolkit'] });
    assert.deepEqual(sanitizePreferences({ dashboard: { hidden: ['upgrade'] } }), {});
});

test('hiddenDashboardWidgets counts only widgets this viewer would see', () => {
    assert.deepEqual(hiddenDashboardWidgets({ hidden: ['announcements', 'streak'] }), ['announcements', 'streak']);
    assert.deepEqual(hiddenDashboardWidgets({ hidden: ['announcements'] }, ['announcements']), []);
    assert.deepEqual(hiddenDashboardWidgets(null), []);
});

test('compactDashboard stores only what differs from the default', () => {
    assert.equal(compactDashboard(DASHBOARD_WIDGET_IDS, []), null);
    assert.equal(compactDashboard([], new Set()), null);
    assert.deepEqual(compactDashboard(['streak'], ['calendar']), {
        order: ['streak', ...DASHBOARD_WIDGET_IDS.filter((id) => id !== 'streak')],
        hidden: ['calendar'],
    });
});

// ── Opening page ───────────────────────────────────────────────────────────

test('the opening page: dashboard by default, a known page, its href for the exam track', () => {
    assert.equal(landingPageOf(null), 'dashboard');
    assert.equal(landingPageOf({}), 'dashboard');
    assert.equal(landingPageOf({ landing_page: 'tests' }), 'tests');
    assert.equal(landingPageOf({ landing_page: 'upload' as never }), 'dashboard');
    assert.equal(landingHref('questions', 'cms'), '/questions');
    assert.equal(landingHref('questions', 'neet_pg'), '/questions/neet-pg/practice');
    assert.equal(landingHref('flashcards', 'neet_pg'), '/flashcards');
    for (const id of LANDING_PAGE_IDS) {
        const item = sidebarItem(id);
        assert.ok(item, `${id} is a sidebar link`);
        assert.ok(!item.adminOnly && !item.requireTrack, `${id} is open to every learner`);
    }
});

// ── Question bank ──────────────────────────────────────────────────────────

test('question bank: every tool shows and the bank opens in practice mode by default', () => {
    for (const prefs of [undefined, null, {}]) {
        assert.deepEqual([...questionBankHidden(prefs)], []);
        assert.equal(studyModeOf(prefs), 'practice');
    }
    assert.equal(DEFAULT_STUDY_MODE, 'practice');
    assert.deepEqual([...STUDY_MODE_IDS], ['practice', 'exam']);
    assert.equal(STUDY_MODE_LABELS.practice, 'Practice Mode'); // the names of the bank's own switch
    assert.equal(STUDY_MODE_LABELS.exam, 'Exam Mode');
    assert.equal(studyModeOf({ study_mode: 'exam' }), 'exam');
    assert.equal(studyModeOf({ study_mode: 'timed' as never }), 'practice');
    assert.equal(isStudyMode('exam'), true);
    assert.equal(isStudyMode('Exam'), false);
    assert.equal(isStudyMode(undefined), false);
});

test('question bank: hidden tools are left out, Flag Issue never is', () => {
    assert.deepEqual([...QUESTION_BANK_ALWAYS_SHOWN_IDS], ['report']);
    assert.equal(toolAlwaysShown('report'), true);
    assert.equal(toolAlwaysShown('strike'), false);
    const hidden = questionBankHidden({ hidden: ['strike', 'report', 'retired-tool', 'discussion'] });
    assert.deepEqual([...hidden].sort(), ['discussion', 'strike']);
    assert.ok(!hidden.has('report'));
});

test('compactQuestionBank stores only what differs from the default', () => {
    assert.equal(compactQuestionBank([], 'practice'), null);
    assert.equal(compactQuestionBank(new Set(), 'practice'), null);
    assert.equal(compactQuestionBank(['report'], 'practice'), null); // Flag Issue is never stored as hidden
    assert.equal(compactQuestionBank([], 'timed'), null); // an unknown mode is the default
    assert.deepEqual(compactQuestionBank([], 'exam'), { study_mode: 'exam' });
    // Catalog order, unknown ids dropped.
    assert.deepEqual(compactQuestionBank(['strike', 'gone', 'ai-analysis'], 'exam'), {
        hidden: ['ai-analysis', 'strike'], study_mode: 'exam',
    });
});

test('the question-bank catalog: a definition per tool, two groups, the answer flow is no tool', () => {
    assert.equal(new Set(QUESTION_BANK_TOOL_IDS).size, QUESTION_BANK_TOOL_IDS.length);
    assert.deepEqual(Object.keys(QUESTION_BANK_TOOLS).sort(), [...QUESTION_BANK_TOOL_IDS].sort());
    assert.deepEqual(QUESTION_BANK_TOOL_GROUPS.map((group) => group.id), ['bank', 'session']);
    const grouped = QUESTION_BANK_TOOL_GROUPS.flatMap((group) => questionBankToolIds(group.id));
    assert.deepEqual(grouped, [...QUESTION_BANK_TOOL_IDS]); // every tool in one group, catalog order
    assert.equal(QUESTION_BANK_TOOLS.report.group, 'bank');
    for (const flow of ['options', 'submit', 'answer', 'explanation', 'navigation', 'reveal']) {
        assert.ok(!(QUESTION_BANK_TOOL_IDS as readonly string[]).includes(flow), flow);
    }
});

// ── Whole preferences ──────────────────────────────────────────────────────

test('sanitizePreferences keeps only what this build knows', () => {
    for (const junk of [null, undefined, 'x', 3, [], [{}], { sidebar: 'x', dashboard: [] }]) {
        assert.deepEqual(sanitizePreferences(junk), {}, JSON.stringify(junk));
    }
    assert.deepEqual(sanitizePreferences({
        sidebar: { sections: ['study', 'study', 'gone'], items: 'tests', hidden: ['quests', 9], extra: ['x'] },
        dashboard: { order: ['welcome', 'old'], hidden: [] },
        landing_page: 'nowhere',
        theme: 'dark',
    }), { sidebar: { sections: ['study'], hidden: ['quests'] }, dashboard: { order: ['welcome'] } });
    const full = {
        sidebar: { hidden: ['jobs'] }, dashboard: { order: ['streak'] }, landing_page: 'tests',
        question_bank: { hidden: ['strike'], study_mode: 'exam' },
    };
    assert.deepEqual(sanitizePreferences(full), full);
    // The question bank: unknown / repeated tools, Flag Issue and unknown modes are dropped.
    assert.deepEqual(sanitizePreferences({
        question_bank: { hidden: ['strike', 'strike', 'report', 'gone', 4], study_mode: 'timed', order: ['strike'] },
    }), { question_bank: { hidden: ['strike'] } });
    for (const junk of [{ question_bank: 'exam' }, { question_bank: ['strike'] }, { question_bank: { hidden: ['report'] } }]) {
        assert.deepEqual(sanitizePreferences(junk), {}, JSON.stringify(junk));
    }
});

test('applyPreferencesPatch replaces named keys, null removes one, undefined keeps it', () => {
    const prefs = sanitizePreferences({ sidebar: { hidden: ['jobs'] }, landing_page: 'tests' });
    assert.deepEqual(applyPreferencesPatch(prefs, { dashboard: { hidden: ['streak'] } }), {
        sidebar: { hidden: ['jobs'] }, dashboard: { hidden: ['streak'] }, landing_page: 'tests',
    });
    assert.deepEqual(applyPreferencesPatch(prefs, { sidebar: { sections: ['account'] } }).sidebar, { sections: ['account'] });
    assert.deepEqual(applyPreferencesPatch(prefs, { landing_page: null }), { sidebar: { hidden: ['jobs'] } });
    assert.deepEqual(applyPreferencesPatch(prefs, { sidebar: undefined }), prefs);
    assert.deepEqual(applyPreferencesPatch(prefs, RESET_PATCH), {});
    const withBank = applyPreferencesPatch(prefs, { question_bank: { study_mode: 'exam' } });
    assert.deepEqual(withBank.question_bank, { study_mode: 'exam' });
    assert.deepEqual(applyPreferencesPatch(withBank, { question_bank: null }), prefs);
    assert.deepEqual(applyPreferencesPatch(withBank, RESET_PATCH), {});
    assert.deepEqual(Object.keys(RESET_PATCH).sort(), ['dashboard', 'landing_page', 'question_bank', 'sidebar']);
});

// ── Catalog and backend allow-lists ────────────────────────────────────────

test('catalog ids are unique; every widget has a definition; admin tools are not in the catalog', () => {
    assert.equal(new Set(SIDEBAR_SECTION_IDS).size, SIDEBAR_SECTION_IDS.length);
    assert.equal(new Set(SIDEBAR_ITEM_IDS).size, SIDEBAR_ITEM_IDS.length);
    assert.deepEqual(Object.keys(DASHBOARD_WIDGETS).sort(), [...DASHBOARD_WIDGET_IDS].sort());
    assert.ok(SIDEBAR_SECTIONS.flatMap((s) => s.items).every((item) => !item.href.startsWith('/admin')));
});

function pythonTuple(source: string, name: string): string[] {
    const match = source.match(new RegExp(`^${name} = \\(([^)]*)\\)`, 'm'));
    assert.ok(match, `${name} is defined in backend/accounts/preferences.py`);
    return [...match[1].matchAll(/'([^']*)'/g)].map((m) => m[1]);
}

test('the ids match the backend allow-lists (backend/accounts/preferences.py), in the same order', () => {
    const backend = read('../../../backend/accounts/preferences.py');
    assert.deepEqual(pythonTuple(backend, 'SIDEBAR_SECTION_IDS'), [...SIDEBAR_SECTION_IDS]);
    assert.deepEqual(pythonTuple(backend, 'SIDEBAR_ITEM_IDS'), [...SIDEBAR_ITEM_IDS]);
    assert.deepEqual(pythonTuple(backend, 'DASHBOARD_WIDGET_IDS'), [...DASHBOARD_WIDGET_IDS]);
    assert.deepEqual(pythonTuple(backend, 'DASHBOARD_ALWAYS_SHOWN_IDS'), [...DASHBOARD_ALWAYS_SHOWN_IDS]);
    assert.deepEqual(pythonTuple(backend, 'LANDING_PAGE_IDS'), [...LANDING_PAGE_IDS]);
    assert.deepEqual(pythonTuple(backend, 'QUESTION_BANK_TOOL_IDS'), [...QUESTION_BANK_TOOL_IDS]);
    assert.deepEqual(pythonTuple(backend, 'QUESTION_BANK_ALWAYS_SHOWN_IDS'), [...QUESTION_BANK_ALWAYS_SHOWN_IDS]);
    assert.deepEqual(pythonTuple(backend, 'STUDY_MODE_IDS'), [...STUDY_MODE_IDS]);
});

test('the question bank and practice pages read the question-bank choices', () => {
    const bank = read('../../src/components/question/ExamQuestionBank.tsx');
    assert.match(bank, /const questionBankPrefs = useQuestionBankPreferences\(\);/);
    // The saved mode applies until the student switches (or answers) on the page.
    assert.match(bank, /const studyMode: StudyMode = studyModeChoice \?\? questionBankPrefs\.studyMode;/);
    assert.equal((bank.match(/keepStudyMode\(\);/g) || []).length, 2);
    for (const tool of ['ai-analysis', 'mnemonic', 'textbook-reference', 'find-in-textbook', 'similar-pyqs',
        'citations', 'video', 'discussion', 'shortcuts']) {
        assert.match(bank, new RegExp(`shows\\('${tool}'\\)`), tool);
    }
    // Flag Issue and the answer flow are never behind a preference.
    assert.doesNotMatch(bank, /shows\('report'\)/);
    assert.match(bank, /<Flag className="w-3\.5 h-3\.5" \/> Flag Issue/);
    assert.match(bank, /href="\/settings#customise-question-bank"/);

    const year = read('../../src/app/questions/practice/page.tsx');
    assert.match(year, /const \{ shows \} = useQuestionBankPreferences\(\);/);
    for (const tool of ['ai-analysis', 'mnemonic', 'citations']) {
        assert.match(year, new RegExp(`shows\\('${tool}'\\)`), tool);
    }
    assert.doesNotMatch(year, /shows\('report'\)/);
    assert.match(year, /\{flagSection\}/);

    const session = read('../../src/app/practice/page.tsx');
    assert.match(session, /const \{ shows \} = useQuestionBankPreferences\(\);/);
    assert.match(session, /onReveal=\{\(\) => setRevealed\(true\)\}/);
    assert.match(session, /revealed=\{revealed\}/);
    assert.match(session, /shows=\{shows\}/);
    assert.match(session, /disabled=\{busy \|\| !!picked \|\| revealed \|\| q\.id !== qid\}/);
    for (const tool of ['strike', 'provenance', 'related-pyqs', 'related-topics']) {
        assert.match(session, new RegExp(`shows\\("${tool}"\\)`), tool);
    }
    // The per-question timer records study time whatever the student hides.
    assert.match(session, /\{qid \? <QuestionTimer questionId=\{qid\} \/> : null\}/);

    const toolbar = read('../../src/components/question/QuestionToolbar.tsx');
    assert.doesNotMatch(toolbar, /const \[revealed, setRevealed\]/, 'Reveal is the page\'s reveal, not a local flag');
    assert.match(toolbar, /onClick=\{onReveal\}/);
    for (const tool of ['review-flag', 'confidence', 'strike', 'time-spent']) {
        assert.match(toolbar, new RegExp(`shows\\("${tool}"\\)`), tool);
    }

    const settings = read('../../src/components/customize/CustomizeSection.tsx');
    assert.match(settings, /id="customise-question-bank"/);
    assert.match(settings, /updatePreferences\(\{ question_bank: null \}, \{ immediate: true \}\)/);
    // Flag Issue's switch is shown on and cannot be turned off.
    assert.match(settings, /title=\{fixed \? 'Always shown: it is how wrong answer keys get reported' : undefined\}/);
    assert.match(settings, /const shown = fixed \|\| !hiddenTools\.has\(id\);/);
});

test('the sidebar, dashboard and settings use the preferences', () => {
    const sidebar = read('../../src/components/Sidebar.tsx');
    assert.match(sidebar, /sidebarLayout\(prefs\.sidebar\)/);
    assert.match(sidebar, /navItemAvailable\(item, viewer\)/);
    assert.match(sidebar, /id="sidebar-more-links"/);
    assert.match(sidebar, /ADMIN_LINKS\.map/); // the Admin group is rendered as before, not customisable
    assert.doesNotMatch(sidebar, /const navSections/);
    const dashboard = read('../../src/app/dashboard/page.tsx');
    assert.match(dashboard, /dashboardBlocks\(prefs\.dashboard/);
    assert.match(dashboard, /useLandingRedirect\(ready\)/);
    assert.match(dashboard, /href="\/settings#customise"/);
    const settings = read('../../src/app/settings/page.tsx');
    assert.match(settings, /<CustomizeSection \/>/);
});

// ── Store ──────────────────────────────────────────────────────────────────

process.env.NEXT_PUBLIC_AUTH_MODE = 'local'; // no Supabase client in this test
const browser = installFakeBrowser('http://localhost:3000/settings');
const api = (await import('../../src/lib/api.ts')).default;
const store = await import('../../src/components/customize/preferencesStore.ts');

type Call = { method?: string; url?: string; body?: Record<string, unknown> };
let calls: Call[] = [];
let server: Record<string, unknown> = {};
let failNext: number | null = null;

const settle = (ms = 20) => new Promise((resolve) => setTimeout(resolve, ms));
const CACHE = 'crackcms_ui_prefs:';

beforeEach(async () => {
    store.activatePreferences(null);
    await settle();
    browser.storage.clear();
    calls = [];
    server = {};
    failNext = null;
    api.defaults.adapter = async (config) => {
        const body = typeof config.data === 'string' && config.data ? JSON.parse(config.data) : undefined;
        calls.push({ method: config.method, url: config.url, body });
        if (failNext !== null) {
            const status = failNext;
            failNext = null;
            throw Object.assign(new Error(`HTTP ${status}`), {
                config, isAxiosError: true, response: { status, data: { code: 'x' }, headers: {}, config },
            });
        }
        if (config.method === 'patch' && body) {
            for (const [key, value] of Object.entries(body)) {
                if (value === null) delete server[key];
                else server[key] = value;
            }
        }
        return { data: { preferences: server }, status: 200, statusText: 'OK', headers: {}, config };
    };
});

test('store: signed out gets the defaults and sends nothing', async () => {
    const snap = store.getPreferencesSnapshot();
    assert.equal(snap.userKey, null);
    assert.deepEqual(snap.prefs, {});
    assert.equal(snap.loaded, true);
    store.updatePreferences({ landing_page: 'tests' }, { immediate: true });
    await settle();
    assert.deepEqual(calls, []);
    assert.deepEqual(store.getServerPreferencesSnapshot().prefs, {});
});

test("store: this browser's copy first, then the server's answer (which is cached)", async () => {
    browser.storage.setItem(`${CACHE}5`, JSON.stringify({ v: 1, prefs: { landing_page: 'tests', junk: 1 } }));
    server = { landing_page: 'flashcards' };
    store.activatePreferences('5');
    let snap = store.getPreferencesSnapshot();
    assert.deepEqual(snap.prefs, { landing_page: 'tests' });
    assert.equal(snap.fromCache, true);
    assert.equal(snap.loaded, false);
    await settle();
    snap = store.getPreferencesSnapshot();
    assert.deepEqual(snap.prefs, { landing_page: 'flashcards' });
    assert.equal(snap.loaded, true);
    assert.equal(snap.fromCache, false);
    assert.deepEqual(calls.map((c) => `${c.method} ${c.url}`), ['get /auth/preferences/']);
    assert.deepEqual(JSON.parse(browser.storage.getItem(`${CACHE}5`)!).prefs, { landing_page: 'flashcards' });
    // A broken copy is ignored.
    store.activatePreferences(null);
    browser.storage.setItem(`${CACHE}6`, '{not json');
    store.activatePreferences('6');
    assert.deepEqual(store.getPreferencesSnapshot().prefs, {});
    assert.equal(store.getPreferencesSnapshot().fromCache, false);
    await settle();
});

test('store: changes apply at once and a burst of them is saved with one PATCH', async () => {
    store.activatePreferences('5');
    await settle();
    calls = [];
    store.updatePreferences({ sidebar: { hidden: ['quests'] } });
    store.updatePreferences({ dashboard: { hidden: ['streak'] } });
    store.updatePreferences({ sidebar: { hidden: ['quests', 'jobs'] } });
    assert.deepEqual(store.getPreferencesSnapshot().prefs, {
        sidebar: { hidden: ['quests', 'jobs'] }, dashboard: { hidden: ['streak'] },
    });
    assert.deepEqual(calls, []); // waits for a pause
    await settle(800);
    assert.equal(calls.length, 1);
    assert.equal(calls[0].method, 'patch');
    assert.deepEqual(calls[0].body, { sidebar: { hidden: ['quests', 'jobs'] }, dashboard: { hidden: ['streak'] } });
    const snap = store.getPreferencesSnapshot();
    assert.equal(snap.saving, false);
    assert.equal(snap.saveError, null);
    assert.deepEqual(JSON.parse(browser.storage.getItem(`${CACHE}5`)!).prefs, server);
});

test('store: a failed save goes back to the saved layout and says why', async () => {
    server = { landing_page: 'tests' };
    store.activatePreferences('5');
    await settle();
    failNext = 429;
    store.updatePreferences({ landing_page: 'analytics' }, { immediate: true });
    assert.equal(store.getPreferencesSnapshot().prefs.landing_page, 'analytics');
    await settle();
    const snap = store.getPreferencesSnapshot();
    assert.equal(snap.prefs.landing_page, 'tests');
    assert.match(snap.saveError ?? '', /Too many changes/);
    // The next change clears the message.
    store.updatePreferences({ landing_page: 'bookmarks' }, { immediate: true });
    assert.equal(store.getPreferencesSnapshot().saveError, null);
    await settle();
    assert.deepEqual(server, { landing_page: 'bookmarks' });
});

test("store: reset sends every key as null; another user's answers are ignored", async () => {
    server = { landing_page: 'tests', sidebar: { hidden: ['jobs'] } };
    store.activatePreferences('5');
    await settle();
    store.resetPreferences();
    await settle();
    assert.deepEqual(calls.at(-1)?.body, { sidebar: null, dashboard: null, landing_page: null, question_bank: null });
    assert.deepEqual(store.getPreferencesSnapshot().prefs, {});

    // Switching user while a GET is out: the old answer never shows for the new user.
    server = { landing_page: 'flashcards' };
    store.activatePreferences('7');
    store.activatePreferences('8');
    assert.equal(store.getPreferencesSnapshot().userKey, '8');
    await settle();
    assert.equal(store.getPreferencesSnapshot().userKey, '8');
});
