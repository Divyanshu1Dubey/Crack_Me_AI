'use client';
import Link from 'next/link';
import { useAuth } from '@/lib/auth';
import {
  Activity,
  BarChart3,
  BookOpen,
  Brain,
  CheckCircle2,
  ChevronRight,
  Clock3,
  FileText,
  GraduationCap,
  ShieldCheck,
  Sparkles,
  Stethoscope,
  Target,
  TrendingUp,
  Users,
} from 'lucide-react';
import BrandMark from '@/components/BrandMark';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';

export default function LandingPage() {
  const { isAuthenticated } = useAuth();

  const features = [
    {
      icon: BookOpen,
      title: 'Clinical PYQ Atlas',
      desc: '1900+ active previous year questions with textbook-linked explanations and high-yield clinical framing.',
      color: 'text-indigo-700 dark:text-indigo-300',
      bg: 'bg-indigo-100 dark:bg-indigo-500/15',
    },
    {
      icon: Brain,
      title: 'Doctor-Grade AI Tutor',
      desc: 'Ask diagnosis, management, pathology, and medicine logic exactly like viva and exam day reasoning.',
      color: 'text-blue-700 dark:text-blue-300',
      bg: 'bg-blue-100 dark:bg-blue-500/15',
    },
    {
      icon: Target,
      title: 'Smart Exam Engine',
      desc: 'Adaptive testing with CMS scoring style, negative marking, and targeted follow-up practice blocks.',
      color: 'text-sky-700 dark:text-sky-300',
      bg: 'bg-sky-100 dark:bg-sky-500/15',
    },
    {
      icon: Sparkles,
      title: 'Rapid Recall AI',
      desc: 'Generate mnemonics and instant one-minute revision capsules for high-yield retention.',
      color: 'text-indigo-700 dark:text-indigo-300',
      bg: 'bg-indigo-100 dark:bg-indigo-500/15',
    },
    {
      icon: BarChart3,
      title: 'Performance Command Center',
      desc: 'Track weak systems, monitor daily streaks, and get guided next-step recommendations.',
      color: 'text-blue-700 dark:text-blue-300',
      bg: 'bg-blue-100 dark:bg-blue-500/15',
    },
    {
      icon: GraduationCap,
      title: 'Full CMS Simulators',
      desc: 'Paper-style mocks with strict timing, review analytics, and practical exam pressure simulation.',
      color: 'text-sky-700 dark:text-sky-300',
      bg: 'bg-sky-100 dark:bg-sky-500/15',
    },
  ];

  const campuses = [
    'AIIMS Delhi',
    'CMC Vellore',
    'JIPMER Puducherry',
    'KGMU Lucknow',
    'Maulana Azad Medical College',
    'Seth GS Medical College',
  ];

  const communityProfiles = [
    { name: 'Riya S.', college: 'AIIMS Delhi', progress: '412 Qs this month' },
    { name: 'Aarav M.', college: 'CMC Vellore', progress: '7-day streak active' },
    { name: 'Nisha K.', college: 'JIPMER Puducherry', progress: 'Top 9% in mocks' },
    { name: 'Harsh V.', college: 'KGMU Lucknow', progress: '58 weak tags resolved' },
  ];

  const stats = [
    { value: '1900+', label: 'Active Questions', icon: FileText },
    { value: '5', label: 'Core Subjects', icon: Stethoscope },
    { value: '47+', label: 'Topic Clusters', icon: Activity },
    { value: '9', label: 'Exam Modes', icon: ShieldCheck },
  ];

  const subjects = [
    'General Medicine', 'Surgery', 'Pediatrics', 'Obstetrics & Gynecology', 'Preventive & Social Medicine'
  ];

  return (
    <div className="min-h-screen bg-transparent">
      {/* Navbar */}
      <nav className="sticky top-0 z-50 border-b border-border/70 bg-background/75 backdrop-blur-xl">
        <div className="mx-auto flex h-16 max-w-6xl items-center justify-between px-4 sm:px-6">
          <BrandMark href="/" compact showTagline={false} />
          <div className="flex items-center gap-3">
            {isAuthenticated ? (
              <Button asChild className="rounded-xl">
                <Link href="/dashboard">Open Dashboard <ChevronRight className="w-4 h-4" /></Link>
              </Button>
            ) : (
              <>
                <Button variant="ghost" asChild className="hidden sm:inline-flex">
                  <Link href="/login">Log in</Link>
                </Button>
                <Button asChild className="rounded-xl">
                  <Link href="/register">Start Free <ChevronRight className="w-4 h-4" /></Link>
                </Button>
              </>
            )}
          </div>
        </div>
      </nav>

      {/* Hero Section */}
      <section className="mx-auto max-w-6xl px-4 pb-20 pt-14 sm:px-6">
        <div className="grid gap-10 lg:grid-cols-12 lg:items-center">
          <div className="lg:col-span-7">
            <Badge variant="secondary" className="mb-5 rounded-full border border-border bg-card px-4 py-1.5 text-xs font-semibold uppercase tracking-[0.11em] text-blue-600 dark:text-blue-400">
              <Sparkles className="w-3.5 h-3.5 mr-1.5" />
                Intelligent Study System
            </Badge>

            <h1 className="text-4xl font-bold leading-[1.02] tracking-tight text-foreground sm:text-5xl lg:text-6xl">
              The Most Powerful & Addictive 
              <span className="gradient-text"> UPSC CMS Prep System</span>
            </h1>

            <p className="mt-6 max-w-2xl text-base leading-relaxed text-muted-foreground sm:text-lg">
              Stop boring lectures. Build consistency with a gamified medical prep operating system: question bank, AI tutor, high-yield revision,
              and analytics that actually make you want to study every day.
            </p>

            <div className="mt-8 flex flex-col items-start gap-3 sm:flex-row sm:items-center">
              <Button size="xl" asChild className="w-full rounded-2xl sm:w-auto">
                <Link href={isAuthenticated ? '/dashboard' : '/register'}>
                  Start Preparing For Free
                  <ChevronRight className="w-5 h-5" />
                </Link>
              </Button>
              <Button size="xl" variant="outline" asChild className="w-full rounded-2xl sm:w-auto">
                <Link href="#features">Explore Platform</Link>
              </Button>
            </div>

            <div className="mt-8 flex flex-wrap gap-2">
              <div className="inline-flex items-center gap-2 rounded-full border border-border bg-card px-3 py-1.5 text-xs font-medium text-muted-foreground">
                <Clock3 className="h-3.5 w-3.5 text-primary" />
                Daily workflow optimized
              </div>
              <div className="inline-flex items-center gap-2 rounded-full border border-border bg-card px-3 py-1.5 text-xs font-medium text-muted-foreground">
                <Target className="h-3.5 w-3.5 text-primary" />
                Exam-style reasoning
              </div>
              <div className="inline-flex items-center gap-2 rounded-full border border-border bg-card px-3 py-1.5 text-xs font-medium text-muted-foreground">
                <TrendingUp className="h-3.5 w-3.5 text-primary" />
                Outcome-focused analytics
              </div>
            </div>
          </div>

          <div className="lg:col-span-5">
            <Card className="relative overflow-hidden rounded-3xl border-0 bg-gradient-to-br from-blue-600 via-indigo-600 to-sky-600 text-white shadow-2xl">
              <div className="absolute -right-14 -top-14 h-40 w-40 rounded-full bg-white/15 blur-2xl" />
              <CardContent className="p-6 sm:p-7">
                <BrandMark light priority />
                <div className="space-y-3">
                  {[
                    { label: 'Today Target', value: '30 question sprint' },
                    { label: 'AI Explanations', value: 'Mnemonics & deep topic dives' },
                    { label: 'Smart Analytics', value: 'Heatmaps & predictive scoring' },
                  ].map((item) => (
                    <div key={item.label} className="rounded-2xl border border-white/20 bg-white/10 p-3 backdrop-blur-sm">
                      <p className="text-[11px] uppercase tracking-[0.1em] text-blue-100">{item.label}</p>
                      <p className="mt-1 text-sm font-semibold">{item.value}</p>
                    </div>
                  ))}
                </div>
                <div className="mt-5 rounded-2xl border border-white/20 bg-slate-950/15 p-4">
                  <div className="flex items-center gap-2 text-[11px] font-semibold uppercase tracking-[0.14em] text-blue-100">
                    <Stethoscope className="h-3.5 w-3.5" />
                    Clinical Exam Cockpit
                  </div>
                  <p className="mt-2 text-sm text-white/88">
                    One place for question practice, mocks, AI explanations, and predictive analytics aligned with the real CMS pattern.
                  </p>
                </div>
              </CardContent>
            </Card>
          </div>
        </div>

        {/* Stats */}
        <div className="mt-12 grid max-w-4xl grid-cols-2 gap-4 md:grid-cols-4">
          {stats.map((stat, i) => (
            <Card key={i} className="text-center shadow-sm">
              <CardContent className="p-5">
                <stat.icon className="mx-auto mb-2 h-5 w-5 text-primary" />
                <div className="text-2xl font-bold text-foreground">{stat.value}</div>
                <div className="text-xs text-muted-foreground mt-1">{stat.label}</div>
              </CardContent>
            </Card>
          ))}
        </div>

        <div className="mt-8 rounded-3xl border border-border bg-card/70 p-5 shadow-sm">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <p className="text-sm font-semibold text-foreground">Campus Community Momentum</p>
              <p className="text-xs text-muted-foreground">Students from leading medical colleges are actively preparing here.</p>
            </div>
            <Badge className="bg-blue-600 text-white hover:bg-blue-600">2,900+ active this week</Badge>
          </div>
          <div className="mt-4 flex flex-wrap gap-2">
            {campuses.map((campus) => (
              <span key={campus} className="rounded-full border border-border bg-muted px-3 py-1 text-xs font-medium text-foreground">
                {campus}
              </span>
            ))}
          </div>
          <div className="mt-4 grid gap-3 md:grid-cols-2">
            {communityProfiles.map((profile) => (
              <div key={profile.name} className="rounded-2xl border border-border bg-background/80 p-3">
                <p className="text-sm font-semibold text-foreground">{profile.name}</p>
                <p className="text-xs text-muted-foreground">{profile.college}</p>
                <p className="mt-1 text-xs font-medium text-blue-700 dark:text-blue-300">{profile.progress}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Features Section */}
      <section id="features" className="bg-muted/35 px-4 py-20 sm:px-6">
        <div className="mx-auto max-w-6xl">
          <div className="text-center mb-12">
            <h2 className="text-3xl font-bold text-foreground mb-3">
              Everything Needed for High-Performance CMS Prep
            </h2>
            <p className="mx-auto max-w-xl text-muted-foreground">
              Built as a complete system, not a collection of random tools.
            </p>
          </div>
          <div className="grid gap-5 md:grid-cols-2 lg:grid-cols-3">
            {features.map((feat, i) => (
              <Card key={i} className="border-border/90 transition-all hover:-translate-y-0.5 hover:shadow-md">
                <CardContent className="p-6">
                  <div className={`mb-4 flex h-11 w-11 items-center justify-center rounded-xl ${feat.bg}`}>
                    <feat.icon className={`h-5 w-5 ${feat.color}`} />
                  </div>
                  <h3 className="text-base font-semibold text-foreground mb-2">{feat.title}</h3>
                  <p className="text-sm text-muted-foreground leading-relaxed">{feat.desc}</p>
                </CardContent>
              </Card>
            ))}
          </div>
        </div>
      </section>

      {/* Subjects Section */}
      <section className="px-4 py-20 sm:px-6">
        <div className="mx-auto max-w-4xl">
          <div className="text-center mb-10">
            <h2 className="text-3xl font-bold text-foreground mb-3">All 5 UPSC CMS Subjects</h2>
            <p className="text-muted-foreground">Paper 1 + Paper 2 complete coverage with structured depth</p>
          </div>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {subjects.map((s, i) => (
              <Card key={i} className="transition-colors hover:border-primary/30">
                <CardContent className="p-5 flex items-center gap-3">
                  <CheckCircle2 className="w-5 h-5 text-blue-500 shrink-0" />
                  <span className="font-medium text-foreground">{s}</span>
                </CardContent>
              </Card>
            ))}
            <Card className="hover:border-primary/30 transition-colors">
              <CardContent className="p-5 flex items-center gap-3">
                <CheckCircle2 className="w-5 h-5 text-blue-500 shrink-0" />
                <span className="font-medium text-foreground">AI-Powered Analysis</span>
              </CardContent>
            </Card>
          </div>
        </div>
      </section>

      {/* Why CrackCMS Section */}
      <section className="bg-muted/35 px-4 py-20 sm:px-6">
        <div className="mx-auto max-w-4xl">
          <div className="text-center mb-10">
            <h2 className="text-3xl font-bold text-foreground mb-3">Why This Feels Like a Real System</h2>
          </div>
          <div className="grid md:grid-cols-3 gap-6">
            {[
              { icon: Clock3, title: 'Workflow-First', desc: 'The platform is organized around what to do now, next, and after-review.' },
              { icon: Users, title: 'Doctor-Centric', desc: 'Language and features align with medical preparation, not generic exam templates.' },
              { icon: TrendingUp, title: 'Continuous Improvement', desc: 'Data-backed recommendations keep narrowing your weakest clinical domains.' },
            ].map((item, i) => (
              <div key={i} className="text-center">
                <div className="w-12 h-12 rounded-xl flex items-center justify-center mx-auto mb-4 bg-primary/10">
                  <item.icon className="w-6 h-6 text-primary" />
                </div>
                <h3 className="font-semibold text-foreground mb-2">{item.title}</h3>
                <p className="text-sm text-muted-foreground leading-relaxed">{item.desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* CTA Section */}
      <section className="px-4 py-20 sm:px-6">
        <Card className="mx-auto max-w-3xl border-primary/20 bg-primary/[0.04]">
          <CardContent className="p-10 md:p-14 text-center">
            <GraduationCap className="w-10 h-10 mx-auto mb-4 text-primary" />
            <h2 className="text-2xl md:text-3xl font-bold text-foreground mb-3">
              Ready to Build an Exam-Ready Routine?
            </h2>
            <p className="text-muted-foreground mb-8 max-w-lg mx-auto">
              Join aspirants using an AI + doctor workflow to prepare faster, cleaner, and with better retention.
            </p>
            <Button size="xl" asChild className="rounded-2xl">
              <Link href={isAuthenticated ? '/dashboard' : '/register'}>
                Get Started Free <ChevronRight className="w-5 h-5" />
              </Link>
            </Button>
          </CardContent>
        </Card>
      </section>

      {/* Footer */}
      <footer className="border-t border-border/70 px-4 py-8 sm:px-6">
        <div className="mx-auto flex max-w-6xl flex-col items-center justify-between gap-4 sm:flex-row">
          <BrandMark href="/" compact showTagline={false} />
          <p className="text-sm text-muted-foreground">© 2026 CrackCMS | AI-powered UPSC CMS preparation platform</p>
        </div>
      </footer>
    </div>
  );
}
