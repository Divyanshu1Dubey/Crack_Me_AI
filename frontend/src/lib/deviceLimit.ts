/**
 * deviceLimit.ts -- where api.ts sends a device that is over its plan's
 * device cap (backend 401 `{code: 'device_limit_reached'}`, 2 devices free /
 * 4 subscribed; accounts/supabase_rest_auth.py).
 *
 * The over-limit device may stay on Settings (remove a device there) and on
 * Subscription (buy the 4-device plan from this device). Background requests
 * those pages make (Header token pill, announcements) must not bounce it to
 * Settings, or the plan can never be bought from the over-limit device.
 */

export const DEVICE_LIMIT_SETTINGS_URL = '/settings?deviceLimit=1';

const DEVICE_LIMIT_SAFE_PAGES = ['/settings', '/subscription'];

/** True when a device_limit_reached answer on `pathname` should open Settings. */
export const shouldOpenSettingsForDeviceLimit = (pathname: string): boolean =>
  !DEVICE_LIMIT_SAFE_PAGES.some((page) => pathname === page || pathname.startsWith(`${page}/`));
