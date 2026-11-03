/**
 * Unit tests for src/lib/googleIdentity.ts (the helper behind
 * components/auth/GoogleSignInButton.tsx) with a stubbed window.google:
 *  - the button exists only in django mode with NEXT_PUBLIC_GOOGLE_CLIENT_ID;
 *  - GIS is initialised once per client id (popup mode, no auto sign-in) and
 *    the button rendered into its container at a width GIS accepts;
 *  - the ID token of the chosen account reaches the latest handler.
 *
 * Run (from frontend/):
 *   node --import ./tests/unit/register-ts-alias.mjs --test tests/unit/google-identity.test.ts
 */
import { test, beforeEach } from 'node:test';
import assert from 'node:assert/strict';
import {
  GSI_CLIENT_SRC,
  googleButtonWidth,
  googleClientId,
  googleSignInConfigured,
  isGsiLoaded,
  renderGoogleButton,
  resetGoogleIdentityForTests,
  type GsiWindow,
} from '../../src/lib/googleIdentity.ts';

const CLIENT_ID = '1234567890-abcdef.apps.googleusercontent.com';

type InitConfig = { client_id: string; callback: (response: { credential?: string }) => void; ux_mode?: string; auto_select?: boolean; context?: string };

function stubGoogle() {
  const calls = { initialize: [] as InitConfig[], renderButton: [] as Array<{ parent: unknown; options: Record<string, unknown> }> };
  const win: GsiWindow = {
    google: {
      accounts: {
        id: {
          initialize: (config) => { calls.initialize.push(config as InitConfig); },
          renderButton: (parent, options) => { calls.renderButton.push({ parent, options: options as Record<string, unknown> }); },
        },
      },
    },
  };
  return { win, calls };
}

/** A container element stand-in with a width and children. */
function container(clientWidth: number) {
  const children: unknown[] = ['old button'];
  return {
    clientWidth,
    get firstChild() { return children[0] ?? null; },
    removeChild: (child: unknown) => { children.splice(children.indexOf(child), 1); return child; },
    children,
  } as unknown as HTMLElement & { children: unknown[] };
}

beforeEach(() => {
  resetGoogleIdentityForTests();
  process.env.NEXT_PUBLIC_AUTH_MODE = 'django';
  process.env.NEXT_PUBLIC_GOOGLE_CLIENT_ID = CLIENT_ID;
});

test('the button is offered only in django mode with a client id', () => {
  assert.equal(GSI_CLIENT_SRC, 'https://accounts.google.com/gsi/client');
  assert.equal(googleClientId(), CLIENT_ID);
  assert.equal(googleSignInConfigured(), true);
  process.env.NEXT_PUBLIC_GOOGLE_CLIENT_ID = '  ';
  assert.equal(googleSignInConfigured(), false);
  process.env.NEXT_PUBLIC_GOOGLE_CLIENT_ID = CLIENT_ID;
  for (const mode of ['local', 'supabase']) {
    process.env.NEXT_PUBLIC_AUTH_MODE = mode;
    assert.equal(googleSignInConfigured(), false, mode);
  }
  // Unset mode follows the Supabase keys (lib/localSession.ts authBuildMode).
  const savedUrl = process.env.NEXT_PUBLIC_SUPABASE_URL;
  const savedKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;
  try {
    process.env.NEXT_PUBLIC_AUTH_MODE = '';
    process.env.NEXT_PUBLIC_SUPABASE_URL = 'https://project.supabase.example';
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY = 'anon-key';
    assert.equal(googleSignInConfigured(), false, 'unset mode with Supabase keys');
    delete process.env.NEXT_PUBLIC_SUPABASE_URL;
    delete process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;
    assert.equal(googleSignInConfigured(), true, 'unset mode without Supabase keys is django');
  } finally {
    if (savedUrl === undefined) delete process.env.NEXT_PUBLIC_SUPABASE_URL;
    else process.env.NEXT_PUBLIC_SUPABASE_URL = savedUrl;
    if (savedKey === undefined) delete process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;
    else process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY = savedKey;
    process.env.NEXT_PUBLIC_AUTH_MODE = 'django';
  }
});

test('nothing renders before GIS has loaded or without a client id', () => {
  const el = container(360);
  assert.equal(isGsiLoaded(undefined), false);
  assert.equal(isGsiLoaded({}), false);
  assert.equal(renderGoogleButton({}, el, { clientId: CLIENT_ID, onCredential: () => {} }), false);
  const { win, calls } = stubGoogle();
  assert.equal(renderGoogleButton(win, el, { clientId: '', onCredential: () => {} }), false);
  assert.equal(calls.initialize.length + calls.renderButton.length, 0);
});

test('GIS is initialised once (popup, no auto sign-in) and the button rendered per mount', () => {
  const { win, calls } = stubGoogle();
  const first = container(372);
  assert.equal(renderGoogleButton(win, first, { clientId: CLIENT_ID, text: 'signin_with', onCredential: () => {} }), true);
  const second = container(1000);
  assert.equal(renderGoogleButton(win, second, { clientId: CLIENT_ID, text: 'signup_with', onCredential: () => {} }), true);

  assert.equal(calls.initialize.length, 1);
  assert.equal(calls.initialize[0].client_id, CLIENT_ID);
  assert.equal(calls.initialize[0].ux_mode, 'popup');
  assert.equal(calls.initialize[0].auto_select, false);
  assert.equal(calls.renderButton.length, 2);
  assert.equal(calls.renderButton[0].parent, first);
  assert.deepEqual(
    { text: calls.renderButton[0].options.text, width: calls.renderButton[0].options.width, theme: calls.renderButton[0].options.theme },
    { text: 'signin_with', width: 372, theme: 'outline' },
  );
  assert.equal(calls.renderButton[1].options.width, 400); // GIS maximum
  assert.equal(calls.renderButton[1].options.text, 'signup_with');
  // The previous button is removed before rendering.
  assert.equal((first as unknown as { children: unknown[] }).children.length, 0);
});

test('the chosen account\'s ID token reaches the handler of the button rendered last', () => {
  const { win, calls } = stubGoogle();
  const received: string[] = [];
  renderGoogleButton(win, container(300), { clientId: CLIENT_ID, onCredential: (c) => received.push(`old:${c}`) });
  renderGoogleButton(win, container(300), { clientId: CLIENT_ID, onCredential: (c) => received.push(`new:${c}`) });
  const callback = calls.initialize[0].callback;
  callback({ credential: 'eyJ.id-token.sig' });
  callback({});
  callback({ credential: '' });
  assert.deepEqual(received, ['new:eyJ.id-token.sig']);
});

test('button width is clamped to what GIS accepts (200-400 px)', () => {
  assert.equal(googleButtonWidth(150), 200);
  assert.equal(googleButtonWidth(320.4), 320);
  assert.equal(googleButtonWidth(900), 400);
  assert.equal(googleButtonWidth(0), 320);
  assert.equal(googleButtonWidth(Number.NaN), 320);
});
