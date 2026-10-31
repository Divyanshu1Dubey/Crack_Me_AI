/**
 * localAuth.ts — dev-only email/password auth for running CrackLabs without
 * Supabase (NEXT_PUBLIC_AUTH_MODE=local). Talks to /api/auth/local/*, which
 * the backend only mounts when DEBUG=True and LOCAL_DEV_AUTH=1.
 *
 * Tokens are SimpleJWT access/refresh tokens kept in localStorage. Never used
 * in production builds (the env flag is unset there and the backend refuses).
 */
import { apiUrl } from './apiBase';

const ACCESS_KEY = 'crack_local_access';
const REFRESH_KEY = 'crack_local_refresh';

export const isLocalAuthMode = (): boolean =>
  (process.env.NEXT_PUBLIC_AUTH_MODE || '').trim().toLowerCase() === 'local';

const storage = (): Storage | null => {
  if (typeof window === 'undefined') return null;
  try {
    return window.localStorage;
  } catch {
    return null;
  }
};

export const getLocalAccessToken = (): string | null => storage()?.getItem(ACCESS_KEY) ?? null;

export const setLocalTokens = (access: string, refresh?: string | null) => {
  const s = storage();
  if (!s) return;
  s.setItem(ACCESS_KEY, access);
  if (refresh) s.setItem(REFRESH_KEY, refresh);
};

export const clearLocalTokens = () => {
  const s = storage();
  if (!s) return;
  s.removeItem(ACCESS_KEY);
  s.removeItem(REFRESH_KEY);
};

const postJson = async (path: string, body: unknown) => {
  const response = await fetch(apiUrl(path), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  let data: Record<string, unknown> = {};
  try {
    data = await response.json();
  } catch {
    data = {};
  }
  if (!response.ok) {
    const fieldErrors = Object.values(data)
      .flat()
      .filter((v) => typeof v === 'string') as string[];
    const message = (data.error as string) || (data.detail as string) || fieldErrors[0] || `Request failed (${response.status})`;
    throw new Error(message);
  }
  return data;
};

export interface LocalAuthResult {
  access: string;
  refresh: string;
  user: Record<string, unknown>;
}

export const localLogin = async (identifier: string, password: string): Promise<LocalAuthResult> => {
  const data = (await postJson('/auth/local/login/', { email: identifier.trim(), password })) as unknown as LocalAuthResult;
  setLocalTokens(data.access, data.refresh);
  return data;
};

export const localRegister = async (form: Record<string, string>): Promise<LocalAuthResult> => {
  const data = (await postJson('/auth/local/register/', {
    email: (form.email || '').trim(),
    username: (form.username || '').trim(),
    password: form.password || '',
    first_name: (form.first_name || '').trim(),
    last_name: (form.last_name || '').trim(),
  })) as unknown as LocalAuthResult;
  setLocalTokens(data.access, data.refresh);
  return data;
};

/** Exchange the stored refresh token for a new access token. */
export const refreshLocalAccessToken = async (): Promise<string | null> => {
  const refresh = storage()?.getItem(REFRESH_KEY);
  if (!refresh) return null;
  try {
    const data = await postJson('/auth/local/refresh/', { refresh });
    const access = data.access as string | undefined;
    if (!access) return null;
    setLocalTokens(access, (data.refresh as string | undefined) || null);
    return access;
  } catch {
    clearLocalTokens();
    return null;
  }
};

/** Load the backend profile for the stored session (refreshing once on 401). */
export const fetchLocalProfile = async (): Promise<Record<string, unknown> | null> => {
  let access = getLocalAccessToken();
  if (!access) return null;
  for (let attempt = 0; attempt < 2; attempt++) {
    const response = await fetch(apiUrl('/auth/profile/'), {
      headers: { Authorization: `Bearer ${access}` },
    });
    if (response.ok) return (await response.json()) as Record<string, unknown>;
    if (response.status !== 401 || attempt > 0) break;
    access = await refreshLocalAccessToken();
    if (!access) break;
  }
  return null;
};
