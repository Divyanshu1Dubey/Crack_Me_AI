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

/**
 * Per-subject topic cache.
 *
 * - `ensureTopics(subjectId)` loads that subject's topics once (call it from
 *   event handlers / effects, e.g. when a subject is picked).
 * - `topicsFor(subjectId)` returns the loaded topics, or [] until they arrive.
 * - `topicsLoading(subjectId)` is true while a load is in flight.
 */
export function useSubjectTopics() {
  const [topicsBySubject, setTopicsBySubject] = useState<Record<string, AdminTopic[]>>({});
  const [loadingKeys, setLoadingKeys] = useState<Record<string, boolean>>({});
  const requested = useRef<Set<string>>(new Set());

  const ensureTopics = useCallback((subjectId: unknown) => {
    const key = subjectKey(subjectId);
    if (!key || requested.current.has(key)) return;
    requested.current.add(key);
    setLoadingKeys((prev) => ({ ...prev, [key]: true }));
    fetchSubjectTopics(key)
      .then((rows) => setTopicsBySubject((prev) => ({ ...prev, [key]: rows })))
      .catch(() => {
        // Allow a retry the next time this subject is picked.
        requested.current.delete(key);
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

  return { ensureTopics, topicsFor, topicsLoading };
}
