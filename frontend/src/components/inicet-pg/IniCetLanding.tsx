/**
 * IniCetLanding — premium landing for /inicet.
 *
 * Sister of NeetPgLanding (which lives at /neet-pg). Different visual
 * language: indigo / sky / fuchsia medical-academic palette to
 * distinguish AIIMS / PGIMER / JIPMER / NIMHANS from NEET PG.
 *
 * Highlights the image-heavy recall style that INI-CET is famous for:
 * every subject PDF contains full-page diagrams + deep explanation
 * images. The page surfaces that strength with a "Why INI-CET on
 * CrackCMS" explainer block.
 */
'use client';
import Link from 'next/link';
import { useEffect, useMemo, useState } from 'react';
import {
  Activity, ArrowRight, Award, BookOpen, Brain, Calendar,
  ChevronRight, Clock, FileImage, Filter, FlaskConical,
  GraduationCap, HeartPulse, Image as ImageIcon, Layers, Microscope,
  Pill, ScanSearch, Sparkles, Stethoscope, Target, Zap,
} from 'lucide-react';
import { questionsAPI } from '@/lib/api';
import { Card, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Skeleton } from '@/components/ui/skeleton';
import { cn } from '@/lib/utils';

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

const SUBJECT_VISUAL: Record<string, { icon: any; gradient: string; ring: string; tone: string; blurb: string }> = {
  MED: { icon: HeartPulse, gradient: 'from-indigo-500 to-blue-600', ring: 'ring-indigo-300', tone: 'bg-indigo-50 dark:bg-indigo-950/40 text-indigo-700 dark:text-indigo-300', blurb: 'Cardiology, endo, neuro, GI, infectious.' },
  SUR: { icon: Stethoscope, gradient: 'from-sky-500 to-indigo-600', ring: 'ring-sky-300', tone: 'bg-sky-50 dark:bg-sky-950/40 text-sky-700 dark:text-sky-300', blurb: 'General + ortho + anaesthesia basics.' },
  OBG: { icon: HeartPulse, gradient: 'from-fuchsia-500 to-pink-600', ring: 'ring-fuchsia-300', tone: 'bg-fuchsia-50 dark:bg-fuchsia-950/40 text-fuchsia-700 dark:text-fuchsia-300', blurb: 'Antenatal, labour, gynae oncology.' },
  PED: { icon: Activity, gradient: 'from-violet-500 to-purple-600', ring: 'ring-violet-300', tone: 'bg-violet-50 dark:bg-violet-950/40 text-violet-700 dark:text-violet-300', blurb: 'Neonatology, growth, immunization.' },
  PSM: { icon: Layers, gradient: 'from-cyan-500 to-blue-600', ring: 'ring-cyan-300', tone: 'bg-cyan-50 dark:bg-cyan-950/40 text-cyan-700 dark:text-cyan-300', blurb: 'Epidemiology, biostatistics, NHM.' },
  ANA: { icon: Microscope, gradient: 'from-purple-500 to-fuchsia-600', ring: 'ring-purple-300', tone: 'bg-purple-50 dark:bg-purple-950/40 text-purple-700 dark:text-purple-300', blurb: 'Embryology, histology, neuroanatomy.' },
  PHY: { icon: Activity, gradient: 'from-blue-500 to-indigo-600', ring: 'ring-blue-300', tone: 'bg-blue-50 dark:bg-blue-950/40 text-blue-700 dark:text-blue-300', blurb: 'General, systemic, neurophysiology.' },
  BCH: { icon: FlaskConical, gradient: 'from-teal-500 to-cyan-600', ring: 'ring-teal-300', tone: 'bg-teal-50 dark:bg-teal-950/40 text-teal-700 dark:text-teal-300', blurb: 'Enzymes, metabolism, inborn errors.' },
  PTH: { icon: Microscope, gradient: 'from-amber-500 to-orange-600', ring: 'ring-amber-300', tone: 'bg-amber-50 dark:bg-amber-950/40 text-amber-700 dark:text-amber-300', blurb: 'General + systemic pathology.' },
  PHR: { icon: Pill, gradient: 'from-indigo-500 to-violet-600', ring: 'ring-indigo-300', tone: 'bg-indigo-50 dark:bg-indigo-950/40 text-indigo-700 dark:text-indigo-300', blurb: 'ANS, CVS, CNS, chemotherapy.' },
  MIC: { icon: Microscope, gradient: 'from-cyan-500 to-teal-600', ring: 'ring-cyan-300', tone: 'bg-cyan-50 dark:bg-cyan-950/40 text-cyan-700 dark:text-cyan-300', blurb: 'Bacteriology, virology, immunology.' },
  FMT: { icon: BookOpen, gradient: 'from-slate-500 to-zinc-600', ring: 'ring-slate-300', tone: 'bg-slate-50 dark:bg-slate-950/40 text-slate-700 dark:text-slate-300', blurb: 'Forensic pathology, toxicology.' },
  DER: { icon: Sparkles, gradient: 'from-pink-500 to-rose-600', ring: 'ring-pink-300', tone: 'bg-pink-50 dark:bg-pink-950/40 text-pink-700 dark:text-pink-300', blurb: 'Skin disorders, STIs, leprosy.' },
  ENT: { icon: Stethoscope, gradient: 'from-orange-500 to-amber-600', ring: 'ring-orange-300', tone: 'bg-orange-50 dark:bg-orange-950/40 text-orange-700 dark:text-orange-300', blurb: 'Ear, nose, throat.' },
  OPH: { icon: Target, gradient: 'from-blue-500 to-sky-600', ring: 'ring-blue-300', tone: 'bg-blue-50 dark:bg-blue-950/40 text-blue-700 dark:text-blue-300', blurb: 'Refraction, retina, glaucoma.' },
  ORT: { icon: Activity, gradient: 'from-stone-500 to-zinc-600', ring: 'ring-stone-300', tone: 'bg-stone-50 dark:bg-stone-950/40 text-stone-700 dark:text-stone-300', blurb: 'Fractures, joint disease, spine.' },
  PSY: { icon: Brain, gradient: 'from-violet-500 to-indigo-600', ring: 'ring-violet-300', tone: 'bg-violet-50 dark:bg-violet-950/40 text-violet-700 dark:text-violet-300', blurb: 'Mood, anxiety, psychosis.' },
  RAD: { icon: ScanSearch, gradient: 'from-sky-500 to-blue-600', ring: 'ring-sky-300', tone: 'bg-sky-50 dark:bg-sky-950/40 text-sky-700 dark:text-sky-300', blurb: 'Imaging modalities, signs — image-heavy.' },
  ANS: { icon: Pill, gradient: 'from-fuchsia-500 to-purple-600', ring: 'ring-fuchsia-300', tone: 'bg-fuchsia-50 dark:bg-fuchsia-950/40 text-fuchsia-700 dark:text-fuchsia-300', blurb: 'Anaesthesia, critical care.' },
};

