// Paging for the Mistake Notebook page (backend analytics.views
// MistakeNotebookView: `{ results, count, page, page_size }`, page_size <= 100).

export type NotebookFilter = 'all' | 'due' | 'new' | 'learning' | 'reviewing' | 'mastered';

/**
 * Query params of one page of a tab. "Due now" is the list's `?due=true`
 * filter: the old `due/` call returned every due entry at once, which for an
 * active student is most of the notebook.
 */
export function notebookListParams(
    filter: NotebookFilter,
    page: number,
    pageSize: number,
): Record<string, string | number> {
    const params: Record<string, string | number> = { page, page_size: pageSize };
    if (filter === 'due') params.due = 'true';
    else if (filter !== 'all') params.review_status = filter;
    return params;
}

/**
 * The page "Load more" asks for while `shown` entries are on screen.
 *
 * A reviewed entry leaves the "Due now" and status views, on screen and on the
 * server, so the server's later rows move up. Counting from what is still shown
 * (the page holds the first rows of that view) never skips any of them; rows
 * already on screen come back at most once more and are de-duplicated by id.
 */
export function nextPageToLoad(shown: number, pageSize: number): number {
    return Math.floor(Math.max(0, shown) / pageSize) + 1;
}
