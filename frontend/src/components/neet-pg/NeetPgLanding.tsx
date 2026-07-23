/**
 * NeetPgLanding — premium landing for /neet-pg.
 *
 * Distinct from the shared exam microsite (used by /exams/cms, /exams/neet-pg,
 * /exams/usmle). Renders a hero with cinematic gradient, live stats loaded
 * from /api/questions/ + /api/questions/subjects/, year tiles that route into
 * the dedicated NEET PG player, and a subject grid that uses live counts.
 *
 * Visual language: emerald-teal medical palette with ECG-style line art,
 * image-rich subject cards, and dark-mode support.
 */
'use client';
import Link from 'next/link';
import { useEffect, useMemo, useState } from 'react';
import {
  Activity, ArrowRight, Award, BookOpen, Brain, Calendar,
  ChevronRight, Clock, Filter, FlaskConical, GraduationCap, HeartPulse,
  Image as ImageIcon, Layers, Microscope, Pill, Sparkles, Stethoscope,
  Target, TrendingUp, Zap,
} from 'lucide-react';
import { questionsAPI } from '@/lib/api';
import { Card, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Skeleton } from '@/components/ui/skeleton';
import { cn } from '@/lib/utils';

// ──────────────────────────────────────────────────── types ──

interface SubjectRow {
  id: number;
  name: string;
  code: string;
  question_count: number;
  paper?: number;
}
interface StatsPayload {
  total: number;
  total_solved: number;
  by_year: { year: number; count: number; solved: number }[];
  by_subject?: { id: number; name: string; count: number; solved: number }[];
}

// ──────────────────────────────────────────── subject metadata ──