const DEFAULT_VISUAL = {
  icon: BookOpen, gradient: 'from-indigo-500 to-sky-600', ring: 'ring-indigo-300',
  tone: 'bg-indigo-50 dark:bg-indigo-950/40 text-indigo-700 dark:text-indigo-300',
  blurb: '',
};

const INSTITUTES = [
  { name: 'AIIMS', subspecialty: 'New Delhi · Bhubaneswar · Jodhpur · Rishikesh · Patna · Raipur · Bhopal · Nagpur · Bibinagar · Mangalagiri · Bathinda · Deoghar · Kalyani · Gorakhpur · Guwahati · Bilaspur · Rajkot · Vijaypur' },
  { name: 'PGIMER', subspecialty: 'Chandigarh' },
  { name: 'JIPMER', subspecialty: 'Puducherry · Karaikal' },
  { name: 'NIMHANS', subspecialty: 'Bengaluru' },
  { name: 'SCTIMST', subspecialty: 'Trivandrum' },
];

const HIGH_YIELD = [
  { topic: 'Clinical case scenarios', count: '60-70% of paper', tag: 'MED', reason: 'Long vignettes, multi-system reasoning.' },
  { topic: 'Image-based diagnosis', count: '15-20 Qs / paper', tag: 'RAD', reason: 'CT, MRI, X-ray, histopathology slides.' },
  { topic: 'Recent advances + guidelines', count: '5-8 Qs / paper', tag: 'MED', reason: 'Newer trials, AHA / WHO updates.' },
  { topic: 'Instrument & specimen ID', count: '3-5 Qs / paper', tag: 'SUR', reason: 'Anatomy, pathology specimens.' },
  { topic: 'Drug adverse effects & interactions', count: '6-8 Qs / paper', tag: 'PHR', reason: 'High-yield pharmacology recall.' },
];

