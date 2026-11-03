/**
 * deviceId.ts -- this browser's device id, sent as X-Session-ID on every
 * authenticated request (moved unchanged from api.ts so the token-mode
 * profile fetch and logout in lib/localAuth.ts send it too).
 *
 * The backend binds the id to the sign-in session of the access token
 * (accounts/device_limits.py: the Supabase session, or the Django-native
 * AuthSession), so signing in again on this browser keeps its device slot.
 * A request of a new session WITHOUT the header is enrolled as a device of
 * its own, which is how one browser used to end up holding several slots.
 *
 * No imports: safe to load from any module and from unit tests.
 */
export const DEVICE_ID_KEY = 'crack_device_id';
const DEVICE_ID_COOKIE_MAX_AGE = 60 * 60 * 24 * 365;

const newDeviceId = () => 'dev_' + Math.random().toString(36).slice(2) + '_' + Date.now();

const readDeviceIdCookie = (): string | null => {
  try {
    const match = document.cookie.match(new RegExp(`(?:^|; )${DEVICE_ID_KEY}=([^;]*)`));
    return match ? decodeURIComponent(match[1]) : null;
  } catch {
    return null;
  }
};

const writeDeviceIdCookie = (id: string | null) => {
  try {
    document.cookie = id
      ? `${DEVICE_ID_KEY}=${encodeURIComponent(id)}; Path=/; SameSite=Lax; Max-Age=${DEVICE_ID_COOKIE_MAX_AGE}`
      : `${DEVICE_ID_KEY}=; Path=/; SameSite=Lax; Max-Age=0`;
  } catch {
    // Cookies blocked as well.
  }
};

// Storage access can throw (site data blocked, some privacy modes / webviews).
// Then keep the id in a first-party cookie. If that cannot be persisted
// either, send no X-Session-ID at all: the backend then counts this browser
// by its sign-in session (one device per sign-in). A new id per page load
// used to enrol a new device on every visit and use up the 2-device
// allowance within two page loads.
export const getOrCreateSessionId = (): string => {
  if (typeof window === 'undefined') return '';
  try {
    let id = window.localStorage.getItem(DEVICE_ID_KEY);
    if (!id) {
      id = newDeviceId();
      window.localStorage.setItem(DEVICE_ID_KEY, id);
    }
    return id;
  } catch {
    let id = readDeviceIdCookie();
    if (!id) {
      writeDeviceIdCookie(newDeviceId());
      id = readDeviceIdCookie();
    }
    return id || '';
  }
};

/** Forget this browser's device id, so the next sign-in enrols a new device. */
export const resetDeviceId = () => {
  if (typeof window === 'undefined') return;
  writeDeviceIdCookie(null);
  try {
    window.localStorage.removeItem(DEVICE_ID_KEY);
  } catch {
    // Storage unavailable: the cookie was cleared above.
  }
};

/** `{'X-Session-ID': id}` for a request made outside the Axios client (empty when no id can be kept). */
export const deviceIdHeader = (): Record<string, string> => {
  const id = getOrCreateSessionId();
  return id ? { 'X-Session-ID': id } : {};
};
