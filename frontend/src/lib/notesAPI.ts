/**
 * Topic-notes API (backend: questions/views.py TopicNote views, questions/views_notes.py).
 * Types and pure rules: src/components/notes/notesData.ts.
 *
 * Student routes (signed in): the published list and its facets work whatever the server's
 * TOPIC_NOTES_BUILDER flag says; the published detail (points + sources) answers 404
 * {code: 'feature_disabled'} while it is off, so `loadPublishedNote` falls back to the list row.
 * Admin routes: the library (CRUD), build / sources (builder flag) and rebuild.
 */
import api from './api';
import {
  isFeatureDisabled,
  type BuilderStatus,
  type BuildReport,
  type NoteFacets,
  type PublishedNote,
} from '@/components/notes/notesData';

type Params = Record<string, string | number | boolean>;

export const notesAPI = {
  // Students
  published: (params?: Params) => api.get('/questions/topic-notes/published/', { params }),
  facets: (params?: Params) => api.get<NoteFacets>('/questions/topic-notes/published/facets/', { params }),
  publishedDetail: (id: number) => api.get<PublishedNote>(`/questions/topic-notes/published/${id}/`),
  // Admins
  library: (params?: Params) => api.get('/questions/topic-notes/library/', { params }),
  libraryNote: (id: number) => api.get(`/questions/topic-notes/library/${id}/`),
  update: (id: number, data: Record<string, unknown>) => api.patch(`/questions/topic-notes/library/${id}/`, data),
  remove: (id: number) => api.delete(`/questions/topic-notes/library/${id}/`),
  createManual: (data: Record<string, unknown>) => api.post('/questions/topic-notes/', data),
  /** Builder status: {enabled, builder_version, ai_offline, evidence_state, async_threshold}. */
  builderStatus: () => api.get<BuilderStatus>('/questions/topic-notes/build/'),
  build: (body: Record<string, unknown>) => api.post<BuildReport>('/questions/topic-notes/build/', body),
  /** Rebuild one note from its PYQs (builder on) or the AI generator (builder off). */
  rebuild: (id: number, body: Record<string, unknown> = {}) =>
    api.post(`/questions/topic-notes/library/${id}/generate/`, body),
  sources: (id: number, params?: Params) => api.get(`/questions/topic-notes/library/${id}/sources/`, { params }),
};

export interface LoadedNote {
  note: PublishedNote | null;
  /** True when the note came from the detail route (sections, points and sources). */
  detailed: boolean;
}

/** One published note for the reader: the detail route, else (builder switched off) the list row. */
export async function loadPublishedNote(id: number): Promise<LoadedNote> {
  try {
    const res = await notesAPI.publishedDetail(id);
    return { note: res.data, detailed: true };
  } catch (err) {
    if (!isFeatureDisabled(err)) {
      const status = (err as { response?: { status?: number } })?.response?.status;
      if (status === 404) return { note: null, detailed: false };
      throw err;
    }
  }
  const res = await notesAPI.published({ id });
  const rows = (res.data?.results ?? res.data ?? []) as PublishedNote[];
  return { note: Array.isArray(rows) && rows.length ? rows[0] : null, detailed: false };
}