const SUBJECT_VISUAL: Record<string, { icon: any; gradient: string; ring: string; tone: string; blurb: string }> = {
  MED: { icon: HeartPulse, gradient: 'from-rose-500 to-red-600', ring: 'ring-rose-300', tone: 'bg-rose-50 dark:bg-rose-950/40 text-rose-700 dark:text-rose-300', blurb: 'Cardiology, endocrinology, neurology, GI, infectious.' },
  SUR: { icon: Stethoscope, gradient: 'from-blue-500 to-indigo-600', ring: 'ring-blue-300', tone: 'bg-blue-50 dark:bg-blue-950/40 text-blue-700 dark:text-blue-300', blurb: 'General surgery, orthopaedics, anaesthesia basics.' },
  OBG: { icon: HeartPulse, gradient: 'from-pink-500 to-fuchsia-600', ring: 'ring-pink-300', tone: 'bg-pink-50 dark:bg-pink-950/40 text-pink-700 dark:text-pink-300', blurb: 'Antenatal, labour, gynae oncology, contraception.' },
  PED: { icon: Activity, gradient: 'from-amber-500 to-orange-600', ring: 'ring-amber-300', tone: 'bg-amber-50 dark:bg-amber-950/40 text-amber-700 dark:text-amber-300', blurb: 'Neonatology, growth, immunization, emergencies.' },
  PSM: { icon: Layers, gradient: 'from-emerald-500 to-teal-600', ring: 'ring-emerald-300', tone: 'bg-emerald-50 dark:bg-emerald-950/40 text-emerald-700 dark:text-emerald-300', blurb: 'Epidemiology, biostatistics, NHM, nutrition.' },
  ANA: { icon: Microscope, gradient: 'from-fuchsia-500 to-purple-600', ring: 'ring-purple-300', tone: 'bg-fuchsia-50 dark:bg-fuchsia-950/40 text-fuchsia-700 dark:text-fuchsia-300', blurb: 'Embryology, histology, neuroanatomy, gross.' },
  PHY: { icon: Activity, gradient: 'from-sky-500 to-cyan-600', ring: 'ring-sky-300', tone: 'bg-sky-50 dark:bg-sky-950/40 text-sky-700 dark:text-sky-300', blurb: 'General, systemic, biostatistics, neurophysiology.' },
  BCH: { icon: FlaskConical, gradient: 'from-lime-500 to-green-600', ring: 'ring-lime-300', tone: 'bg-lime-50 dark:bg-lime-950/40 text-lime-700 dark:text-lime-300', blurb: 'Enzymes, metabolism, inborn errors, nutrition.' },
  PTH: { icon: Microscope, gradient: 'from-yellow-500 to-amber-600', ring: 'ring-yellow-300', tone: 'bg-yellow-50 dark:bg-yellow-950/40 text-yellow-700 dark:text-yellow-300', blurb: 'General + systemic pathology, haematology.' },
  PHR: { icon: Pill, gradient: 'from-violet-500 to-purple-600', ring: 'ring-violet-300', tone: 'bg-violet-50 dark:bg-violet-950/40 text-violet-700 dark:text-violet-300', blurb: 'ANS, CVS, CNS, chemotherapy, antimicrobials.' },
  MIC: { icon: Microscope, gradient: 'from-teal-500 to-emerald-600', ring: 'ring-teal-300', tone: 'bg-teal-50 dark:bg-teal-950/40 text-teal-700 dark:text-teal-300', blurb: 'Bacteriology, virology, immunology, parasitology.' },
  FMT: { icon: BookOpen, gradient: 'from-slate-500 to-gray-600', ring: 'ring-slate-300', tone: 'bg-slate-50 dark:bg-slate-950/40 text-slate-700 dark:text-slate-300', blurb: 'Forensic pathology, toxicology, medical law.' },
  DER: { icon: Sparkles, gradient: 'from-pink-400 to-rose-500', ring: 'ring-pink-300', tone: 'bg-pink-50 dark:bg-pink-950/40 text-pink-700 dark:text-pink-300', blurb: 'Skin disorders, STIs, leprosy, fungal.' },
  ENT: { icon: Stethoscope, gradient: 'from-orange-500 to-red-500', ring: 'ring-orange-300', tone: 'bg-orange-50 dark:bg-orange-950/40 text-orange-700 dark:text-orange-300', blurb: 'Ear, nose, throat — common surgical topics.' },
  OPH: { icon: Target, gradient: 'from-cyan-500 to-blue-600', ring: 'ring-cyan-300', tone: 'bg-cyan-50 dark:bg-cyan-950/40 text-cyan-700 dark:text-cyan-300', blurb: 'Refraction, retina, glaucoma, emergencies.' },
  ORT: { icon: Activity, gradient: 'from-stone-500 to-zinc-600', ring: 'ring-stone-300', tone: 'bg-stone-50 dark:bg-stone-950/40 text-stone-700 dark:text-stone-300', blurb: 'Fractures, joint disease, spine, sports.' },
  PSY: { icon: Brain, gradient: 'from-indigo-500 to-violet-600', ring: 'ring-indigo-300', tone: 'bg-indigo-50 dark:bg-indigo-950/40 text-indigo-700 dark:text-indigo-300', blurb: 'Mood, anxiety, psychosis, substance use.' },
  RAD: { icon: ImageIcon, gradient: 'from-blue-600 to-indigo-700', ring: 'ring-blue-300', tone: 'bg-blue-50 dark:bg-blue-950/40 text-blue-700 dark:text-blue-300', blurb: 'Imaging modalities, signs, interventional.' },
  ANS: { icon: Pill, gradient: 'from-violet-500 to-fuchsia-600', ring: 'ring-violet-300', tone: 'bg-violet-50 dark:bg-violet-950/40 text-violet-700 dark:text-violet-300', blurb: 'General + regional anaesthesia, critical care.' },
};

const DEFAULT_VISUAL = {
  icon: BookOpen, gradient: 'from-emerald-500 to-teal-600', ring: 'ring-emerald-300',
  tone: 'bg-emerald-50 dark:bg-emerald-950/40 text-emerald-700 dark:text-emerald-300',
  blurb: '',
};