const HOW_IT_WORKS = [
  {
    n: '01', icon: FileImage,
    title: 'Open a subject recall PDF',
    body: 'Each INI-CET subject PDF is loaded as image-rich cards — diagrams stay sharp at any zoom level.',
  },
  {
    n: '02', icon: ScanSearch,
    title: 'Practise image-first',
    body: 'Zoomable image viewer, multi-image stems, and explanation images inside the answer panel.',
  },
  {
    n: '03', icon: Brain,
    title: 'AI tutor for clinical reasoning',
    body: 'Differential dx, workup, clinical pearl — the AI tutor reasons through every multi-step vignette.',
  },
];

const FAQS = [
  { q: 'What is INI-CET?', a: 'INI-CET (Institute of National Importance Combined Entrance Test) is the common entrance exam for PG medical courses (MD / MS / DM / MCh / MDS) at AIIMS, PGIMER, JIPMER, NIMHANS, and SCTIMST. Conducted twice a year by AIIMS, New Delhi.' },
  { q: 'How is INI-CET different from NEET PG?', a: 'INI-CET is the entrance only for Institutes of National Importance. The paper pattern, syllabus weightage, and difficulty differ — INI-CET is widely considered more clinical-case-heavy and image-rich.' },
  { q: 'How many questions in INI-CET?', a: '200 MCQs in 3 hours (Stage I) / 90 minutes (Stage II for some institutes). Usually 1.5× – 2× the difficulty of NEET PG.' },
  { q: 'Why use CrackCMS for INI-CET prep?', a: 'Subject-wise image-rich recall PDFs, full PYQ coverage, AI tutor trained on standard PG references, and a dedicated indigo / sky medical-academic player UI.' },
];

