'use client';

import { Link as LinkIcon } from 'lucide-react';
import { useState } from 'react';

/**
 * Small client-only "copy link" button used in the blog share row.
 *
 * Lives in a separate file so the surrounding `BlogPostLayout` (a server
 * component) can render it without having to convert itself to a client
 * component just for the onClick handler.
 */
export function CopyLinkButton({ url, slug }: { url: string; slug?: string }) {
    const [copied, setCopied] = useState(false);
    return (
        <button
            type="button"
            className="blog-share-btn"
            aria-label="Copy link"
            data-blog-copy={slug ?? ''}
            onClick={() => {
                if (typeof navigator !== 'undefined' && navigator.clipboard) {
                    navigator.clipboard.writeText(url).then(() => {
                        setCopied(true);
                        setTimeout(() => setCopied(false), 1800);
                    });
                }
            }}
        >
            <LinkIcon className="h-3.5 w-3.5" />
            {copied ? 'Copied!' : 'Copy link'}
        </button>
    );
}
