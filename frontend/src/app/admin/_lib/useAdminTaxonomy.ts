/**
 * Subject / topic loaders for the admin pickers.
 *
 * /questions/subjects/ and /questions/topics/ are paginated (20 rows per
 * page), and there are ~40 subjects and ~1,950 topics, so a single GET left
 * most of both out of every admin dropdown. Subjects are loaded in full
 * (one or two requests). Topics are loaded per subject, on demand, with
 * `?subject=<id>`: loading all ~1,950 up front would cost dozens of requests
 * against the 60-GETs-per-minute limit on /api/questions/
 * (questions/middleware.py RateLimitMiddleware).
 */
import { useCallback, useRef, useState } from 'react';
import { questionsAPI } from '@/lib/api';
import { ADMIN_PAGE_SIZE, fetchAllPages } from './adminHelpers';

export interface AdminSubject {
  id: number;
  name: string;
  [key: string]: any;
}

export interface AdminTopic {
  id: number;
  name: string;
  subject: number;
  [key: string]: any;
}

/** Every subject, following DRF pagination. */
export function fetchAllSubjects(): Promise<AdminSubject[]> {
  return fetchAllPages<AdminSubject>((page) =>
    questionsAPI.getSubjects({ page, page_size: ADMIN_PAGE_SIZE }).then((res) => res.data),
  );
}

/** Every topic of one subject, following DRF pagination. */
export function fetchSubjectTopics(subjectId: string | number): Promise<AdminTopic[]> {
  return fetchAllPages<AdminTopic>((page) =>
    questionsAPI
      .getTopics({ subject: subjectId, page, page_size: ADMIN_PAGE_SIZE })
      .then((res) => res.data),
  );
}

function subjectKey(subjectId: unknown): string {
  const key = String(subjectId ?? '').trim();
  return /^\d+$/.test(key) ? key : '';
}

/** Empty-option text of a topic picker whose topics failed to load. */
export const TOPICS_ERROR_LABEL = 'Could not load topics (reopen to retry)';

/**
 * Per-subject topic cache.
 *
 * - `ensureTopics(subjectId)` loads that subject's topics once (call it from
 *   event handlers / effects, e.g. when a subject is picked, and from the
 *   topic picker's focus / mousedown so a failed load is retried).
 * - `topicsFor(subjectId)` returns the loaded topics, or [] until they arrive.
 * - `topicsLoading(subjectId)` is true while a load is in flight.
 * - `topicsError(subjectId)` is true after a failed load (e.g. a 429 from the
 *   question-bank limiter), until the retry starts. A failure used to look
 *   exactly like a subject without topics.
 * - `topicsPlaceholder(subjectId, idleLabel)` is the picker's empty-option
 *   text: "Loading topics…", TOPICS_ERROR_LABEL, or `idleLabel`.
 */
export function useSubjectTopics() {
  const [topicsBySubject, setTopicsBySubject] = useState<Record<string, AdminTopic[]>>({});
  const [loadingKeys, setLoadingKeys] = useState<Record<string, boolean>>({});
  const [errorKeys, setErrorKeys] = useState<Record<string, boolean>>({});
  const requested = useRef<Set<string>>(new Set());

  const ensureTopics = useCallback((subjectId: unknown) => {
    const key = subjectKey(subjectId);
    if (!key || requested.current.has(key)) return;
    requested.current.add(key);
    setLoadingKeys((prev) => ({ ...prev, [key]: true }));
    setErrorKeys((prev) => (prev[key] ? { ...prev, [key]: false } : prev));
    fetchSubjectTopics(key)
      .then((rows) => setTopicsBySubject((prev) => ({ ...prev, [key]: rows })))
      .catch(() => {
        // Show the failure in the picker and allow a retry the next time
        // this subject is picked or its topic picker is opened.
        requested.current.delete(key);
        setErrorKeys((prev) => ({ ...prev, [key]: true }));
      })
      .finally(() => setLoadingKeys((prev) => ({ ...prev, [key]: false })));
  }, []);

  const topicsFor = useCallback(
    (subjectId: unknown): AdminTopic[] => topicsBySubject[subjectKey(subjectId)] ?? [],
    [topicsBySubject],
  );

  const topicsLoading = useCallback(
    (subjectId: unknown): boolean => Boolean(loadingKeys[subjectKey(subjectId)]),
    [loadingKeys],
  );

  const topicsError = useCallback(
    (subjectId: unknown): boolean => Boolean(errorKeys[subjectKey(subjectId)]),
    [errorKeys],
  );

  const topicsPlaceholder = useCallback(
    (subjectId: unknown, idleLabel: string): string => {
      const key = subjectKey(subjectId);
      if (key && loadingKeys[key]) return 'Loading topics…';
      if (key && errorKeys[key]) return TOPICS_ERROR_LABEL;
      return idleLabel;
    },
    [loadingKeys, errorKeys],
  );

  return { ensureTopics, topicsFor, topicsLoading, topicsError, topicsPlaceholder };
}
