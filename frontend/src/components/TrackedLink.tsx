'use client';

import Link from 'next/link';
import type { ComponentProps } from 'react';
import { consent } from '@/lib/consent';

interface TrackedLinkProps extends ComponentProps<typeof Link> {
    eventName?: string;
    eventParams?: Record<string, unknown>;
}

export function TrackedLink({ eventName, eventParams, onClick, children, ...props }: TrackedLinkProps) {
    return (
        <Link
            {...props}
            onClick={(e) => {
                // Only with analytics consent (the gtag stub exists before
                // consent, and queued events would be sent once gtag.js loads).
                if (eventName && typeof window !== 'undefined' && (window as any).gtag && consent.isAllowed('analytics')) {
                    (window as any).gtag('event', eventName, eventParams);
                }
                if (onClick) {
                    onClick(e);
                }
            }}
        >
            {children}
        </Link>
    );
}
