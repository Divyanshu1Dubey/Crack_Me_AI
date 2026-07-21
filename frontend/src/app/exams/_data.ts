/**
 * exams/_data.ts — Shared exam microsite config.
 *
 * Each exam gets its own theme, color tokens, hero copy, subject list,
 * high-yield topics, and CTAs. The /exams/[slug]/page.tsx dispatcher
 * routes by slug to a per-exam page renderer (see /exams/_renders/*.tsx).
 */
export type ExamTheme = {
  /** Tailwind gradient classes for the hero background. */
  heroGradient: string;
  /** Primary accent (button / link / icon). */
  primary: string;
  /** Soft tinted backdrop class. */
  tint: string;
  /** Tag for analytics + meta. */
  badgeText: string;
};

export type ExamSubject = {
  code: string;
  name: string;
  /** Approximate number of questions on this exam (rough, for marketing copy). */
  weightage: string;
  /** A short, encouraging sentence shown on subject cards. */
  blurb: string;
};

export type ExamHighYield = {
  topic: string;
  reason: string;
  /** Optional 3-letter code tying back to a subject code (for color). */
  code?: string;
};

export type ExamConfig = {
  /** Internal slug; matches /exams/[slug]. */
  slug: 'cms' | 'neet-pg' | 'usmle';
  /** Short display name (e.g. "UPSC CMS"). */
  shortName: string;
  /** Long display name (e.g. "UPSC Combined Medical Services"). */
  fullName: string;
  /** One-sentence positioning statement under the hero. */
  tagline: string;
  /** Long description, ~2 sentences, used on the about section. */
  description: string;
  /** Tags rendered as badges on the hero. */
  tags: string[];
  /** Hero CTA primary label + href. */
  primaryCta: { label: string; href: string };
  /** Hero CTA secondary label + href. */
  secondaryCta: { label: string; href: string };
  /** Theme tokens. */
  theme: ExamTheme;
  /** Exam pattern summary. */
  pattern: {
    type: string;
    totalMarks: string;
    duration: string;
    negativeMarking: string;
  };
  /** Eligibility bullets. */
  eligibility: Array<{ label: string; value: string }>;
  /** Subject list with weightage + blurb. */
  subjects: ExamSubject[];
  /** High-yield topics (used in a "Why CrackCMS" section). */
  highYield: ExamHighYield[];
  /** Recent PYQ year list (shown in the year grid). */
  pyqYears: number[];
  /** Stats row shown in the hero. */
  stats: Array<{ value: string; label: string }>;
};

