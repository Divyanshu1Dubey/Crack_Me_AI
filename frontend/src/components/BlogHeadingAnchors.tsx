'use client';

import { useEffect } from 'react';
import { assignHeadingIds, type TocItem } from '@/components/blogToc';

/**
 * Gives the rendered post headings the ids the "On this page" links point
 * at. FormattedText (react-markdown) renders `##` headings without ids, so
 * every table-of-contents link was a dead `#anchor`. Runs once after the
 * body renders; headings that already have an id are left alone.
 */
export default function BlogHeadingAnchors({ containerId, items }: { containerId: string; items: TocItem[] }) {
    useEffect(() => {
        const root = document.getElementById(containerId);
        if (!root || items.length === 0) return;
        const headings = Array.from(root.querySelectorAll<HTMLHeadingElement>('h2'));
        const assigned = assignHeadingIds(
            headings.map((h) => ({ text: h.textContent ?? '', id: h.id })),
            items,
            (id) => Boolean(document.getElementById(id)),
        );
        assigned.forEach((id, i) => {
            if (!id) return;
            headings[i].id = id;
            // Clear the sticky public nav when jumping to a heading.
            headings[i].style.scrollMarginTop = '5rem';
        });
    }, [containerId, items]);

    return null;
}
