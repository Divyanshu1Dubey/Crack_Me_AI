/**
 * Student evidence endpoint (backend/evidence/views.py StudentCitationsView):
 * GET /api/evidence/questions/<qid>/citations/ -> the accepted citations of a question (title,
 * edition, chapter, page label, a snippet of at most 240 characters; never pages, paths or hashes).
 * A viewer who may not see the answer gets `{citations: [], locked: true}` (HTTP 200).
 * The display rules are in components/evidence/citationRules.ts (pure, unit-tested).
 */
import api from '@/lib/api';

export interface StudentCitationRaw {
  id: number;
  citation: string;
  source: { title: string; edition: string; year: number | null; kind: string };
  chapter: string;
  page_label: string;
  page_note: string;
  snippet: string;
  stance: string;
  option_letter: string;
  figure_url: string | null;
  verified: boolean;
}

export interface StudentCitationsResponse {
  question_id: number;
  citations: StudentCitationRaw[];
  locked: boolean;
  image_context?: string;
}

export async function fetchStudentCitations(questionId: number): Promise<StudentCitationsResponse> {
  const res = await api.get<StudentCitationsResponse>(`/evidence/questions/${questionId}/citations/`);
  return res.data;
}
