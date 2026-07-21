'use client';

import Link from 'next/link';
import type { ComponentProps } from 'react';

interface TrackedLinkProps extends ComponentProps<typeof Link> {
    eventName?: string;
    eventParams?: Record<string, unknown>;
}

export function TrackedLink({ eventName, eventParams, onClick, children, ...props }: TrackedLinkProps) {
    return (
        <Link
            {...props}
            onClick={(e) => {
                if (eventName && typeof window !== 'undefined' && (window as any).gtag) {
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
