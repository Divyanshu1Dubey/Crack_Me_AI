/**
 * Pure coupon helpers (no network, no React): unit-tested in tests/unit/coupons.test.ts.
 * The API calls and types live in src/lib/couponsAPI.ts, which re-exports these.
 */

export type DiscountType = 'percent' | 'fixed';

/** "20% off" / "₹100 off". */
export function describeDiscount(type: DiscountType, value: number): string {
    return type === 'percent' ? `${value}% off` : `₹${value} off`;
}

/** Upper case without spaces: what the server compares. */
export function normalizeCouponCode(raw: string): string {
    return (raw || '').replace(/\s+/g, '').toUpperCase();
}

const CODE_RE = /^[A-Z0-9][A-Z0-9-]{2,31}$/;

/** True when a typed code has the server's shape (3-32 letters, digits, hyphens). */
export function looksLikeCouponCode(raw: string): boolean {
    return CODE_RE.test(normalizeCouponCode(raw));
}

/** A code from a `?coupon=` link, if it looks like one. */
export function couponFromSearch(search: string): string {
    const value = new URLSearchParams(search || '').get('coupon') || '';
    const code = normalizeCouponCode(value);
    return CODE_RE.test(code) ? code : '';
}

/** The server's sentence for a refused code (400 {code: coupon_*, error}), else a generic one. */
export function couponErrorMessage(err: unknown): string {
    const response = (err as { response?: { status?: number; data?: { error?: unknown; errors?: unknown } } } | null)?.response;
    if (response?.status === 429) return 'Too many coupon checks. Please wait a while and try again.';
    const message = response?.data?.error;
    if (typeof message === 'string' && message.trim()) return message;
    const fields = response?.data?.errors;
    if (fields && typeof fields === 'object') {
        const first = Object.entries(fields as Record<string, unknown>).find(([, v]) => typeof v === 'string');
        if (first) return `${first[0].replace(/_/g, ' ')}: ${first[1] as string}`;
    }
    return 'The coupon could not be checked. Please try again.';
}

/** A shareable link that opens /subscription with the code filled in. */
export function couponShareLink(origin: string, code: string): string {
    return `${(origin || 'https://cracklabs.app').replace(/\/$/, '')}/subscription?coupon=${encodeURIComponent(code)}`;
}

/** `datetime-local` input value ("2026-12-31T23:59") -> ISO with the browser's offset, '' -> null. */
export function localInputToIso(value: string): string | null {
    if (!value) return null;
    const date = new Date(value);
    return Number.isNaN(date.getTime()) ? null : date.toISOString();
}

/** ISO -> `datetime-local` input value in the browser's time zone ('' for null). */
export function isoToLocalInput(iso: string | null | undefined): string {
    if (!iso) return '';
    const date = new Date(iso);
    if (Number.isNaN(date.getTime())) return '';
    const pad = (n: number) => String(n).padStart(2, '0');
    return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}`;
}