const HIGH_YIELD = [
  { topic: 'Pharmacology — drug of choice tables', count: '12-15 Qs / paper', tag: 'PHR', reason: 'Pure recall, asked across every paper.' },
  { topic: 'ECG & echocardiography', count: '5-7 Qs / paper', tag: 'MED', reason: 'Clinical classics — image-based since 2019.' },
  { topic: 'Vaccination / NIS schedule', count: '4-5 Qs / paper', tag: 'PED', reason: 'High recall, PSM-Paeds overlap.' },
  { topic: 'Biostatistics / research methodology', count: '3-5 Qs / paper', tag: 'PSM', reason: 'Predictable pattern, easy marks.' },
  { topic: 'Embryology dates & genes', count: '4-6 Qs / paper', tag: 'ANA', reason: 'Exact-match recall, high-yield.' },
  { topic: 'Histopathology + Radiology images', count: '10+ Qs / paper', tag: 'RAD', reason: 'New image-based Qs by NBE since 2019.' },
];

const HOW_IT_WORKS = [
  {
    n: '01',
    icon: BookOpen,
    title: 'Open a NEET PG paper',
    body: 'Pick a year from 2018-2025. Every question is loaded with subject, topic, image, and correct answer.',
  },
  {
    n: '02',
    icon: Brain,
    title: 'Practise in fullscreen',
    body: 'Image-first player with palette, keyboard shortcuts, AI tutor panel, and a Related PYQs sidebar.',
  },
  {
    n: '03',
    icon: TrendingUp,
    title: 'Track + revise',
    body: 'Year-wise + subject-wise analytics, spaced-repetition flashcards, and AIR-rank prediction after every mock.',
  },
];

const FAQS = [
  { q: 'What is NEET PG?', a: 'NEET PG is the single-window entrance exam for MD / MS / PG Diploma admissions across India, conducted by the National Board of Examinations (NBE).' },
  { q: 'How many questions in NEET PG?', a: '200 MCQs, 800 marks, 3 hours 30 minutes. Negative marking: -1 for wrong, +4 for correct.' },
  { q: 'How many NEET PG PYQs are on CrackCMS?', a: '2,300+ verified PYQs across 19 PG subjects, image-rich recalls from 2018-2025.' },
  { q: 'Does it support image-based questions?', a: 'Yes — image-heavy recalls (radiology, histopathology, dermatology, ECG) are pinned to the question and shown in a zoomable viewer.' },
  { q: 'Does the AI tutor work on NEET PG?', a: 'Yes. The AI tutor is grounded on Harrison, Robbins, Bailey & Love, Ghai, Park, and KD Tripathi. It pulls the closest matching recall chunks for every question.' },
];

// ──────────────────────────────────────────── page component ──

