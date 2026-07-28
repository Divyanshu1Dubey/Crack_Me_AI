/**
 * constants.ts — Per-exam-track metadata + offline fallback subject list
 * for the AI question generator.
 *
 * Centralised so a future preset library or migration to a CMS-managed
 * config can swap one file.
 */
// `ExamTrack` is re-exported via the index barrel; not referenced here.

export interface TrackMeta {
  label: string;
  tagline: string;
  defaultSubject: string;
}

export const TRACK_META: Record<string, TrackMeta> = {
  cms: {
    label: 'UPSC CMS',
    tagline: 'Generate AI-powered MCQs across UPSC CMS subjects',
    defaultSubject: 'General Medicine',
  },
  neet_pg: {
    label: 'NEET PG',
    tagline: 'Image-rich, clinical AI MCQs on 19 PG subjects',
    defaultSubject: 'General Medicine',
  },
  ini_cet: {
    label: 'INI-CET',
    tagline: 'AIIMS / PGIMER style super-specialty practice MCQs',
    defaultSubject: 'General Medicine',
  },
  usmle: {
    label: 'USMLE',
    tagline: 'USMLE-style MCQs grounded in First Aid + UWorld',
    defaultSubject: 'General Medicine',
  },
  fmge: {
    label: 'FMGE',
    tagline: 'NMC-screening style MCQs across MBBS subjects',
    defaultSubject: 'General Medicine',
  },
};

/** Hard-coded fallback when the API is unreachable; keeps the page useful offline. */
export const FALLBACK_SUBJECTS_BY_TRACK: Record<string, string[]> = {
  cms: [
    'General Medicine', 'General Surgery', 'Paediatrics',
    'Obstetrics & Gynaecology', 'Preventive & Social Medicine', 'ENT',
    'Ophthalmology', 'Orthopaedics', 'Dermatology', 'Psychiatry', 'Anaesthesia',
  ],
  neet_pg: [
    'General Medicine', 'General Surgery', 'Paediatrics',
    'Obstetrics & Gynaecology', 'Orthopaedics', 'ENT', 'Ophthalmology',
    'Dermatology', 'Psychiatry', 'Anaesthesia', 'Radiodiagnosis',
  ],
  ini_cet: ['General Medicine', 'General Surgery', 'Paediatrics'],
  usmle:   ['Internal Medicine', 'Surgery', 'Paediatrics', 'OB-GYN', 'Psychiatry'],
  fmge:    ['General Medicine', 'General Surgery', 'Paediatrics', 'OB-GYN'],
};

export const DIFFICULTY_OPTIONS: { value: 'easy' | 'medium' | 'hard'; label: string }[] = [
  { value: 'easy',   label: 'Easy — recall' },
  { value: 'medium', label: 'Medium — applied' },
  { value: 'hard',   label: 'Hard — clinical reasoning' },
];

export const COUNT_OPTIONS = [3, 5, 10, 15, 20];

export const ACCENT_CLASSES: Record<
  'emerald' | 'red' | 'amber' | 'violet' | 'pink',
  string
> = {
  emerald: 'border-emerald-500/30 bg-emerald-500/10 text-emerald-700 dark:text-emerald-300',
  red:     'border-red-500/30 bg-red-500/10 text-red-700 dark:text-red-300',
  amber:   'border-amber-500/30 bg-amber-500/10 text-amber-700 dark:text-amber-300',
  violet:  'border-violet-500/30 bg-violet-500/10 text-violet-700 dark:text-violet-300',
  pink:    'border-pink-500/30 bg-pink-500/10 text-pink-700 dark:text-pink-300',
};
