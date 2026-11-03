'use client';

import { OPEN_CONSENT_EVENT } from '@/components/ConsentBanner';

/** Reopens the cookie banner's preferences panel (see ConsentBanner). */
export default function ManageCookiesButton() {
    return (
        <button
            type="button"
            onClick={() => window.dispatchEvent(new Event(OPEN_CONSENT_EVENT))}
            className="my-3 rounded-xl border border-border bg-card px-4 py-2 text-sm font-bold text-foreground hover:bg-muted"
        >
            Manage cookie preferences
        </button>
    );
}
