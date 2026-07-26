'use client';
/**
 * components/exams/ExamMicrosite.tsx — Shared shell for the three exam
 * microsites (/exams/cms, /exams/neet-pg, /exams/usmle).
 *
 * Renders the hero, stats strip, eligibility card, subject grid, high-yield
 * list, and the year-wise PYQ grid. Each exam only customizes theme +
 * content; the layout is shared so the sites feel like one product family.
 */
import Link from 'next/link';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import {
  ArrowRight, BookOpen, Calendar, CheckCircle2, ChevronRight,
  Clock, GraduationCap, Layers, Sparkles, Target, TrendingUp,
  Users,
} from 'lucide-react';
import type { ExamConfig } from '@/app/exams/_data';

interface Props { cfg: ExamConfig }

export function ExamMicrosite({ cfg }: Props) {
  return (
    <main className="min-h-screen bg-background">
      {/* ── HERO ───────────────────────────────────────────── */}
      <section className={`relative overflow-hidden bg-linear-to-br ${cfg.theme.heroGradient} text-white`}>
        <div className="absolute inset-0 opacity-30 mix-blend-overlay pointer-events-none"
             style={{
               backgroundImage:
                 'radial-gradient(circle at 20% 20%, rgba(255,255,255,0.25), transparent 50%),' +
                 'radial-gradient(circle at 80% 70%, rgba(255,255,255,0.18), transparent 50%)',
             }} />
        <div className="relative max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-16 lg:py-24">
          <div className="flex flex-wrap gap-2 mb-6">
            <Badge className="bg-white/15 text-white border border-white/20 backdrop-blur-sm hover:bg-white/25">
              {cfg.theme.badgeText}
            </Badge>
            {cfg.tags.map((t) => (
              <Badge key={t} className="bg-white/10 text-white/90 border border-white/15 hover:bg-white/20">
                {t}
              </Badge>
            ))}
          </div>
          <h1 className="text-4xl md:text-5xl lg:text-6xl font-extrabold tracking-tight max-w-3xl leading-tight">
            {cfg.shortName}
            <span className="block text-2xl md:text-3xl font-semibold mt-3 text-white/85">
              {cfg.fullName}
            </span>
          </h1>
          <p className="mt-5 text-lg md:text-xl max-w-2xl text-white/90 leading-relaxed">
            {cfg.tagline}
          </p>

          <div className="mt-8 flex flex-wrap gap-3">
            <Button asChild size="lg"
              className="bg-white text-slate-900 hover:bg-white/90 font-semibold shadow-lg">
              <Link href={cfg.primaryCta.href}>
                {cfg.primaryCta.label} <ArrowRight className="ml-2 w-4 h-4" />
              </Link>
            </Button>
            <Button asChild size="lg" variant="outline"
              className="bg-transparent border-white/40 text-white hover:bg-white/10 hover:border-white/60">
              <Link href={cfg.secondaryCta.href}>{cfg.secondaryCta.label}</Link>
            </Button>
          </div>

          {/* stats row */}
          <div className="mt-10 grid grid-cols-3 gap-3 sm:gap-6 max-w-2xl">
            {cfg.stats.map((s) => (
              <div key={s.label}
                className="rounded-2xl bg-white/10 backdrop-blur-sm border border-white/15 px-4 py-4">
                <div className="text-2xl md:text-3xl font-extrabold">{s.value}</div>
                <div className="text-xs md:text-sm text-white/80 mt-0.5">{s.label}</div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── ABOUT + PATTERN ──────────────────────────────── */}
      <section className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-12 lg:py-16">
        <div className="grid md:grid-cols-3 gap-6">
          <div className="md:col-span-2">
            <h2 className="text-2xl md:text-3xl font-bold text-foreground">
              About the {cfg.shortName} exam
            </h2>
            <p className="mt-3 text-base md:text-lg text-muted-foreground leading-relaxed">
              {cfg.description}
            </p>
          </div>
          <Card className="border-border/60 bg-card/80 backdrop-blur-sm shadow-sm">
            <CardHeader className="pb-3 border-b border-border/40">
              <CardTitle className="flex items-center gap-2 text-base">
                <Target className="w-4 h-4 text-amber-500" /> Exam Pattern
              </CardTitle>
            </CardHeader>
            <CardContent className="pt-4 space-y-3 text-sm">
              <PatternRow label="Type" value={cfg.pattern.type} />
              <PatternRow label="Total Marks" value={cfg.pattern.totalMarks} />
              <PatternRow label="Duration" value={cfg.pattern.duration} />
              <PatternRow label="Negative Marking" value={cfg.pattern.negativeMarking} accent />
            </CardContent>
          </Card>
        </div>
      </section>

      {/* ── ELIGIBILITY ──────────────────────────────────── */}
      <section className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 pb-12">
        <Card className="border-border/60 bg-card/80 backdrop-blur-sm shadow-sm">
          <CardHeader className="pb-3 border-b border-border/40">
            <CardTitle className="flex items-center gap-2 text-lg">
              <CheckCircle2 className="w-5 h-5 text-emerald-500" /> Eligibility Criteria
            </CardTitle>
          </CardHeader>
          <CardContent className="pt-6 grid sm:grid-cols-2 lg:grid-cols-4 gap-5">
            {cfg.eligibility.map((e) => (
              <div key={e.label} className="flex gap-3 items-start">
                <div className={`w-9 h-9 rounded-lg ${cfg.theme.tint} flex items-center justify-center shrink-0`}>
                  <Users className={`w-4 h-4 ${cfg.theme.primary}`} />
                </div>
                <div>
                  <h4 className="text-xs font-bold uppercase tracking-wider text-muted-foreground">
                    {e.label}
                  </h4>
                  <p className="mt-1 text-sm text-foreground leading-snug">{e.value}</p>
                </div>
              </div>
            ))}
          </CardContent>
        </Card>
      </section>

      {/* ── SUBJECTS ─────────────────────────────────────── */}
      <section id="subjects" className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 pb-12 lg:pb-16">
        <div className="flex items-end justify-between flex-wrap gap-3 mb-6">
          <div>
            <h2 className="text-2xl md:text-3xl font-bold text-foreground flex items-center gap-2">
              <Layers className={`w-6 h-6 ${cfg.theme.primary}`} /> Subjects you'll master
            </h2>
            <p className="text-sm md:text-base text-muted-foreground mt-1.5">
              Tap any subject to filter the question bank by it.
            </p>
          </div>
          <Button asChild variant="outline" size="sm">
            <Link href={`/questions?exam_type=${cfg.slug === 'neet-pg' ? 'neet-pg' : cfg.slug === 'cms' ? 'cms' : 'usmle'}`}>
              Open QBank <ChevronRight className="w-4 h-4 ml-1" />
            </Link>
          </Button>
        </div>
        <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {cfg.subjects.map((s) => (
            <Link key={s.code} href={`/questions?exam_type=${cfg.slug === 'neet-pg' ? 'neet-pg' : cfg.slug === 'cms' ? 'cms' : 'usmle'}&subject=${encodeURIComponent(s.name)}`}>
              <Card className="h-full border-border/60 hover:border-primary/40 hover:shadow-md transition-all group cursor-pointer">
                <CardContent className="p-5">
                  <div className="flex items-start justify-between gap-2">
                    <Badge variant="outline" className={`${cfg.theme.tint} ${cfg.theme.primary} border-0 font-mono text-xs`}>
                      {s.code}
                    </Badge>
                    <Badge variant="secondary" className="text-[10px] font-normal">
                      {s.weightage}
                    </Badge>
                  </div>
                  <h3 className="mt-3 font-semibold text-foreground group-hover:text-primary transition-colors">
                    {s.name}
                  </h3>
                  <p className="mt-1.5 text-xs text-muted-foreground leading-relaxed">{s.blurb}</p>
                  <div className="mt-3 flex items-center text-xs text-primary opacity-0 group-hover:opacity-100 transition-opacity">
                    Practice {s.name} <ArrowRight className="ml-1 w-3 h-3" />
                  </div>
                </CardContent>
              </Card>
            </Link>
          ))}
        </div>
      </section>

      {/* ── HIGH-YIELD ───────────────────────────────────── */}
      <section id="high-yield" className={`${cfg.theme.tint} border-y border-border/40`}>
        <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-12 lg:py-16">
          <div className="flex items-center gap-3 mb-6">
            <Sparkles className={`w-6 h-6 ${cfg.theme.primary}`} />
            <h2 className="text-2xl md:text-3xl font-bold text-foreground">
              High-yield topics that show up every year
            </h2>
          </div>
          <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-4">
            {cfg.highYield.map((h) => (
              <Card key={h.topic} className="bg-card/90 border-border/60">
                <CardContent className="p-5">
                  <div className="flex items-start gap-2 mb-2">
                    <TrendingUp className={`w-4 h-4 mt-1 shrink-0 ${cfg.theme.primary}`} />
                    <h3 className="font-semibold text-foreground text-sm leading-snug">{h.topic}</h3>
                  </div>
                  <p className="text-xs text-muted-foreground leading-relaxed pl-6">{h.reason}</p>
                </CardContent>
              </Card>
            ))}
          </div>
        </div>
      </section>

      {/* ── YEAR-WISE PYQ GRID ───────────────────────────── */}
      {cfg.pyqYears.length > 0 && (
        <section className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-12 lg:py-16">
          <div className="flex items-end justify-between flex-wrap gap-3 mb-6">
            <div>
              <h2 className="text-2xl md:text-3xl font-bold text-foreground flex items-center gap-2">
                <Calendar className={`w-6 h-6 ${cfg.theme.primary}`} /> PYQ year-wise practice
              </h2>
              <p className="text-sm md:text-base text-muted-foreground mt-1.5">
                Click a year to attempt the full paper in Practice or Exam mode.
              </p>
            </div>
            <Badge variant="secondary" className="text-xs">
              {cfg.pyqYears.length} years of PYQs available
            </Badge>
          </div>
          <div className="grid grid-cols-3 sm:grid-cols-4 md:grid-cols-6 lg:grid-cols-8 gap-3">
            {cfg.pyqYears.map((y) => (
              <Link key={y}
                href={`/questions/practice?year=${y}&exam=${cfg.slug === 'neet-pg' ? 'neet-pg' : cfg.slug === 'cms' ? 'cms' : 'usmle'}`}
                className="group">
                <div className={`aspect-square rounded-2xl border border-border/60 bg-card/80 hover:border-primary/50 hover:bg-card transition-all flex flex-col items-center justify-center text-center shadow-sm hover:shadow-md`}>
                  <div className="text-2xl font-extrabold text-foreground group-hover:text-primary transition-colors">
                    {y}
                  </div>
                  <div className={`text-[10px] uppercase tracking-wider mt-0.5 ${cfg.theme.primary}`}>
                    PYQ
                  </div>
                </div>
              </Link>
            ))}
          </div>
        </section>
      )}

      {/* ── HOW IT WORKS ─────────────────────────────────── */}
      <section className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 pb-16">
        <h2 className="text-2xl md:text-3xl font-bold text-foreground mb-6 flex items-center gap-2">
          <GraduationCap className={`w-6 h-6 ${cfg.theme.primary}`} /> How CrackCMS helps you crack {cfg.shortName}
        </h2>
        <div className="grid md:grid-cols-3 gap-4">
          {[
            {
              icon: BookOpen,
              title: '1. Read the PYQ year',
              body: `Start with one PYQ year from ${cfg.pyqYears[0] ?? '2020'}. Each question comes with subject + topic context.`,
            },
            {
              icon: Target,
              title: '2. Practice or simulate',
              body: 'Switch between Practice Mode (one-by-one with AI explanations) and Exam Mode (timed full-paper simulation).',
            },
            {
              icon: Clock,
              title: '3. Track progress',
              body: 'Year-wise + subject-wise analytics show exactly which high-yield topics you still need to revise.',
            },
          ].map((step) => (
            <Card key={step.title} className="border-border/60 bg-card/80">
              <CardContent className="p-5">
                <div className={`w-10 h-10 rounded-xl ${cfg.theme.tint} flex items-center justify-center mb-3`}>
                  <step.icon className={`w-5 h-5 ${cfg.theme.primary}`} />
                </div>
                <h3 className="font-semibold text-foreground">{step.title}</h3>
                <p className="mt-1.5 text-sm text-muted-foreground leading-relaxed">{step.body}</p>
              </CardContent>
            </Card>
          ))}
        </div>

        <div className="mt-10 flex flex-wrap items-center justify-center gap-3">
          <Button asChild size="lg" className="font-semibold">
            <Link href={cfg.primaryCta.href}>
              {cfg.primaryCta.label} <ArrowRight className="ml-2 w-4 h-4" />
            </Link>
          </Button>
          <Button asChild size="lg" variant="outline">
            <Link href="/dashboard">Back to Dashboard</Link>
          </Button>
        </div>
      </section>

      {/* footer-light */}
      <footer className="border-t border-border/40 bg-muted/30">
        <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-6 flex flex-wrap items-center justify-between gap-3 text-xs text-muted-foreground">
          <span>© {new Date().getFullYear()} CrackCMS · {cfg.shortName} microsite</span>
          <span className="flex items-center gap-3">
            <Link href="/exams/cms" className="hover:text-primary">UPSC CMS</Link>
            <span>·</span>
            <Link href="/exams/neet-pg" className="hover:text-primary">NEET PG</Link>
            <span>·</span>
            <Link href="/exams/usmle" className="hover:text-primary">USMLE</Link>
          </span>
        </div>
      </footer>
    </main>
  );
}

function PatternRow({ label, value, accent }: { label: string; value: string; accent?: boolean }) {
  return (
    <div className="flex justify-between items-start gap-3">
      <span className="text-[11px] font-medium uppercase tracking-wider text-muted-foreground shrink-0">
        {label}
      </span>
      <span className={`font-semibold text-right text-sm ${accent ? 'text-rose-500' : ''}`}>
        {value}
      </span>
    </div>
  );
}