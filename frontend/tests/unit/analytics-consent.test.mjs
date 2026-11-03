// Regression tests for consent gating, the backend relay payload and the
// PostHog loader (PUB-08, AN-10, PUB-28/AN-01).
// Run (from frontend/): node --import ./tests/unit/register-ts-alias.mjs --test "tests/unit/*.test.mjs" "tests/unit/*.test.ts"
import { test, beforeEach } from 'node:test';
import assert from 'node:assert/strict';
import vm from 'node:vm';

// --- minimal browser globals (analytics.ts / consent.ts only touch these) ---
const store = new Map();
globalThis.window = globalThis;
globalThis.localStorage = {
    getItem: (k) => (store.has(k) ? store.get(k) : null),
    setItem: (k, v) => store.set(k, String(v)),
    removeItem: (k) => store.delete(k),
};
globalThis.sessionStorage = globalThis.localStorage;
globalThis.document = { referrer: '', title: 't' };
globalThis.location = { origin: 'https://www.example.test', pathname: '/x', href: 'https://www.example.test/x' };
globalThis.screen = { width: 1, height: 1 };
Object.defineProperty(globalThis, 'navigator', { value: { userAgent: 'node', language: 'en' }, configurable: true });
const bus = new EventTarget();
globalThis.addEventListener = bus.addEventListener.bind(bus);
globalThis.removeEventListener = bus.removeEventListener.bind(bus);
globalThis.dispatchEvent = bus.dispatchEvent.bind(bus);
globalThis.CustomEvent = class CustomEvent extends Event {
    constructor(type, init) {
        super(type);
        this.detail = init?.detail;
    }
};

const { analytics, buildRelayPayload, posthogLoaderScript, RELAYED_EVENTS } = await import('../../src/lib/analytics.ts');
const { consent } = await import('../../src/lib/consent.ts');

let gtagCalls;
let posthogCalls;
beforeEach(() => {
    store.clear();
    gtagCalls = [];
    posthogCalls = [];
    window.gtag = (...args) => gtagCalls.push(args);
    window.posthog = { capture: (...args) => posthogCalls.push(args) };
});

test('no vendor receives events before the visitor decides', () => {
    analytics.ctaClick('hero', 'home');
    assert.equal(gtagCalls.length, 0);
    assert.equal(posthogCalls.length, 0);
});

test('"Reject all" keeps every vendor silent, including the consent_update event itself', () => {
    consent.rejectAll();
    analytics.event('consent_update', { decision: 'reject_all' });
    analytics.pageView('/after-reject');
    assert.equal(gtagCalls.length, 0);
    assert.equal(posthogCalls.length, 0);
});

test('analytics-only consent reaches GA but not PostHog (marketing)', () => {
    consent.update('analytics', true);
    analytics.ctaClick('hero', 'home');
    assert.equal(gtagCalls.length, 1);
    assert.equal(gtagCalls[0][1], 'cta_click');
    assert.equal(posthogCalls.length, 0);
});

test('accept all reaches both GA and PostHog', () => {
    consent.acceptAll();
    analytics.ctaClick('hero', 'home');
    assert.equal(gtagCalls.length, 1);
    assert.equal(posthogCalls.length, 1);
});

test('relay payload nests params under properties and lifts known columns', () => {
    const body = buildRelayPayload(
        'site_search',
        { search_term: 'pericarditis', results_count: 3, page_type: 'blog_post', utm_source: 'google', empty: undefined },
        { visitor_id: 'v1', session_id: 's1', path: '/blog', referrer: '' },
    );
    assert.equal(body.event_name, 'site_search');
    assert.equal(body.visitor_id, 'v1');
    assert.equal(body.path, '/blog');
    assert.equal(body.page_type, 'blog_post');
    assert.equal(body.utm_source, 'google');
    assert.equal(body.referrer, undefined, 'empty context values are dropped');
    assert.deepEqual(body.properties, {
        search_term: 'pericarditis',
        results_count: 3,
        page_type: 'blog_post',
        utm_source: 'google',
    });
    assert.equal(body.search_term, undefined, 'params are not spread at the top level');
});

test('page views are relayed (admin dashboard KPIs depend on them)', () => {
    assert.ok(RELAYED_EVENTS.has('page_view'));
    assert.ok(RELAYED_EVENTS.has('site_search'));
    assert.ok(!RELAYED_EVENTS.has('scroll_depth'));
});

test('PostHog loader is valid JavaScript, queues init and loads array.js', () => {
    const code = posthogLoaderScript('phc_test</script>', { api_host: 'https://us.i.posthog.com' });
    assert.ok(!code.includes('</script>'), 'key cannot close the inline script tag');
    assert.doesNotThrow(() => new vm.Script(code));

    const inserted = [];
    const fakeScriptTag = { parentNode: { insertBefore: (el) => inserted.push(el) } };
    const sandbox = {
        document: {
            createElement: () => ({}),
            getElementsByTagName: () => [fakeScriptTag],
        },
    };
    sandbox.window = sandbox;
    vm.runInNewContext(code, sandbox);
    assert.equal(inserted.length, 1);
    assert.equal(inserted[0].src, 'https://us-assets.i.posthog.com/static/array.js');
    assert.ok(Array.isArray(sandbox.window.posthog._i));
    assert.equal(sandbox.window.posthog._i.length, 1);
    assert.equal(sandbox.window.posthog._i[0][0], 'phc_test</script>');
    sandbox.window.posthog.capture('evt', { a: 1 });
    // (cross-realm array: compare by value)
    assert.equal(JSON.stringify(sandbox.window.posthog.at(-1)), JSON.stringify(['capture', 'evt', { a: 1 }]));
});
