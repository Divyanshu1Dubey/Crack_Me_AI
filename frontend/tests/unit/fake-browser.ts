/**
 * Minimal browser globals for unit tests of the token-mode auth code
 * (lib/localAuth.ts, lib/api.ts): window.localStorage, window.location /
 * history, window events and document.cookie. Not a test file itself
 * (the runner only picks up *.test.ts).
 *
 * Install it BEFORE importing the module under test when that module reads
 * `window` at import time (lib/apiBase.ts does).
 */

export class MemoryStorage {
  private data = new Map<string, string>();

  get length() {
    return this.data.size;
  }

  key(index: number) {
    return [...this.data.keys()][index] ?? null;
  }

  getItem(key: string) {
    return this.data.has(key) ? (this.data.get(key) as string) : null;
  }

  setItem(key: string, value: string) {
    this.data.set(key, String(value));
  }

  removeItem(key: string) {
    this.data.delete(key);
  }

  clear() {
    this.data.clear();
  }
}

export interface FakeBrowser {
  storage: MemoryStorage;
  sessionStorage: MemoryStorage;
  /** Current cookies (name -> value), after Max-Age=0 deletions. */
  cookies: Map<string, string>;
  /** Every raw document.cookie assignment, in order. */
  cookieWrites: string[];
  location: { href: string; pathname: string; search: string; hash: string; hostname: string; protocol: string; origin: string };
  /** URLs passed to history.replaceState. */
  replacedUrls: string[];
  events: string[];
  /** Deliver an event to the window listeners (e.g. a `storage` event from "another tab"). */
  dispatch: (event: Event) => void;
  setUrl: (url: string) => void;
}

export function installFakeBrowser(initialUrl = 'http://localhost:3000/dashboard'): FakeBrowser {
  const storage = new MemoryStorage();
  const sessionStorage = new MemoryStorage();
  const cookies = new Map<string, string>();
  const cookieWrites: string[] = [];
  const replacedUrls: string[] = [];
  const events: string[] = [];
  const listeners = new Map<string, Set<(event: Event) => void>>();

  const location = { href: '', pathname: '', search: '', hash: '', hostname: '', protocol: '', origin: '' };
  const setUrl = (url: string) => {
    const parsed = new URL(url, location.href || 'http://localhost:3000/');
    Object.assign(location, {
      href: parsed.href,
      pathname: parsed.pathname,
      search: parsed.search,
      hash: parsed.hash,
      hostname: parsed.hostname,
      protocol: parsed.protocol,
      origin: parsed.origin,
    });
  };
  setUrl(initialUrl);

  // Assigning location.href (api.ts sends a signed-out browser to /login) only records it.
  const locationProxy = new Proxy(location, {
    set(target, prop, value) {
      if (prop === 'href') {
        setUrl(String(value));
        return true;
      }
      (target as Record<string | symbol, unknown>)[prop] = value;
      return true;
    },
  });

  const dispatch = (event: Event) => {
    events.push(event.type);
    for (const listener of listeners.get(event.type) ?? []) listener(event);
  };

  const fakeWindow = {
    localStorage: storage,
    sessionStorage,
    location: locationProxy,
    history: {
      replaceState: (_state: unknown, _title: string, url?: string | URL | null) => {
        if (url !== undefined && url !== null) {
          replacedUrls.push(String(url));
          setUrl(String(url));
        }
      },
    },
    addEventListener: (type: string, listener: (event: Event) => void) => {
      if (!listeners.has(type)) listeners.set(type, new Set());
      listeners.get(type)?.add(listener);
    },
    removeEventListener: (type: string, listener: (event: Event) => void) => {
      listeners.get(type)?.delete(listener);
    },
    dispatchEvent: (event: Event) => {
      dispatch(event);
      return true;
    },
    setTimeout,
    clearTimeout,
  };

  const fakeDocument = {
    get cookie() {
      return [...cookies.entries()].map(([name, value]) => `${name}=${value}`).join('; ');
    },
    set cookie(raw: string) {
      cookieWrites.push(raw);
      const [pair, ...attributes] = raw.split(';').map((part) => part.trim());
      const eq = pair.indexOf('=');
      const name = pair.slice(0, eq);
      const value = pair.slice(eq + 1);
      const maxAge = attributes.find((a) => a.toLowerCase().startsWith('max-age='));
      if (maxAge && Number(maxAge.split('=')[1]) <= 0) cookies.delete(name);
      else cookies.set(name, value);
    },
  };

  Object.assign(globalThis, { window: fakeWindow, document: fakeDocument, localStorage: storage });

  return { storage, sessionStorage, cookies, cookieWrites, location: locationProxy, replacedUrls, events, dispatch, setUrl };
}

/** A SimpleJWT-shaped token (unsigned) whose payload carries `user_id` and a marker. */
export function fakeJwt(userId: number | string, marker = 'x'): string {
  const encode = (value: unknown) => Buffer.from(JSON.stringify(value)).toString('base64url');
  return `${encode({ alg: 'HS256', typ: 'JWT' })}.${encode({ user_id: userId, jti: marker, session_id: '6f1c2c1e-3d0b-4a58-9c1e-1b2a3c4d5e6f' })}.sig-${marker}`;
}

/** A fetch Response with a JSON body. */
export function jsonResponse(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } });
}