export default function NeetPgLanding() {
  const [stats, setStats] = useState<StatsPayload | null>(null);
  const [subjects, setSubjects] = useState<SubjectRow[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const [statsRes, subjectsRes] = await Promise.all([
          questionsAPI.getStats({ exam_source: 'NEET PG' }),
          questionsAPI.getSubjects(),
        ]);
        if (cancelled) return;
        const rawStats = statsRes.data as any;
        const subjRows = ((subjectsRes.data as any)?.results || (subjectsRes.data as any) || []) as SubjectRow[];
        // Combine live stats with full subject list (subjects endpoint gives
        // every Subject row, while stats only lists subjects that actually
        // have NEET PG questions). Show all 19 so the grid feels complete.
        setStats({
          total: rawStats.total ?? 0,
          total_solved: rawStats.total_solved ?? 0,
          by_year: rawStats.by_year ?? [],
          by_subject: rawStats.by_subject ?? [],
        });
        setSubjects(subjRows);
      } catch {
        // graceful degradation — empty state, no crash
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, []);

  const totalQs = stats?.total ?? 0;
  const totalYears = stats?.by_year.length ?? 0;
  const totalSubjects = subjects.length || 19;

  // Featured year (most recent with content)
  const featuredYear = useMemo(() => {
    if (!stats?.by_year?.length) return 2025;
    const top = [...stats.by_year].sort((a, b) => b.year - a.year)[0];
    return top?.year ?? 2025;
  }, [stats]);

  return (
    <main className="min-h-screen bg-background text-foreground">
      {/* ════════════════ HERO ════════════════ */}
      <section className="relative overflow-hidden bg-gradient-to-br from-emerald-600 via-teal-600 to-cyan-800 text-white">
        {/* layered overlays */}
        <div className="absolute inset-0 pointer-events-none opacity-30"
             style={{
               backgroundImage:
                 'radial-gradient(circle at 15% 20%, rgba(255,255,255,0.30), transparent 55%),' +
                 'radial-gradient(circle at 80% 70%, rgba(255,255,255,0.22), transparent 55%),' +
                 'radial-gradient(circle at 50% 100%, rgba(16,185,129,0.35), transparent 60%)',
             }} />
        {/* ECG-line art */}
        <svg className="absolute inset-x-0 bottom-0 w-full h-32 opacity-25 pointer-events-none" viewBox="0 0 1200 120" preserveAspectRatio="none" aria-hidden>
          <path d="M0,60 L150,60 L170,30 L190,90 L210,55 L230,70 L260,60 L450,60 L470,25 L490,95 L510,55 L530,72 L560,60 L760,60 L780,35 L800,90 L820,55 L840,72 L870,60 L1100,60 L1120,30 L1140,90 L1160,60 L1200,60"
                fill="none" stroke="rgba(255,255,255,0.85)" strokeWidth="2" />
        </svg>

        <div className="relative max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-16 lg:py-24">
          {/* Tag row */}
          <div className="flex flex-wrap items-center gap-2 mb-6">
            <Badge className="bg-white/15 text-white border border-white/20 backdrop-blur-sm hover:bg-white/25 px-3 py-1">
              🩺 NBE · NEET PG
            </Badge>
            <Badge className="bg-emerald-500/30 text-white border border-emerald-300/40 backdrop-blur-sm hover:bg-emerald-500/40 px-3 py-1">
              2026 Batch
            </Badge>
            <Badge className="bg-cyan-500/30 text-white border border-cyan-300/40 backdrop-blur-sm hover:bg-cyan-500/40 px-3 py-1">
              MD · MS · PG Diploma
            </Badge>
          </div>

          <h1 className="text-4xl md:text-5xl lg:text-7xl font-extrabold tracking-tight leading-[1.05] max-w-4xl">
            NEET PG
            <span className="block text-2xl md:text-3xl lg:text-4xl font-semibold mt-3 text-white/90">
              Crack it with 2,300+ PYQs, AI Tutor & Image-Rich Recalls
            </span>
          </h1>

          <p className="mt-6 text-base md:text-xl max-w-2xl text-white/90 leading-relaxed">
            India&apos;s most dedicated NEET PG platform — 19 PG subjects, image-heavy clinical vignettes, AI tutor grounded on Harrison &amp; Robbins, and full mock tests with AIR prediction.
          </p>

          <div className="mt-8 flex flex-wrap gap-3">
            <Button asChild size="lg" className="bg-white text-emerald-800 hover:bg-white/95 font-bold shadow-2xl shadow-emerald-900/30">
              <Link href={`/questions/neet-pg/practice?year=${featuredYear}`}>
                <Zap className="w-4 h-4 mr-2 fill-emerald-700" />
                Start NEET PG {featuredYear}
              </Link>
            </Button>
            <Button asChild size="lg" variant="outline"
                    className="bg-transparent border-white/40 text-white hover:bg-white/10 hover:border-white/60 backdrop-blur-sm font-semibold">
              <Link href="/questions?exam=neet-pg">
                <Filter className="w-4 h-4 mr-2" />
                Open QBank
              </Link>
            </Button>
            <Button asChild size="lg" variant="outline"
                    className="bg-emerald-500/20 border-white/30 text-white hover:bg-emerald-500/30 backdrop-blur-sm font-semibold">
              <Link href="#subjects">
                <Layers className="w-4 h-4 mr-2" />
                Browse 19 Subjects
              </Link>
            </Button>
          </div>

          {/* Live stats row */}
          <div className="mt-10 grid grid-cols-2 sm:grid-cols-4 gap-3 max-w-4xl">
            <StatTile value={loading ? '—' : `${totalQs.toLocaleString()}+`} label="NEET PG PYQs" sub="live from API" />
            <StatTile value={loading ? '—' : `${totalYears}`} label="Years covered" sub="2018 – 2025" />
            <StatTile value={loading ? '—' : `${totalSubjects}`} label="PG Subjects" sub="clinical + para + pre" />
            <StatTile value="800" label="Max Marks" sub="200 Qs · +4 / -1" />
          </div>
        </div>
      </section>

      {/* ════════════════ PATTERN STRIP ════════════════ */}
      <section className="border-y border-border/60 bg-card/60 backdrop-blur-sm">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6 grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-4">
          <PatternStat icon={Target} label="Mode" value="CBT" />
          <PatternStat icon={BookOpen} label="Questions" value="200 MCQs" />
          <PatternStat icon={Clock} label="Time" value="3h 30m" />
          <PatternStat icon={Award} label="Marks" value="+4 / −1" />
          <PatternStat icon={GraduationCap} label="Total Marks" value="800" />
          <PatternStat icon={Sparkles} label="Syllabus" value="NBE 2026" />
        </div>
      </section>

      {/* ════════════════ YEAR GRID ════════════════ */}
      <section id="years" className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-12 lg:py-16">
        <div className="flex items-end justify-between flex-wrap gap-3 mb-6">
          <div>
            <h2 className="text-2xl md:text-4xl font-bold flex items-center gap-2">
              <Calendar className="w-7 h-7 text-emerald-600" /> Year-wise PYQ Practice
            </h2>
            <p className="text-sm md:text-base text-muted-foreground mt-2 max-w-2xl">
              Click a year to launch the full NEET PG paper in our image-first player. Image-based recalls, AI tutor, and progress tracking included.
            </p>
          </div>
          <Badge variant="secondary" className="text-xs">
            {loading ? '—' : totalYears} years of PYQs available
          </Badge>
        </div>

        {loading ? (
          <div className="grid grid-cols-3 sm:grid-cols-4 md:grid-cols-6 lg:grid-cols-8 gap-3">
            {Array.from({ length: 8 }).map((_, i) => (
              <Skeleton key={i} className="aspect-square rounded-2xl" />
            ))}
          </div>
        ) : (
          <div className="grid grid-cols-3 sm:grid-cols-4 md:grid-cols-6 lg:grid-cols-8 gap-3">
            {stats?.by_year.map((y) => (
              <Link key={y.year} href={`/questions/neet-pg/practice?year=${y.year}`} className="group">
                <div className="aspect-square rounded-2xl border border-emerald-200/60 dark:border-emerald-800/40 bg-gradient-to-br from-emerald-50/60 via-white to-teal-50/60 dark:from-emerald-950/40 dark:via-slate-900 dark:to-teal-950/30 hover:border-emerald-400 hover:shadow-lg hover:shadow-emerald-500/10 transition-all flex flex-col items-center justify-center text-center p-2 group-hover:scale-[1.03]">
                  <div className="text-2xl md:text-3xl font-extrabold text-emerald-800 dark:text-emerald-300 group-hover:text-emerald-600">
                    {y.year}
                  </div>
                  <div className="text-[10px] uppercase tracking-wider mt-0.5 text-emerald-600/80 dark:text-emerald-400/80">
                    NEET PG
                  </div>
                  <div className="mt-1 text-[10px] font-semibold text-muted-foreground">
                    {y.count.toLocaleString()} Qs
                  </div>
                  <div className="w-full bg-emerald-100/60 dark:bg-emerald-900/40 h-1 rounded-full overflow-hidden mt-1.5">
                    <div
                      className="h-full bg-emerald-500 transition-all"
                      style={{ width: `${Math.min(100, Math.round((y.solved / (y.count || 1)) * 100))}%` }}
                    />
                  </div>
                </div>
              </Link>
            ))}
          </div>
        )}
      </section>

      {/* ════════════════ SUBJECT GRID ════════════════ */}
      <section id="subjects" className="bg-gradient-to-br from-emerald-50/40 via-background to-teal-50/40 border-y border-border/60">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-12 lg:py-16">
          <div className="flex items-end justify-between flex-wrap gap-3 mb-6">
            <div>
              <h2 className="text-2xl md:text-4xl font-bold flex items-center gap-2">
                <Layers className="w-7 h-7 text-emerald-600" />
                19 PG Subjects · Tap to Practise
              </h2>
              <p className="text-sm md:text-base text-muted-foreground mt-2 max-w-2xl">
                Every NEET PG subject from Anatomy to Anaesthesia — image-heavy recalls, AI explanations, year-wise PYQs.
              </p>
            </div>
            <Button asChild variant="outline" size="sm" className="border-emerald-300 text-emerald-700 hover:bg-emerald-50">
              <Link href="/questions?exam=neet-pg">
                Open QBank <ChevronRight className="w-4 h-4 ml-1" />
              </Link>
            </Button>
          </div>

          {loading ? (
            <div className="grid sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
              {Array.from({ length: 12 }).map((_, i) => (
                <Skeleton key={i} className="h-44 rounded-2xl" />
              ))}
            </div>
          ) : (
            <div className="grid sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
              {subjects.map((s) => {
                const v = SUBJECT_VISUAL[s.code] ?? DEFAULT_VISUAL;
                const Icon = v.icon;
                const count = s.question_count ?? 0;
                return (
                  <Link key={s.id} href={`/questions/neet-pg/practice?subject=${encodeURIComponent(s.name)}`}
                        className="group">
                    <Card className={cn(
                      'h-full border-border/60 bg-card/90 hover:border-emerald-400/60 transition-all group-hover:shadow-xl group-hover:-translate-y-0.5 overflow-hidden',
                      'dark:bg-slate-900/70 dark:border-slate-800'
                    )}>
                      <div className={cn('h-1.5 w-full bg-gradient-to-r', v.gradient)} />
                      <CardContent className="p-5 space-y-3">
                        <div className="flex items-start justify-between">
                          <div className={cn(
                            'w-11 h-11 rounded-xl flex items-center justify-center bg-gradient-to-br shadow-md ring-2',
                            v.gradient, v.ring,
                          )}>
                            <Icon className="w-5 h-5 text-white" />
                          </div>
                          <Badge variant="outline" className="font-mono text-[10px]">
                            {s.code}
                          </Badge>
                        </div>
                        <div>
                          <h3 className="font-bold text-base group-hover:text-emerald-600 dark:group-hover:text-emerald-400 transition-colors">
                            {s.name}
                          </h3>
                          <p className="text-xs text-muted-foreground mt-1 leading-relaxed line-clamp-2">
                            {v.blurb}
                          </p>
                        </div>
                        <div className="flex items-end justify-between pt-2 border-t border-border/40">
                          <div>
                            <div className="text-2xl font-extrabold text-emerald-700 dark:text-emerald-400">
                              {count.toLocaleString()}
                            </div>
                            <div className="text-[10px] uppercase tracking-wider text-muted-foreground mt-0.5">
                              PYQs available
                            </div>
                          </div>
                          <ArrowRight className="w-4 h-4 text-emerald-600 opacity-0 group-hover:opacity-100 transition-opacity" />
                        </div>
                      </CardContent>
                    </Card>
                  </Link>
                );
              })}
            </div>
          )}
        </div>
      </section>

      {/* ════════════════ HIGH-YIELD ════════════════ */}
      <section id="high-yield" className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-12 lg:py-16">
        <div className="flex items-center gap-3 mb-6">
          <Sparkles className="w-7 h-7 text-emerald-600" />
          <h2 className="text-2xl md:text-4xl font-bold">High-yield topics that show up every year</h2>
        </div>
        <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-4">
          {HIGH_YIELD.map((h) => {
            const v = SUBJECT_VISUAL[h.tag] ?? DEFAULT_VISUAL;
            const Icon = v.icon;
            return (
              <Card key={h.topic} className="border-border/60 bg-card/90 dark:bg-slate-900/60">
                <CardContent className="p-5 space-y-3">
                  <div className="flex items-center gap-3">
                    <div className={cn(
                      'w-10 h-10 rounded-xl flex items-center justify-center bg-gradient-to-br shadow-sm',
                      v.gradient,
                    )}>
                      <Icon className="w-5 h-5 text-white" />
                    </div>
                    <Badge variant="outline" className="font-mono text-[10px]">{h.tag}</Badge>
                  </div>
                  <h3 className="font-semibold text-foreground">{h.topic}</h3>
                  <p className="text-xs text-muted-foreground leading-relaxed">{h.reason}</p>
                  <div className="text-[11px] font-bold text-emerald-600 dark:text-emerald-400 uppercase tracking-wider">
                    {h.count}
                  </div>
                </CardContent>
              </Card>
            );
          })}
        </div>
      </section>

      {/* ════════════════ HOW IT WORKS ════════════════ */}
      <section className="bg-emerald-50/40 dark:bg-emerald-950/20 border-y border-border/60">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-12 lg:py-16">
          <h2 className="text-2xl md:text-4xl font-bold flex items-center gap-2 mb-8">
            <GraduationCap className="w-7 h-7 text-emerald-600" />
            How CrackCMS helps you crack NEET PG
          </h2>
          <div className="grid md:grid-cols-3 gap-5">
            {HOW_IT_WORKS.map((step) => {
              const Icon = step.icon;
              return (
                <Card key={step.n} className="border-emerald-200/60 dark:border-emerald-900/40 bg-card/95 dark:bg-slate-900/70">
                  <CardContent className="p-6 space-y-4">
                    <div className="flex items-center justify-between">
                      <div className="text-5xl font-extrabold bg-gradient-to-br from-emerald-500 to-teal-700 bg-clip-text text-transparent">
                        {step.n}
                      </div>
                      <div className="w-12 h-12 rounded-xl bg-emerald-100 dark:bg-emerald-950/60 flex items-center justify-center">
                        <Icon className="w-6 h-6 text-emerald-700 dark:text-emerald-400" />
                      </div>
                    </div>
                    <h3 className="font-bold text-lg">{step.title}</h3>
                    <p className="text-sm text-muted-foreground leading-relaxed">{step.body}</p>
                  </CardContent>
                </Card>
              );
            })}
          </div>
        </div>
      </section>

      {/* ════════════════ FAQ ════════════════ */}
      <section className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 py-12 lg:py-16">
        <h2 className="text-2xl md:text-4xl font-bold flex items-center gap-2 mb-6">
          <Brain className="w-7 h-7 text-emerald-600" />
          NEET PG FAQs
        </h2>
        <div className="space-y-3">
          {FAQS.map((f) => (
            <details key={f.q} className="group rounded-2xl border border-border/60 bg-card/90 dark:bg-slate-900/60 overflow-hidden">
              <summary className="cursor-pointer list-none p-5 flex items-start justify-between gap-4 hover:bg-emerald-50/30 dark:hover:bg-emerald-950/20">
                <span className="font-semibold text-foreground">{f.q}</span>
                <ChevronRight className="w-4 h-4 text-muted-foreground group-open:rotate-90 transition-transform shrink-0" />
              </summary>
              <div className="px-5 pb-5 text-sm text-muted-foreground leading-relaxed">
                {f.a}
              </div>
            </details>
          ))}
        </div>
      </section>

      {/* ════════════════ CTA STRIP ════════════════ */}
      <section className="bg-gradient-to-br from-emerald-700 via-teal-700 to-cyan-800 text-white">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-12 lg:py-16 text-center">
          <Award className="w-12 h-12 mx-auto mb-4 text-emerald-200" />
          <h2 className="text-3xl md:text-5xl font-extrabold max-w-3xl mx-auto">
            Ready to crack NEET PG {featuredYear + 1}?
          </h2>
          <p className="mt-3 text-emerald-100/90 max-w-xl mx-auto">
            Start practising the {featuredYear} paper today. Image-rich player, AI tutor, year-wise analytics.
          </p>
          <div className="mt-7 flex flex-wrap gap-3 justify-center">
            <Button asChild size="lg" className="bg-white text-emerald-800 hover:bg-white/95 font-bold shadow-xl">
              <Link href={`/questions/neet-pg/practice?year=${featuredYear}`}>
                <Zap className="w-4 h-4 mr-2 fill-emerald-700" />
                Start {featuredYear} Paper
              </Link>
            </Button>
            <Button asChild size="lg" variant="outline" className="bg-transparent border-white/40 text-white hover:bg-white/10 font-semibold">
              <Link href="/ai-tutor">
                <Sparkles className="w-4 h-4 mr-2" />
                Talk to AI Tutor
              </Link>
            </Button>
          </div>
        </div>
      </section>

      {/* ════════════════ FOOTER ════════════════ */}
      <footer className="border-t border-border/40 bg-muted/30">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6 flex flex-wrap items-center justify-between gap-3 text-xs text-muted-foreground">
          <span>© {new Date().getFullYear()} CrackCMS · NEET PG microsite</span>
          <span className="flex items-center gap-3">
            <Link href="/exams/cms" className="hover:text-primary">UPSC CMS</Link>
            <span>·</span>
            <Link href="/neet-pg" className="hover:text-primary font-semibold">NEET PG</Link>
            <span>·</span>
            <Link href="/exams/usmle" className="hover:text-primary">USMLE</Link>
            <span>·</span>
            <Link href="/inicet" className="hover:text-primary">INI-CET</Link>
          </span>
        </div>
      </footer>
    </main>
  );
}

// ───────────────────────────────────────────── sub-components ──

function StatTile({ value, label, sub }: { value: string; label: string; sub?: string }) {
  return (
    <div className="rounded-2xl bg-white/12 backdrop-blur-md border border-white/20 px-4 py-4 hover:bg-white/15 transition-colors">
      <div className="text-2xl md:text-3xl font-extrabold tracking-tight">{value}</div>
      <div className="text-xs md:text-sm text-white/85 mt-0.5 font-semibold">{label}</div>
      {sub && <div className="text-[10px] text-white/65 mt-0.5">{sub}</div>}
    </div>
  );
}

function PatternStat({ icon: Icon, label, value }: { icon: any; label: string; value: string }) {
  return (
    <div className="flex items-center gap-3">
      <div className="w-10 h-10 rounded-xl bg-emerald-100 dark:bg-emerald-950/60 flex items-center justify-center shrink-0">
        <Icon className="w-5 h-5 text-emerald-700 dark:text-emerald-400" />
      </div>
      <div className="min-w-0">
        <div className="text-[10px] uppercase tracking-wider text-muted-foreground font-semibold">{label}</div>
        <div className="font-bold text-foreground truncate">{value}</div>
      </div>
    </div>
  );
}