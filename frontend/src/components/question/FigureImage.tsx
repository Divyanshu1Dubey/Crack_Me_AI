'use client';

/**
 * A question figure that survives a hiccup (2026-11-04). If it fails to load it is retried once
 * after a short pause (right after a deploy the server can still be restoring its files and answer
 * 503 for a few seconds); after that a clear placeholder replaces the browser's broken-image icon.
 * Callers pass the address through `figureSrc` (lib/figureSrc.ts), so a retired storage address is
 * never loaded.
 */
import React, { useEffect, useState } from 'react';
import { ImageOff } from 'lucide-react';
import { figureRetryUrl } from '@/lib/figureSrc';

export const FIGURE_RETRY_DELAY_MS = 1500;

export function FigurePlaceholder({ label, className = '' }: { label?: string; className?: string }) {
    const text = label ? `Figure could not be loaded (${label})` : 'Figure could not be loaded';
    return (
        <span
            role="img"
            aria-label={text}
            className={`missing-image-placeholder inline-flex items-center gap-1.5 dark:text-amber-200 ${className}`}
        >
            <ImageOff className="h-3.5 w-3.5 shrink-0" aria-hidden="true" />
            <span>{text}. Reload the page to try again.</span>
        </span>
    );
}

type FigureImageProps = Omit<React.ImgHTMLAttributes<HTMLImageElement>, 'src'> & {
    src: string;
    /** Named in the placeholder (defaults to the alt text). */
    label?: string;
    placeholderClassName?: string;
};

type Phase = 'first' | 'waiting' | 'retry' | 'failed';

export default function FigureImage({ src, alt, label, placeholderClassName, onError, style, ...rest }: FigureImageProps) {
    const [phase, setPhase] = useState<Phase>('first');
    useEffect(() => {
        setPhase('first');
    }, [src]);
    useEffect(() => {
        if (phase !== 'waiting') return undefined;
        const timer = setTimeout(() => setPhase('retry'), FIGURE_RETRY_DELAY_MS);
        return () => clearTimeout(timer);
    }, [phase]);

    if (!src || phase === 'failed') {
        return (
            <FigurePlaceholder
                label={label ?? (typeof alt === 'string' && alt ? alt : undefined)}
                className={placeholderClassName}
            />
        );
    }
    return (
        <img
            {...rest}
            src={phase === 'retry' ? figureRetryUrl(src) : src}
            alt={alt ?? ''}
            // While the retry waits, hide the broken-image icon.
            style={phase === 'waiting' ? { ...style, visibility: 'hidden' } : style}
            onError={(event) => {
                onError?.(event);
                setPhase((current) => (current === 'first' ? 'waiting' : current === 'retry' ? 'failed' : current));
            }}
        />
    );
}
