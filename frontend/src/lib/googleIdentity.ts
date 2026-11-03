/**
 * googleIdentity.ts -- "Sign in with Google" through Google Identity Services
 * (GIS) for the Django-native sign-in (NEXT_PUBLIC_AUTH_MODE=django).
 *
 * The GIS button hands the page an ID token (`credential`); the backend
 * verifies it (signature, audience = GOOGLE_OAUTH_CLIENT_IDS, issuer, expiry)
 * and matches the Google account by its `sub`, never by email alone
 * (POST /api/auth/google/, accounts/google_identity.py).
 *
 * The script https://accounts.google.com/gsi/client is loaded only by
 * components/auth/GoogleSignInButton.tsx, i.e. only on the sign-in pages (and
 * in Settings once "Connect Google" is clicked), and only when
 * NEXT_PUBLIC_GOOGLE_CLIENT_ID is set. The CSP allows exactly the GIS URLs
 * (frontend/vercel.json).
 *
 * No React / Next imports: unit-tested with a stubbed window.google
 * (tests/unit/google-identity.test.ts).
 */
import { isDjangoAuthBuild } from './localSession';

export const GSI_CLIENT_SRC = 'https://accounts.google.com/gsi/client';

/** The OAuth web client id (inlined at build time); '' when not configured. */
export const googleClientId = (): string => (process.env.NEXT_PUBLIC_GOOGLE_CLIENT_ID || '').trim();

/** True when this build shows the Google button: django mode and a client id. */
export const googleSignInConfigured = (): boolean => isDjangoAuthBuild() && Boolean(googleClientId());

export type GoogleButtonText = 'signin_with' | 'signup_with' | 'continue_with';

interface GsiCredentialResponse {
  credential?: string;
  select_by?: string;
}

interface GsiInitializeConfig {
  client_id: string;
  callback: (response: GsiCredentialResponse) => void;
  ux_mode?: 'popup' | 'redirect';
  auto_select?: boolean;
  cancel_on_tap_outside?: boolean;
  context?: 'signin' | 'signup' | 'use';
}

interface GsiButtonOptions {
  type?: 'standard' | 'icon';
  theme?: 'outline' | 'filled_blue' | 'filled_black';
  size?: 'large' | 'medium' | 'small';
  text?: GoogleButtonText;
  shape?: 'rectangular' | 'pill' | 'circle' | 'square';
  logo_alignment?: 'left' | 'center';
  width?: number;
}

interface GsiIdApi {
  initialize: (config: GsiInitializeConfig) => void;
  renderButton: (parent: HTMLElement, options: GsiButtonOptions) => void;
}

export interface GsiWindow {
  google?: { accounts?: { id?: GsiIdApi } };
}

/** True once the GIS library has loaded in `win`. */
export const isGsiLoaded = (win: GsiWindow | undefined): boolean =>
  Boolean(win?.google?.accounts?.id && typeof win.google.accounts.id.renderButton === 'function');

/** GIS accepts a button width of 200-400 px. */
export const googleButtonWidth = (available: number): number => {
  const width = Number.isFinite(available) && available > 0 ? available : 320;
  return Math.round(Math.min(400, Math.max(200, width)));
};

// GIS warns when initialize() runs more than once per page, so it runs once
// per client id and the callback forwards to the button rendered last.
let initializedClientId: string | null = null;
let credentialHandler: ((credential: string) => void) | null = null;

/** Test hook: forget the one-time initialisation. */
export const resetGoogleIdentityForTests = () => {
  initializedClientId = null;
  credentialHandler = null;
};

/**
 * Render the GIS button into `container`. `onCredential` receives the ID
 * token of the account the visitor picked. Returns false when GIS is not
 * loaded (yet) or no client id is given.
 */
export function renderGoogleButton(
  win: GsiWindow | undefined,
  container: HTMLElement,
  options: { clientId: string; text?: GoogleButtonText; onCredential: (credential: string) => void },
): boolean {
  const gsi = win?.google?.accounts?.id;
  if (!gsi || !options.clientId || !isGsiLoaded(win)) return false;
  credentialHandler = options.onCredential;
  if (initializedClientId !== options.clientId) {
    gsi.initialize({
      client_id: options.clientId,
      callback: (response) => {
        const credential = typeof response?.credential === 'string' ? response.credential : '';
        if (credential) credentialHandler?.(credential);
      },
      // A popup keeps the visitor on this page (the backend gets the token by
      // POST). COOP is same-origin-allow-popups (vercel.json) for it.
      ux_mode: 'popup',
      auto_select: false,
      cancel_on_tap_outside: true,
      context: options.text === 'signup_with' ? 'signup' : 'signin',
    });
    initializedClientId = options.clientId;
  }
  while (container.firstChild) container.removeChild(container.firstChild);
  gsi.renderButton(container, {
    type: 'standard',
    theme: 'outline',
    size: 'large',
    text: options.text ?? 'continue_with',
    shape: 'pill',
    logo_alignment: 'left',
    width: googleButtonWidth(container.clientWidth),
  });
  return true;
}