export default function IniCetLanding() {
  const [stats, setStats] = useState<StatsPayload | null>(null);
  const [subjects, setSubjects] = useState<SubjectRow[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        // INI-CET data is filtered via exam_source since the Question model
        // also stores the older slug.
        const [statsRes, subjectsRes] = await Promise.all([
          questionsAPI.getStats({ exam_source: 'INI-CET' }),
          questionsAPI.getSubjects(),
        ]);
        if (cancelled) return;
        const rawStats = statsRes.data as any;
        const subjRows = ((subjectsRes.data as any)?.results || (subjectsRes.data as any) || []) as SubjectRow[];
        setStats({
          total: rawStats.total ?? 0,
          total_solved: rawStats.total_solved ?? 0,
          by_year: rawStats.by_year ?? [],
          by_subject: rawStats.by_subject ?? [],
        });
        setSubjects(subjRows);
      } catch {
        // graceful degradation
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, []);

  const totalQs = stats?.total ?? 0;
  const totalYears = stats?.by_year.length ?? 0;
  const totalSubjects = subjects.length || 19;

  const featuredYear = useMemo(() => {
    const currentYear = new Date().getFullYear();
    if (!stats?.by_year?.length) return currentYear;
    const top = [...stats.by_year].sort((a, b) => b.year - a.year)[0];
    return top?.year ?? currentYear;
  }, [stats]);

  return (
    <main className="min-h-screen bg-background text-foreground">
      {/* ════════════════ HERO ════════════════ */}
      <section className="relative overflow-hidden bg-linear-to-br from-indigo-700 via-violet-700 to-sky-800 text-white">
        <div className="absolute inset-0 pointer-events-none opacity-30"
             style={{
               backgroundImage:
                 'radial-gradient(circle at 20% 25%, rgba(255,255,255,0.30), transparent 55%),' +
                 'radial-gradient(circle at 80% 70%, rgba(255,255,255,0.22), transparent 55%),' +
                 'radial-gradient(circle at 50% 100%, rgba(99,102,241,0.40), transparent 60%)',
             }} />
        <svg className="absolute inset-x-0 bottom-0 w-full h-32 opacity-25 pointer-events-none" viewBox="0 0 1200 120" preserveAspectRatio="none" aria-hidden>
          <path d="M0,60 L200,60 L220,40 L240,80 L260,55 L280,68 L320,60 L500,60 L520,28 L540,92 L560,55 L580,72 L620,60 L800,60 L820,40 L840,84 L860,55 L880,68 L920,60 L1100,60 L1120,32 L1140,88 L1160,60 L1200,60"
                fill="none" stroke="rgba(255,255,255,0.85)" strokeWidth="2" />
        </svg>

        <div className="relative max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-16 lg:py-24">
          <div className="flex flex-wrap items-center gap-2 mb-6">
            <Badge className="bg-white/15 text-white border border-white/20 backdrop-blur-sm hover:bg-white/25 px-3 py-1">
              🏥 AIIMS · PGIMER · JIPMER · NIMHANS · SCTIMST
            </Badge>
            <Badge className="bg-indigo-500/30 text-white border border-indigo-300/40 backdrop-blur-sm hover:bg-indigo-500/40 px-3 py-1">
              INI-CET
            </Badge>
            <Badge className="bg-sky-500/30 text-white border border-sky-300/40 backdrop-blur-sm hover:bg-sky-500/40 px-3 py-1">
              MD · MS · DM · MCh
            </Badge>
          </div>

          <h1 className="text-4xl md:text-5xl lg:text-7xl font-extrabold tracking-tight leading-[1.05] max-w-4xl">
            INI-CET
            <span className="block text-2xl md:text-3xl lg:text-4xl font-semibold mt-3 text-white/90">
              Image-Heavy Recalls · AIIMS-Standard · AI Tutor
            </span>
          </h1>

          <p className="mt-6 text-base md:text-xl max-w-2xl text-white/90 leading-relaxed">
            India&apos;s only INI-CET platform with full subject-recall PDFs (radiology, histopath, dermatology), image-first player, and AI tutor trained on Harrison, Robbins, Bailey &amp; Love.
          </p>

          <div className="mt-8 flex flex-wrap gap-3">
            <Button asChild size="lg" className="bg-white text-indigo-800 hover:bg-white/95 font-bold shadow-2xl shadow-indigo-900/30">
              <Link href={`/questions/inicet/practice?year=${featuredYear}`}>
                <Zap className="w-4 h-4 mr-2 fill-indigo-700" />
                Start INI-CET {featuredYear}
              </Link>
            </Button>
            <Button asChild size="lg" variant="outline"
                    className="bg-transparent border-white/40 text-white hover:bg-white/10 hover:border-white/60 backdrop-blur-sm font-semibold">
              <Link href="/questions?exam=ini-cet">
                <Filter className="w-4 h-4 mr-2" />
                Open QBank
              </Link>
            </Button>
            <Button asChild size="lg" variant="outline"
                    className="bg-indigo-500/20 border-white/30 text-white hover:bg-indigo-500/30 backdrop-blur-sm font-semibold">
              <Link href="#subjects">
                <Layers className="w-4 h-4 mr-2" />
                Browse 19 Subjects
              </Link>
            </Button>
          </div>

          <div className="mt-10 grid grid-cols-2 sm:grid-cols-4 gap-3 max-w-4xl">
            <StatTile value={loading ? '—' : `${totalQs.toLocaleString()}+`} label="INI-CET Recalls" sub="live from API" />
            <StatTile value={loading ? '—' : `${totalYears}`} label="Recent Sessions" sub="2025 → earlier" />
            <StatTile value={loading ? '—' : `${totalSubjects}`} label="PG Subjects" sub="all 19 mapped" />
            <StatTile value="200" label="Qs per paper" sub="Stage I — 3 hours" />
          </div>
        </div>
      </section>

      {/* Institute strip */}
      <section className="border-y border-border/60 bg-card/60 backdrop-blur-sm">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
          <h3 className="text-[11px] font-bold uppercase tracking-wider text-muted-foreground mb-3 text-center">
            CrackCMS covers INI-CET for India&apos;s Institutes of National Importance
          </h3>
          <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
            {INSTITUTES.map((inst) => (
              <div key={inst.name} className="rounded-xl bg-linear-to-br from-indigo-50/70 to-white dark:from-indigo-950/40 dark:to-slate-900 border border-indigo-200/60 dark:border-indigo-900/40 p-3 text-center">
                <div className="font-extrabold text-base text-indigo-800 dark:text-indigo-300">{inst.name}</div>
                <div className="text-[10px] text-muted-foreground mt-1 leading-tight">{inst.subspecialty}</div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Pattern strip */}
      <section className="border-b border-border/60 bg-card/40">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6 grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-4">
          <PatternStat icon={Target} label="Mode" value="Online CBT" />
          <PatternStat icon={BookOpen} label="Questions" value="200 MCQs" />
          <PatternStat icon={Clock} label="Time" value="3 hours" />
          <PatternStat icon={Award} label="Marks" value="Institute-specific" />
          <PatternStat icon={GraduationCap} label="Sittings" value="Jan + July" />
          <PatternStat icon={Sparkles} label="Standard" value="AIIMS-grade" />
        </div>
      </section>

      {/* ════════════════ YEAR GRID ════════════════ */}
      <section id="years" className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-12 lg:py-16">
        <div className="flex items-end justify-between flex-wrap gap-3 mb-6">
          <div>
            <h2 className="text-2xl md:text-4xl font-bold flex items-center gap-2">
              <Calendar className="w-7 h-7 text-indigo-600" /> Recent INI-CET Papers
            </h2>
            <p className="text-sm md:text-base text-muted-foreground mt-2 max-w-2xl">
              Tap a session to launch the dedicated INI-CET player — image-first, multi-image stems, full explanation panels.
            </p>
          </div>
          <Badge variant="secondary" className="text-xs">
            {loading ? '—' : totalYears} sessions available
          </Badge>
        </div>

        {loading ? (
          <div className="grid grid-cols-3 sm:grid-cols-4 md:grid-cols-6 lg:grid-cols-8 gap-3">
            {Array.from({ length: 6 }).map((_, i) => (
              <Skeleton key={i} className="aspect-square rounded-2xl" />
            ))}
          </div>
        ) : (stats?.by_year ?? []).length === 0 ? (
          <div className="rounded-2xl border border-dashed border-indigo-300 bg-indigo-50/30 dark:bg-indigo-950/20 p-10 text-center">
            <ImageIcon className="w-10 h-10 mx-auto text-indigo-400 mb-3" />
            <h3 className="font-bold text-lg">More INI-CET content is on the way</h3>
            <p className="text-sm text-muted-foreground mt-1 max-w-md mx-auto">
              We&apos;re extracting image-rich recall PDFs and indexing them as Questions. In the meantime, browse subjects below.
            </p>
            <Button asChild className="mt-4 bg-indigo-600 hover:bg-indigo-700">
              <Link href="#subjects"><Layers className="w-4 h-4 mr-2" /> Browse Subjects</Link>
            </Button>
          </div>
        ) : (
          <div className="grid grid-cols-3 sm:grid-cols-4 md:grid-cols-6 lg:grid-cols-8 gap-3">
            {stats?.by_year.map((y) => (
              <Link key={y.year} href={`/questions/inicet/practice?year=${y.year}`} className="group">
                <div className="aspect-square rounded-2xl border border-indigo-200/60 dark:border-indigo-800/40 bg-linear-to-br from-indigo-50/60 via-white to-sky-50/60 dark:from-indigo-950/40 dark:via-slate-900 dark:to-sky-950/30 hover:border-indigo-400 hover:shadow-lg hover:shadow-indigo-500/10 transition-all flex flex-col items-center justify-center text-center p-2 group-hover:scale-[1.03]">
                  <div className="text-2xl md:text-3xl font-extrabold text-indigo-800 dark:text-indigo-300 group-hover:text-indigo-600">
                    {y.year}
                  </div>
                  <div className="text-[10px] uppercase tracking-wider mt-0.5 text-indigo-600/80 dark:text-indigo-400/80">
                    INI-CET
                  </div>
                  <div className="mt-1 text-[10px] font-semibold text-muted-foreground">
                    {y.count.toLocaleString()} Qs
                  </div>
                  <div className="w-full bg-indigo-100/60 dark:bg-indigo-900/40 h-1 rounded-full overflow-hidden mt-1.5">
                    <div className="h-full bg-indigo-500 transition-all"
                         style={{ width: `${Math.min(100, Math.round((y.solved / (y.count || 1)) * 100))}%` }} />
                  </div>
                </div>
              </Link>
            ))}
          </div>
        )}
      </section>

      {/* ════════════════ SUBJECT GRID ════════════════ */}
      <section id="subjects" className="bg-linear-to-br from-indigo-50/40 via-background to-sky-50/40 border-y border-border/60">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-12 lg:py-16">
          <div className="flex items-end justify-between flex-wrap gap-3 mb-6">
            <div>
              <h2 className="text-2xl md:text-4xl font-bold flex items-center gap-2">
                <Layers className="w-7 h-7 text-indigo-600" />
                19 INI-CET Subjects · Tap to Practise
              </h2>
              <p className="text-sm md:text-base text-muted-foreground mt-2 max-w-2xl">
                Image-rich recall cards — every diagram, every annotation preserved at full zoom.
              </p>
            </div>
            <Button asChild variant="outline" size="sm" className="border-indigo-300 text-indigo-700 hover:bg-indigo-50">
              <Link href="/questions?exam=ini-cet">
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
                  <Link key={s.id} href={`/questions/inicet/practice?subject=${s.id}`}
                        className="group">
                    <Card className={cn(
                      'h-full border-border/60 bg-card/90 hover:border-indigo-400/60 transition-all group-hover:shadow-xl group-hover:-translate-y-0.5 overflow-hidden',
                      'dark:bg-slate-900/70 dark:border-slate-800'
                    )}>
                      <div className={cn('h-1.5 w-full bg-linear-to-r', v.gradient)} />
                      <CardContent className="p-5 space-y-3">
                        <div className="flex items-start justify-between">
                          <div className={cn(
                            'w-11 h-11 rounded-xl flex items-center justify-center bg-linear-to-br shadow-md ring-2',
                            v.gradient, v.ring,
                          )}>
                            <Icon className="w-5 h-5 text-white" />
                          </div>
                          <Badge variant="outline" className="font-mono text-[10px]">
                            {s.code}
                          </Badge>
                        </div>
                        <div>
                          <h3 className="font-bold text-base group-hover:text-indigo-600 dark:group-hover:text-indigo-400 transition-colors">
                            {s.name}
                          </h3>
                          <p className="text-xs text-muted-foreground mt-1 leading-relaxed line-clamp-2">
                            {v.blurb}
                          </p>
                        </div>
                        <div className="flex items-end justify-between pt-2 border-t border-border/40">
                          <div>
                            <div className="text-2xl font-extrabold text-indigo-700 dark:text-indigo-400">
                              {count.toLocaleString()}
                            </div>
                            <div className="text-[10px] uppercase tracking-wider text-muted-foreground mt-0.5">
                              Recalls available
                            </div>
                          </div>
                          <ArrowRight className="w-4 h-4 text-indigo-600 opacity-0 group-hover:opacity-100 transition-opacity" />
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

      {/* High-yield */}
      <section id="high-yield" className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-12 lg:py-16">
        <div className="flex items-center gap-3 mb-6">
          <Sparkles className="w-7 h-7 text-indigo-600" />
          <h2 className="text-2xl md:text-4xl font-bold">High-yield patterns INI-CET loves</h2>
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
                      'w-10 h-10 rounded-xl flex items-center justify-center bg-linear-to-br shadow-sm',
                      v.gradient,
                    )}>
                      <Icon className="w-5 h-5 text-white" />
                    </div>
                    <Badge variant="outline" className="font-mono text-[10px]">{h.tag}</Badge>
                  </div>
                  <h3 className="font-semibold text-foreground">{h.topic}</h3>
                  <p className="text-xs text-muted-foreground leading-relaxed">{h.reason}</p>
                  <div className="text-[11px] font-bold text-indigo-600 dark:text-indigo-400 uppercase tracking-wider">
                    {h.count}
                  </div>
                </CardContent>
              </Card>
            );
          })}
        </div>
      </section>

      {/* How it works */}
      <section className="bg-indigo-50/40 dark:bg-indigo-950/20 border-y border-border/60">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-12 lg:py-16">
          <h2 className="text-2xl md:text-4xl font-bold flex items-center gap-2 mb-8">
            <GraduationCap className="w-7 h-7 text-indigo-600" />
            How CrackCMS helps you crack INI-CET
          </h2>
          <div className="grid md:grid-cols-3 gap-5">
            {HOW_IT_WORKS.map((step) => {
              const Icon = step.icon;
              return (
                <Card key={step.n} className="border-indigo-200/60 dark:border-indigo-900/40 bg-card/95 dark:bg-slate-900/70">
                  <CardContent className="p-6 space-y-4">
                    <div className="flex items-center justify-between">
                      <div className="text-5xl font-extrabold bg-linear-to-br from-indigo-500 to-sky-700 bg-clip-text text-transparent">
                        {step.n}
                      </div>
                      <div className="w-12 h-12 rounded-xl bg-indigo-100 dark:bg-indigo-950/60 flex items-center justify-center">
                        <Icon className="w-6 h-6 text-indigo-700 dark:text-indigo-400" />
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

      {/* FAQ */}
      <section className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 py-12 lg:py-16">
        <h2 className="text-2xl md:text-4xl font-bold flex items-center gap-2 mb-6">
          <Brain className="w-7 h-7 text-indigo-600" />
          INI-CET FAQs
        </h2>
        <div className="space-y-3">
          {FAQS.map((f) => (
            <details key={f.q} className="group rounded-2xl border border-border/60 bg-card/90 dark:bg-slate-900/60 overflow-hidden">
              <summary className="cursor-pointer list-none p-5 flex items-start justify-between gap-4 hover:bg-indigo-50/30 dark:hover:bg-indigo-950/20">
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

      {/* From the Blog (internal-link cluster) */}
      <section className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-12 lg:py-16">
        <div className="flex items-end justify-between gap-4 mb-6">
          <div>
            <span className="inline-flex items-center rounded-full bg-indigo-600/10 text-indigo-700 dark:text-indigo-300 border border-indigo-600/30 px-3 py-1 text-xs font-bold uppercase tracking-wider">
              From the Blog
            </span>
            <h2 className="mt-3 text-2xl md:text-4xl font-bold tracking-tight">
              INI-CET deep-dive guides
            </h2>
            <p className="mt-2 text-sm text-muted-foreground max-w-2xl">
              Long-form, EEAT-reviewed coverage of INI-CET cutoffs, comparison with NEET PG, and strategy.
            </p>
          </div>
          <Link href="/blog" className="hidden sm:inline-flex items-center gap-1 text-sm font-semibold text-indigo-700 hover:underline shrink-0">
            All posts →
          </Link>
        </div>
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
          {[
            {
              slug: 'ini-cet-2024-cutoff-closing-ranks',
              title: 'INI-CET 2024 Cutoff: Closing Ranks by Institute (Jan + July)',
              excerpt: 'AIIMS Delhi, PGIMER, JIPMER, NIMHANS — closing ranks for both sessions.',
            },
            {
              slug: 'neet-pg-vs-ini-cet',
              title: 'NEET PG vs INI-CET: Difficulty, Syllabus, Salary & Strategy',
              excerpt: 'Honest comparison — including how to attempt both without burning out.',
            },
            {
              slug: 'cms-vs-neet-pg-vs-ini-cet',
              title: 'CMS vs NEET PG vs INI-CET: Which PG Exam is Right for You?',
              excerpt: 'Definitive three-way comparison across salary, lifestyle, and 5-year trajectory.',
            },
            {
              slug: 'best-pg-medical-entrance-books',
              title: 'Best Medical PG Entrance Books: Verified by PYQs (2026)',
              excerpt: 'Every title on this list has appeared in UPSC CMS / NEET PG / INI-CET PYQs.',
            },
          ].map((p) => (
            <Link
              key={p.slug}
              href={`/blog/${p.slug}`}
              className="group rounded-2xl border border-border/60 bg-card/90 dark:bg-slate-900/60 p-5 transition-all hover:border-indigo-500/50 hover:shadow-md"
            >
              <h3 className="text-base font-bold text-foreground group-hover:text-indigo-600 transition-colors leading-snug">
                {p.title}
              </h3>
              <p className="mt-2 text-sm leading-relaxed text-muted-foreground line-clamp-3">
                {p.excerpt}
              </p>
              <p className="mt-3 inline-flex items-center gap-1 text-xs font-bold uppercase tracking-wider text-indigo-600">
                Read guide <span className="transition-transform group-hover:translate-x-0.5">→</span>
              </p>
            </Link>
          ))}
        </div>
      </section>

      {/* CTA strip */}
      <section className="bg-linear-to-br from-indigo-700 via-violet-700 to-sky-800 text-white">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-12 lg:py-16 text-center">
          <Award className="w-12 h-12 mx-auto mb-4 text-indigo-200" />
          <h2 className="text-3xl md:text-5xl font-extrabold max-w-3xl mx-auto">
            Ready to crack INI-CET {featuredYear + 1}?
          </h2>
          <p className="mt-3 text-indigo-100/90 max-w-xl mx-auto">
            Open the latest recall set, scan images, drill differentials — image-rich AIIMS-grade reasoning.
          </p>
          <div className="mt-7 flex flex-wrap gap-3 justify-center">
            <Button asChild size="lg" className="bg-white text-indigo-800 hover:bg-white/95 font-bold shadow-xl">
              <Link href={`/questions/inicet/practice?year=${featuredYear}`}>
                <Zap className="w-4 h-4 mr-2 fill-indigo-700" />
                Start {featuredYear} Set
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

      <footer className="border-t border-border/40 bg-muted/30">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6 flex flex-wrap items-center justify-between gap-3 text-xs text-muted-foreground">
          <span>© {new Date().getFullYear()} CrackCMS · INI-CET microsite</span>
          <span className="flex items-center gap-3">
            <Link href="/exams/cms" className="hover:text-primary">UPSC CMS</Link>
            <span>·</span>
            <Link href="/neet-pg" className="hover:text-primary">NEET PG</Link>
            <span>·</span>
            <Link href="/exams/usmle" className="hover:text-primary">USMLE</Link>
            <span>·</span>
            <Link href="/inicet" className="hover:text-primary font-semibold">INI-CET</Link>
          </span>
        </div>
      </footer>
    </main>
  );
}

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
      <div className="w-10 h-10 rounded-xl bg-indigo-100 dark:bg-indigo-950/60 flex items-center justify-center shrink-0">
        <Icon className="w-5 h-5 text-indigo-700 dark:text-indigo-400" />
      </div>
      <div className="min-w-0">
        <div className="text-[10px] uppercase tracking-wider text-muted-foreground font-semibold">{label}</div>
        <div className="font-bold text-foreground truncate">{value}</div>
      </div>
    </div>
  );
}