export const EXAM_CONFIGS: Record<ExamConfig['slug'], ExamConfig> = {
  cms: {
    slug: 'cms',
    shortName: 'UPSC CMS',
    fullName: 'UPSC Combined Medical Services',
    tagline: 'Crack the UPSC CMS exam with 2,000+ PYQs, mock tests & AI tutoring.',
    description:
      'UPSC CMS is the gateway to Central Govt medical officer posts — Railways, CGHS, Ordnance Factories. CrackCMS gives you every PYQ from 2018-2025, full mock papers, and an AI tutor trained on Harrison, Bailey & Love, and Park.',
    tags: ['Govt Job', 'Permanent', 'Class-I Officer', 'UPSC'],
    primaryCta: { label: 'Start Year-wise PYQ', href: '/questions?exam_type=cms' },
    secondaryCta: { label: 'Take Mock Test', href: '/tests' },
    theme: {
      heroGradient: 'from-cyan-600 via-sky-600 to-blue-700',
      primary: 'text-cyan-600 dark:text-cyan-400',
      tint: 'bg-cyan-500/10',
      badgeText: 'UPSC',
    },
    pattern: {
      type: 'Computer-Based Test (CBT) + Personality Test',
      totalMarks: '500 Written + 100 Interview',
      duration: '2 hours per paper',
      negativeMarking: '-1/3rd penalty for wrong answers',
    },
    eligibility: [
      { label: 'Qualification', value: 'Passed final MBBS (written + practical).' },
      { label: 'Internship', value: 'Completed (or completing) at the time of joining.' },
      { label: 'Age Limit', value: 'Under 32 years (relaxations for reserved categories).' },
      { label: 'Nationality', value: 'Citizen of India / specified subjects / refugees.' },
    ],
    subjects: [
      { code: 'MED', name: 'General Medicine', weightage: '96 Qs · 192 marks', blurb: 'Cardiology, Resp, GI, Endo, Neuro, Infectious Disease.' },
      { code: 'PED', name: 'Paediatrics', weightage: '24 Qs · 48 marks', blurb: 'Neonatology, growth, immunization, common paediatric emergencies.' },
      { code: 'SUR', name: 'Surgery', weightage: '40 Qs · 80 marks', blurb: 'General surgery, orthopaedics, anaesthesia, radiology basics.' },
      { code: 'OBG', name: 'Obstetrics & Gynaecology', weightage: '40 Qs · 80 marks', blurb: 'Antenatal care, labour, gynae oncology, contraception.' },
      { code: 'PSM', name: 'Preventive & Social Medicine', weightage: '40 Qs · 80 marks', blurb: 'Epidemiology, biostatistics, NHM, national health programmes.' },
    ],
    highYield: [
      { topic: 'ECG / Cardiology emergencies', reason: 'Asked 3-4 times every paper since 2018.', code: 'MED' },
      { topic: 'Vaccination schedule (NIS)', reason: 'High recall, 1-2 Qs / paper in PSM.', code: 'PSM' },
      { topic: 'Drug of choice tables', reason: 'Pure recall, 8-10 Qs across all subjects.', code: 'MED' },
      { topic: 'Biostatistics numericals', reason: 'Predictable marks — Sensitivity, PPV, NNT.', code: 'PSM' },
      { topic: 'Labour management & PPH', reason: 'OBG favourite, asked in 2018, 2019, 2021, 2023.', code: 'OBG' },
    ],
    pyqYears: [2025, 2024, 2023, 2022, 2021, 2020, 2019, 2018],
    stats: [
      { value: '2,000+', label: 'Verified PYQs' },
      { value: '8 yrs', label: 'Coverage 2018-25' },
      { value: '500', label: 'Max Marks' },
    ],
  },

  'neet-pg': {
    slug: 'neet-pg',
    shortName: 'NEET PG',
    fullName: 'NEET PG (National Eligibility cum Entrance Test — Postgraduate)',
    tagline: 'Crack NEET PG with 1,200+ PYQs, full mocks & AI explanations — designed for PG aspirants.',
    description:
      'NEET PG is the single window for MD / MS / PG Diploma admissions across India. CrackCMS brings you the last 5 years of NEET PG PYQs (2020-2025), 19-subject high-yield maps, and an AI tutor trained on standard PG reference books.',
    tags: ['Postgraduate', 'NBE', 'All India 50% Quota', 'NEET PG'],
    primaryCta: { label: 'Start NEET PG PYQ', href: '/questions?exam_type=neet-pg' },
    secondaryCta: { label: 'Browse NEET PG Subjects', href: '/exams/neet-pg#subjects' },
    theme: {
      heroGradient: 'from-emerald-600 via-teal-600 to-cyan-700',
      primary: 'text-emerald-600 dark:text-emerald-400',
      tint: 'bg-emerald-500/10',
      badgeText: 'NEET PG',
    },
    pattern: {
      type: 'Computer-Based Test (CBT)',
      totalMarks: '800 Marks · 200 MCQs',
      duration: '3 hours 30 minutes',
      negativeMarking: '+4 for Correct, -1 for Incorrect',
    },
    eligibility: [
      { label: 'Qualification', value: 'MBBS degree / Provisional Pass Certificate from NMC-recognized college.' },
      { label: 'Internship', value: '1-year rotatory internship completed by NBEMS cutoff.' },
      { label: 'Age Limit', value: 'No upper age limit.' },
      { label: 'Nationality', value: 'Indian citizens, OCI, and foreign nationals (subject to NBE rules).' },
    ],
    subjects: [
      { code: 'ANA', name: 'Anatomy', weightage: 'Pre/Para-clinical', blurb: 'Embryology, histology, neuroanatomy, surface anatomy.' },
      { code: 'PHY', name: 'Physiology', weightage: 'Pre/Para-clinical', blurb: 'General physiology, systemic physiology, biostatistics.' },
      { code: 'BCH', name: 'Biochemistry', weightage: 'Pre/Para-clinical', blurb: 'Enzymes, metabolism, inborn errors, nutrition.' },
      { code: 'PAT', name: 'Pathology', weightage: 'Para-clinical', blurb: 'General & systemic pathology, hematology, transfusion.' },
      { code: 'PHR', name: 'Pharmacology', weightage: 'Para-clinical', blurb: 'General pharmacology, ANS, CVS, CNS, chemotherapy.' },
      { code: 'MIC', name: 'Microbiology', weightage: 'Para-clinical', blurb: 'Bacteriology, virology, immunology, parasitology.' },
      { code: 'FM', name: 'Forensic Medicine', weightage: 'Para-clinical', blurb: 'Forensic pathology, toxicology, medical law.' },
      { code: 'PSM', name: 'Community Medicine / PSM', weightage: 'Para-clinical', blurb: 'Epidemiology, NHM, biostatistics, nutrition.' },
      { code: 'MED', name: 'General Medicine', weightage: 'Clinical', blurb: 'Cardiology, endo, neuro, GI, infectious, emergency.' },
      { code: 'SUR', name: 'General Surgery', weightage: 'Clinical', blurb: 'General + ortho + anaesthesia + radio basics.' },
      { code: 'OBG', name: 'Obstetrics & Gynaecology', weightage: 'Clinical', blurb: 'Antenatal, labour, gynae, contraception, oncology.' },
      { code: 'PED', name: 'Paediatrics', weightage: 'Clinical', blurb: 'Neonatology, growth, immunization, common illnesses.' },
      { code: 'ORT', name: 'Orthopaedics', weightage: 'Clinical', blurb: 'Fractures, joint disease, spine, sports injury.' },
      { code: 'OPH', name: 'Ophthalmology', weightage: 'Clinical', blurb: 'Refraction, retina, glaucoma, ocular emergencies.' },
      { code: 'ENT', name: 'ENT', weightage: 'Clinical', blurb: 'Ear, nose, throat — common surgical topics.' },
      { code: 'SKD', name: 'Dermatology', weightage: 'Clinical', blurb: 'Skin disorders, STIs, leprosy, fungal infections.' },
      { code: 'PSY', name: 'Psychiatry', weightage: 'Clinical', blurb: 'Mood, anxiety, psychosis, substance use.' },
      { code: 'RAD', name: 'Radiology', weightage: 'Clinical', blurb: 'Imaging modalities, signs, interventional basics.' },
      { code: 'ANE', name: 'Anaesthesia', weightage: 'Clinical', blurb: 'General & regional anaesthesia, critical care, pain.' },
    ],
    highYield: [
      { topic: 'Pharmacology drug of choice', reason: 'Asked 12-15 Qs across papers — pure recall.', code: 'PHR' },
      { topic: 'ECG / Echocardiography', reason: 'Clinical classics — almost every paper.', code: 'MED' },
      { topic: 'Vaccination & NIS schedule', reason: 'PSM + Paeds overlap, 4-5 Qs.', code: 'PSM' },
      { topic: 'Biostatistics / Research methodology', reason: 'High-scoring, predictable pattern.', code: 'PSM' },
      { topic: 'Embryology dates & genes', reason: 'High-yield, exact-match recall.', code: 'ANA' },
    ],
    pyqYears: [2025, 2024, 2023, 2022, 2021, 2020],
    stats: [
      { value: '1,200+', label: 'NEET PG PYQs' },
      { value: '19', label: 'PG Subjects' },
      { value: '800', label: 'Max Marks' },
    ],
  },

  usmle: {
    slug: 'usmle',
    shortName: 'USMLE',
    fullName: 'USMLE (United States Medical Licensing Examination)',
    tagline: 'Step into US clinical practice with a USMLE-focused QBank — coming soon.',
    description:
      'USMLE is the multi-step licensing exam for physicians in the United States. The CrackCMS USMLE microsite is in active development — join the waitlist to get early access to a Step 1 / Step 2 CK QBank built around NBME-style questions and explanations.',
    tags: ['International', 'Licensing', 'Step 1', 'Step 2 CK'],
    primaryCta: { label: 'Join USMLE Waitlist', href: '/contact?subject=usmle-waitlist' },
    secondaryCta: { label: 'Explore Step 1 Topics', href: '/exams/usmle#high-yield' },
    theme: {
      heroGradient: 'from-indigo-600 via-violet-600 to-fuchsia-700',
      primary: 'text-indigo-600 dark:text-indigo-400',
      tint: 'bg-indigo-500/10',
      badgeText: 'USMLE',
    },
    pattern: {
      type: 'Computer-Based Test (CBT)',
      totalMarks: 'Step-based scoring (pass/fail since 2022)',
      duration: 'Step 1: 7 hours · Step 2 CK: 9 hours',
      negativeMarking: 'No negative marking',
    },
    eligibility: [
      { label: 'Qualification', value: 'Enrolled in / graduate of a medical school listed in WDOMS.' },
      { label: 'ECFMG Certification', value: 'Required for IMGs before Step 3.' },
      { label: 'Residency', value: 'Apply via ERAS / NRMP after Step 1 + Step 2 CK.' },
      { label: 'Visa', value: 'J-1 (ECFMG-sponsored) or H-1B for residency.' },
    ],
    subjects: [
      { code: 'ANA', name: 'Anatomy', weightage: 'Foundational', blurb: 'Gross, neuro, embryology — image-rich questions.' },
      { code: 'PHY', name: 'Physiology', weightage: 'Foundational', blurb: 'Cell, systemic, acid-base, neurophysiology.' },
      { code: 'BCH', name: 'Biochemistry & Genetics', weightage: 'Foundational', blurb: 'Metabolism, molecular biology, inborn errors.' },
      { code: 'PAT', name: 'Pathology', weightage: 'Systems-based', blurb: 'General & systems pathology, neoplasia.' },
      { code: 'PHR', name: 'Pharmacology', weightage: 'Systems-based', blurb: 'Pharmacokinetics, dynamics, autonomic, antimicrobial.' },
      { code: 'MIC', name: 'Microbiology / Immunology', weightage: 'Systems-based', blurb: 'Bugs, vaccines, immune disorders.' },
      { code: 'BEH', name: 'Behavioural Science', weightage: 'Step 1 heavy', blurb: 'Ethics, biostatistics, psych, development.' },
      { code: 'MED', name: 'Internal Medicine', weightage: 'Step 2 heavy', blurb: 'Cardio, endo, GI, nephro, pulmo, rheum.' },
      { code: 'SUR', name: 'Surgery', weightage: 'Step 2 heavy', blurb: 'Pre-op, post-op, trauma, common procedures.' },
      { code: 'OBG', name: 'OBGYN', weightage: 'Step 2 heavy', blurb: 'Antenatal, gynae, oncology, contraception.' },
      { code: 'PED', name: 'Paediatrics', weightage: 'Step 2 heavy', blurb: 'Growth, common illness, neonatology.' },
      { code: 'PSY', name: 'Psychiatry', weightage: 'Step 1 + 2', blurb: 'Mood, anxiety, substance use, personality.' },
    ],
    highYield: [
      { topic: 'First Aid-style high-yield lists', reason: 'Pure recall — top-of-mind for Step 1.' },
      { topic: 'NBME-style clinical vignettes', reason: 'Step 2 CK — diagnosing from the stem.' },
      { topic: 'Biostatistics & ethics', reason: 'Predictable 10-15 Qs on every Step.' },
      { topic: 'Drug adverse-effect profiles', reason: 'Asked as "side effect of ___" constantly.' },
    ],
    pyqYears: [],
    stats: [
      { value: 'Beta', label: 'Access' },
      { value: 'Step 1+2', label: 'CK Coverage' },
      { value: '∞', label: 'Free Trial' },
    ],
  },
};

export function getExamConfig(slug: string): ExamConfig | null {
  if (slug === 'upsc-cms' || slug === 'cms') return EXAM_CONFIGS.cms;
  if (slug === 'neet-pg' || slug === 'neetpg') return EXAM_CONFIGS['neet-pg'];
  if (slug === 'usmle') return EXAM_CONFIGS.usmle;
  return null;
}