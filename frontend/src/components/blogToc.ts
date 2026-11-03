/**
 * Pure helper for BlogHeadingAnchors: decide which table-of-contents id each
 * rendered `##` heading should get. Kept free of JSX/DOM so it can be
 * unit-tested with Node.
 */

export interface TocItem { id: string; label: string }

/** Lower-case words only, so "**Mistake 1:** Bubbling" matches "Mistake 1: Bubbling". */
export function normaliseHeading(text: string): string {
    return text
        .toLowerCase()
        .replace(/[`*_]/g, '')
        .replace(/[^\p{L}\p{N}\s-]/gu, ' ')
        .replace(/\s+/g, ' ')
        .trim();
}

/**
 * For each heading (in document order) return the TOC id to assign, or null.
 * Headings are matched to items by text first; if the post has exactly as
 * many headings as TOC items, the rest are paired in order. Headings that
 * already carry an id, and ids already present on the page, are skipped.
 */
export function assignHeadingIds(
    headings: { text: string; id?: string }[],
    items: TocItem[],
    idExists: (id: string) => boolean = () => false,
): (string | null)[] {
    const result: (string | null)[] = headings.map(() => null);
    const taken = new Set<number>();
    const usedIds = new Set<string>();

    headings.forEach((h, i) => {
        if (h.id) taken.add(i);
    });

    for (const item of items) {
        if (idExists(item.id)) {
            usedIds.add(item.id);
            continue;
        }
        const want = normaliseHeading(item.label);
        const idx = headings.findIndex((h, i) => !taken.has(i) && normaliseHeading(h.text) === want);
        if (idx >= 0) {
            result[idx] = item.id;
            taken.add(idx);
            usedIds.add(item.id);
        }
    }

    if (headings.length === items.length) {
        headings.forEach((_, i) => {
            const item = items[i];
            if (taken.has(i) || usedIds.has(item.id) || idExists(item.id)) return;
            result[i] = item.id;
            taken.add(i);
            usedIds.add(item.id);
        });
    }
    return result;
}
