'use client';

import { useState, useEffect } from 'react';
import Image from 'next/image';
import Link from 'next/link';
import { useAuth } from '@/lib/auth';
import {
  Activity, Brain, CheckCircle2, ChevronRight, Clock3, FileText,
  GraduationCap, ShieldCheck, Sparkles, Stethoscope, Target,
  TrendingUp, Users, Zap, RotateCw, Flame, Award, ArrowRight,
  Crown, Loader2, ArrowUpRight, BarChart3
} from 'lucide-react';
import BrandMark from '@/components/BrandMark';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { siteName } from '@/lib/seo';
import ExamCountdown from '@/components/ExamCountdown';

const ThemeToggle = dynamic(() => import('@/components/ThemeToggle'), {
  ssr: false,
  loading: () => <div className="h-9 w-9 rounded-xl border border-border/70 bg-muted/60" aria-hidden="true" />,
});

const MagicBento = dynamic(() => import('@/components/ui/MagicBento'), { ssr: false });

function dynamic<T extends object>(importFn: () => Promise<{ default: React.ComponentType<T> }>, opts: { ssr: boolean; loading: React.ReactNode }): React.ComponentType<T> {
  // @ts-ignore - type hack for this file
  return undefined as any;
}

const siteUrl = process.env.NEXT_PUBLIC_SITE_URL || 'https://www.cracklabs.app';

export default function LandingPage() {
  const { isAuthenticated, user } = useAuth();

  // ─── Interactive Widget: PYQ Atlas ───────────────────────────────────────
  const [pyqAnswer, setPyqAnswer] = useState<string | null>(null);
  const [showPyqExplanation, setShowPyqExplanation] = useState(false);
  const [pyqAiLoading, setPyqAiLoading] = useState(false);
  const [pyqAiDone, setPyqAiDone] = useState(false);

  // ─── Interactive Widget: AI Tutor ────────────────────────────────────────
  const [activeTutorTopic, setActiveTutorTopic] = useState<'ra' | 'se' | 'as'>('ra');
  const tutorConversations = {
    ra: {
      question: "What are the core diagnostic criteria for Rheumatoid Arthritis?",
      reply: "According to the standard **ACR/EULAR classification**, Rheumatoid Arthritis requires a score of **≥ 6/10 points** across four clinical domains:\n\n* **Joint Involvement**: Up to 5 points (based on number/size of active small joints).\n* **Serology**: Up to 3 points (RF or anti-CCP antibodies).\n* **Acute Phase Reactants**: 1 point (elevated CRP or ESR).\n* **Duration**: 1 point (symptoms persisting for ≥ 6 weeks)."
    },
    se: {
      question: "What is the initial drug of choice for status epilepticus?",
      reply: "The gold standard initial pharmacological intervention for Status Epilepticus is an **intravenous Benzodiazepine**:\n\n* **First-line**: IV **Lorazepam** (4 mg given slowly over 2 mins) due to its sustained brain half-life.\n* **Alternative**: IV Diazepam or IM Midazolam (if IV access is not yet secured).\n* **Follow-up**: Always initiate a long-acting anticonvulsant (like **Levetiracetam** or **Fosphenytoin**) immediately after to prevent recurrence."
    },
    as: {
      question: "Describe the classic murmur of Aortic Stenosis.",
      reply: "Aortic Stenosis is characterized by a distinctive cardiac murmur:\n\n* **Type**: **Crescendo-decrescendo** systolic ejection murmur.\n* **Location**: Best heard at the **right second intercostal space** (aortic area).\n* **Radiation**: Classically radiates bilaterally to the **carotid arteries**.\n* **High-Yield Signs**: Associated with a delayed carotid pulse (*pulsus parvus et tardus*) and a soft or absent second heart sound (S2)."
    }
  };

  // ─── Interactive Widget: Exam Timer ──────────────────────────────────────
  const [examTimer, setExamTimer] = useState(6291);
  const [examSelectedOption, setExamSelectedOption] = useState<string | null>(null);

  useEffect(() => {
    const interval = setInterval(() => {
      setExamTimer((prev) => (prev > 0 ? prev - 1 : 7200));
    }, 1000);
    return () => clearInterval(interval);
  }, []);

  const formatTimer = (seconds: number) => {
    const h = Math.floor(seconds / 3600);
    const m = Math.floor((seconds % 3600) / 60);
    const s = seconds % 60;
    return `${h.toString().padStart(2, '0')}:${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`;
  };

  // ─── Interactive Widget: Flashcards ──────────────────────────────────────
  const [flippedCard, setFlippedCard] = useState<number | null>(null);
  const mnemonicCards = [
    {
      id: 1, title: "CREST Syndrome", subtitle: "Limited Scleroderma",
      front: "Tap card to reveal mnemonic",
      back: [
        { letter: "C", text: "Calcinosis cutis (calcium deposits)" },
        { letter: "R", text: "Raynaud's phenomenon (vascular spasm)" },
        { letter: "E", text: "Esophageal dysmotility" },
        { letter: "S", text: "Sclerodactyly (tight skin on fingers)" },
        { letter: "T", text: "Telangiectasia (dilated capillaries)" },
      ]
    },
    {
      id: 2, title: "Charcot's Triad", subtitle: "Acute Cholangitis",
      front: "Tap card to reveal mnemonic",
      back: [
        { letter: "J", text: "Jaundice (biliary obstruction)" },
        { letter: "F", text: "Fever with chills (active infection)" },
        { letter: "P", text: "Pain in Right Upper Quadrant (RUQ)" },
      ]
    },
    {
      id: 3, title: "Beck's Triad", subtitle: "Cardiac Tamponade",
      front: "Tap card to reveal mnemonic",
      back: [
        { letter: "H", text: "Hypotension (restricted stroke volume)" },
        { letter: "J", text: "Jugular Venous Distension" },
        { letter: "M", text: "Muffled / Distant Heart Sounds" },
      ]
    }
  ];

  // ─── Social proof data ───────────────────────────────────────────────────
  const communityProfiles = [
    { name: 'Dr. Riya Sharma', college: 'AIIMS Delhi', progress: '412 Clinical Qs this month', badge: 'Active Streak' },
    { name: 'Dr. Aarav Mehta', college: 'CMC Vellore', progress: 'Daily streak — 14 days', badge: 'Top Reviewer' },
    { name: 'Dr. Nisha Krishnan', college: 'JIPMER Puducherry', progress: 'Top 9% in mock simulation', badge: 'Mock Champion' },
    { name: 'Dr. Harsh Vardhan', college: 'KGMU Lucknow', progress: '58 weak tags resolved', badge: 'High Yield Master' },
  ];

  const stats = [
    { value: '2000+', label: 'Verified PYQs', icon: FileText, desc: 'UPSC CMS 2018-2025' },
    { value: '5', label: 'Core Subjects', icon: Stethoscope, desc: 'Paper 1 & Paper 2' },
    { value: '47+', label: 'Topic Clusters', icon: Activity, desc: 'High-yield medical focus' },
    { value: '9', label: 'Exam Modes', icon: ShieldCheck, desc: 'Drills to full simulation' },
  ];

  // ─── Structured data ─────────────────────────────────────────────────────
  const faqSchema = {
    '@type': 'FAQPage',
    mainEntity: [
      { '@type': 'Question', name: 'Is CrackCMS useful for UPSC CMS preparation?', acceptedAnswer: { '@type': 'Answer', text: 'Yes. CrackCMS focuses on UPSC CMS pattern practice with PYQs, timed mocks, and clinical reasoning workflows.' } },
      { '@type': 'Question', name: 'Can NEET PG aspirants use CrackCMS?', acceptedAnswer: { '@type': 'Answer', text: 'Yes. Subject-wise high-yield practice, AI explanations, and analytics are valuable for NEET PG revision too.' } },
      { '@type': 'Question', name: 'Does CrackCMS include mock tests for CMS?', acceptedAnswer: { '@type': 'Answer', text: 'Yes. Full exam-style simulators with timing and analysis are included for CMS exam readiness.' } },
    ],
  };

  const renderHtml = (raw: string) => {
    const escapeHtml = (v: string) => v.replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;').replace(/'/g,'&#39;').replace(/&/g,'&amp;');
    const parts = raw.split(/\*\*(.*?)\*\*/g);
    return parts.map((p, i) => (i % 2 === 1 ? `<strong>${p}</strong>` : escapeHtml(p))).join('');
  };

  return (
    <div className="min-h-screen bg-transparent font-sans">
      {/* Structured Data */}
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify({
        '@context': 'https://schema.org', '@graph': [
          { '@type': 'Organization', name: siteName, url: siteUrl, logo: `${siteUrl}/cms-circle-logo.png`, description: 'Doctor-first UPSC CMS and NEET PG preparation platform.' },
          { '@type': 'WebSite', name: siteName, url: siteUrl, potentialAction: { '@type': 'SearchAction', target: `${siteUrl}/questions?search={search_term_string}`, 'query-input': 'required name=search_term_string' } },
          faqSchema,
        ]
      }) }} />

      <ExamCountdown />

      {/* ═══════════════════════════════════════════════════════════════════════
          SECTION 1 — HERO + EXAM MICROSITES
          Top queries: "upsc cms" (1,263 imp), "upsc cms mock test", "neet pg",
          comparisons (vs-neet-pg: 15k imp), cutoff pages (2,900+ imp each).
          Exam microsites are the primary conversion funnel.
      ═══════════════════════════════════════════════════════════════════════ */}
      <section className="relative overflow-hidden">
        {/* Navbar */}
        <nav className="sticky top-0 z-50 border-b border-border/60 bg-background/80 backdrop-blur-xl">
          <div className="mx-auto flex h-16 max-w-6xl items-center justify-between px-4 sm:px-6">
            <BrandMark href="/" compact showTagline={false} />
            <div className="flex items-center gap-3">
              <ThemeToggle />
              {isAuthenticated ? (
                <Button asChild className="rounded-xl font-semibold shadow-sm shadow-primary/10">
                  <Link href="/dashboard">Open Dashboard <ChevronRight className="ml-1 w-4 h-4" /></Link>
                </Button>
              ) : (
                <>
                  <Button variant="ghost" asChild className="hidden sm:inline-flex font-medium text-muted-foreground hover:text-foreground">
                    <Link href="/login">Log in</Link>
                  </Button>
                  <Button asChild className="rounded-xl font-semibold shadow-md shadow-primary/15 transition-transform active:scale-95">
                    <Link href="/register">Start Free <ChevronRight className="ml-1 w-4 h-4" /></Link>
                  </Button>
                </>
              )}
            </div>
          </div>
        </nav>

        {/* Hero */}
        <section className="relative isolate overflow-hidden py-20 sm:py-28 lg:py-32">
          {/* Animated background effects */}
          <div className="hero-grid-bg" aria-hidden="true" />
          <div className="orb orb-1" aria-hidden="true" />
          <div className="orb orb-2" aria-hidden="true" />
          <div className="orb orb-3" aria-hidden="true" />

          <div className="relative z-10 mx-auto max-w-6xl px-4 pb-10 pt-12 sm:px-6">
            <div className="max-w-3xl mx-auto text-center space-y-5">
              {/* Live indicator */}
              <div className="mb-5 inline-flex items-center gap-2 rounded-full border border-primary/25 bg-primary/5 px-4 py-1.5">
                <span className="relative flex h-2 w-2">
                  <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75" />
                  <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-500" />
                </span>
                <span className="text-xs font-semibold text-primary tracking-wide">2,000+ PYQ Questions • AI-Powered Prep</span>
              </div>

              <h1 className="font-display text-4xl font-extrabold leading-[1.08] tracking-tight text-foreground sm:text-5xl lg:text-6xl">
                <span className="bg-linear-to-r from-amber-500 via-pink-500 to-violet-600 bg-clip-text text-transparent dark:from-amber-300 dark:via-pink-300 dark:to-violet-300">AI Powered</span>{' '}
                <span className="text-foreground">UPSC CMS Platform</span>
              </h1>

              <p className="text-base leading-relaxed text-foreground/80 sm:text-lg max-w-2xl mx-auto">
                Build daily clinical consistency with an integrated medical prep operating system.
                Smart question bank, AI tutoring, hyper-realistic mock tests, and weak-area analytics.
              </p>

              <div className="flex flex-col items-center gap-3 sm:flex-row sm:items-center sm:justify-center pt-1">
                <Button asChild size="xl" className="w-full rounded-2xl sm:w-auto font-semibold text-white shadow-lg shadow-fuchsia-500/30 transition-all hover:scale-[1.02] active:scale-[0.98] btn-shimmer" style={{ backgroundImage: 'linear-gradient(90deg, #f59e0b 0%, #ec4899 50%, #7c3aed 100%)', backgroundSize: '200% 100%' }}>
                  <Link href={isAuthenticated ? '/dashboard' : '/register'}>Start Preparing <ChevronRight className="ml-1.5 w-5 h-5" /></Link>
                </Button>
                <Button variant="glass" size="xl" asChild className="w-full rounded-2xl sm:w-auto font-semibold">
                  <Link href="#features">Explore Features</Link>
                </Button>
              </div>

              {/* Pill tags */}
              <div className="flex flex-wrap justify-center gap-2 pt-4">
                {[
                  { icon: Clock3, label: 'Daily workflow optimized', color: 'text-blue-500' },
                  { icon: Target, label: 'Exam-style reasoning', color: 'text-teal-500' },
                  { icon: TrendingUp, label: 'Outcome-focused analytics', color: 'text-indigo-500' },
                ].map((pill, i) => (
                  <span key={i} className="inline-flex items-center gap-2 rounded-full border border-border bg-card/95 px-4 py-2 text-xs font-semibold text-foreground shadow-sm">
                    <pill.icon className={`h-4 w-4 ${pill.color}`} />{pill.label}
                  </span>
                ))}
              </div>
            </div>
          </div>
        </section>

        {/* Exam Microsites — high-impression entry points (15k+ for vs-neet-pg) */}
        <div className="mx-auto max-w-6xl px-4 pb-16 sm:px-6">
          <div className="text-center mb-8 space-y-2">
            <h2 className="font-display text-2xl font-extrabold text-foreground tracking-tight sm:text-3xl">Pick your exam microsite</h2>
            <p className="text-sm text-muted-foreground max-w-xl mx-auto">Each exam gets its own dedicated experience — different subjects, PYQs, and mocks — but the same AI tutor and analytics.</p>
          </div>
          <div className="grid sm:grid-cols-2 lg:grid-cols-5 gap-4">
            {[
              { href: '/exams/cms', badge: 'UPSC', name: 'UPSC CMS', desc: '2,000+ PYQs 2018-2025. Paper I + II.', gradient: 'from-cyan-600 to-blue-700', icon: '🩺' },
              { href: '/neet-pg', badge: 'NEET PG', name: 'NEET PG', desc: '1,200+ PYQs across 19 subjects (2020-2025).', gradient: 'from-emerald-600 to-teal-700', icon: '🎓' },
              { href: '/inicet', badge: 'INI-CET', name: 'INI-CET', desc: 'May + November sessions. AIIMS/PGI/JIPMER prep.', gradient: 'from-violet-600 to-purple-700', icon: '🏥' },
              { href: '/fmge', badge: 'FMGE', name: 'FMGE / NEXT', desc: 'Screening test + NEXT pattern practice.', gradient: 'from-amber-600 to-orange-700', icon: '📋' },
              { href: '/usmle', badge: 'USMLE', name: 'USMLE', desc: 'Step 1 + Step 2 CK. Beta access — join waitlist.', gradient: 'from-indigo-600 to-violet-700', icon: '🌎' },
            ].map((c) => (
              <Link key={c.href} href={c.href} className="group rounded-2xl border border-border/60 bg-card/80 overflow-hidden transition-all hover:-translate-y-1 exam-card-3d">
                <div className={`bg-linear-to-br ${c.gradient} text-white p-5`}>
                  <div className="flex items-center justify-between mb-2">
                    <Badge className="bg-white/15 text-white border border-white/20 backdrop-blur-sm text-[10px]">{c.badge}</Badge>
                    <span className="text-2xl">{c.icon}</span>
                  </div>
                  <h3 className="text-lg font-extrabold">{c.name}</h3>
                </div>
                <div className="p-4">
                  <p className="text-xs text-muted-foreground leading-relaxed min-h-[3rem]">{c.desc}</p>
                  <div className="mt-2 flex items-center text-xs font-semibold text-primary group-hover:gap-2 transition-all">
                    Open <ArrowUpRight className="ml-1 w-3.5 h-3.5" />
                  </div>
                </div>
              </Link>
            ))}
          </div>
        </div>
      </section>

      {/* ═══════════════════════════════════════════════════════════════════════
          SECTION 2 — PLATFORM FEATURES (condensed from 4 deep-dives)
      ═══════════════════════════════════════════════════════════════════════ */}
      <section id="features" className="border-t border-border/60 bg-muted/20 py-20 px-4 sm:px-6">
        <div className="mx-auto max-w-6xl space-y-12">
          <div className="text-center max-w-2xl mx-auto space-y-3">
            <h2 className="font-display text-3xl font-extrabold text-foreground sm:text-4xl tracking-tight">Everything for High-Performance CMS Prep</h2>
            <p className="text-muted-foreground">Six specialized engines. One seamless workflow.</p>
            <div className="h-1.5 w-16 bg-blue-500 rounded-full mx-auto" />
          </div>

          {/* MagicBento interactive overview */}
          <MagicBento
            textAutoHide
            enableStars
            enableSpotlight
            enableBorderGlow
            enableTilt
            enableMagnetism
            clickEffect
            spotlightRadius={300}
            particleCount={10}
            glowColor="132,0,255"
            cards={[
              { color: '#120F17', title: 'UPSC CMS QBank', description: '3,300+ authentic PYQs with AI-grounded explanations.', label: 'UPSC CMS' },
              { color: '#120F17', title: 'NEET PG Clinical Bank', description: 'Subject-wise high-yield practice with image-based questions.', label: 'NEET PG' },
              { color: '#120F17', title: 'AI Tutor Assistant', description: 'Multi-model AI grounded in 79 textbook chapters.', label: 'AI Tutor' },
              { color: '#120F17', title: 'Adaptive Mock Tests', description: 'Timed engine simulating NBE and UPSC test environments.', label: 'Mock Tests' },
              { color: '#120F17', title: 'Rapid Recall Flashcards', description: 'SM-2 algorithm for high-yield clinical memory retention.', label: 'Recall' },
              { color: '#120F17', title: 'Performance Analytics', description: 'Granular weak-area identification and rank predictions.', label: 'Analytics' },
            ]}
          />

          {/* Compact 3-card feature strip */}
          <div className="grid md:grid-cols-3 gap-4">
            {[
              {
                badge: '2000+ PYQs',
                badgeColor: 'text-emerald-600',
                title: 'Clinical PYQ Atlas',
                desc: 'Every question indexed by subject, topic, and difficulty. Keyboard shortcuts, voter-consensus answers, and textbook cross-references.',
                color: 'emerald',
              },
              {
                badge: 'Multi-model AI',
                badgeColor: 'text-blue-600',
                title: 'Doctor-Grade AI Tutor',
                desc: 'RAG-grounded responses from Harrison, Robbins, and standard clinical references. Socratic, Viva, and High-Yield modes.',
                color: 'blue',
              },
              {
                badge: 'SM-2 Algorithm',
                badgeColor: 'text-amber-600',
                title: 'Smart Exam Engine + Recall',
                desc: 'Timed mock tests with negative marking (+1 / -0.33). Adaptive flashcards with spaced repetition schedules.',
                color: 'amber',
              },
            ].map((feat, i) => (
              <div key={i} className={`rounded-2xl border border-${feat.color}-500/20 bg-${feat.color}-500/2 p-5 shadow-sm hover:border-${feat.color}-500/35 transition-all`}>
                <span className={`text-[10px] font-extrabold uppercase tracking-widest ${feat.badgeColor}`}>{feat.badge}</span>
                <h3 className="font-display text-lg font-extrabold text-foreground mt-1">{feat.title}</h3>
                <p className="text-xs text-muted-foreground mt-2 leading-relaxed">{feat.desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ═══════════════════════════════════════════════════════════════════════
          SECTION 3 — STATS + SOCIAL PROOF (testimonials + campus + cockpit)
      ═══════════════════════════════════════════════════════════════════════ */}
      <section className="border-t border-border/60 px-4 py-20 sm:px-6">
        <div className="mx-auto max-w-6xl space-y-16">
          {/* Stats strip */}
          <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
            {stats.map((stat, i) => (
              <div key={i} className="stat-card-glow flex flex-col items-center text-center p-6 rounded-2xl border border-border/60 bg-card/80 cursor-default">
                <div className="h-11 w-11 rounded-xl bg-primary/10 flex items-center justify-center mb-3 relative">
                  <stat.icon className="h-5 w-5 text-primary relative z-10" />
                  <div className="absolute inset-0 rounded-xl bg-primary/5 animate-pulse" />
                </div>
                <span className="text-3xl font-extrabold text-foreground tracking-tight gradient-text">{stat.value}</span>
                <span className="text-sm font-bold text-foreground mt-1">{stat.label}</span>
                <span className="text-xs text-muted-foreground">{stat.desc}</span>
              </div>
            ))}
          </div>

          {/* Testimonials */}
          <div className="space-y-6">
            <div className="text-center space-y-2">
              <Badge className="bg-primary/10 text-primary hover:bg-primary/15 border-0 font-bold uppercase tracking-wider text-[10px]">Aspirant Reviews</Badge>
              <h2 className="font-display text-2xl font-extrabold text-foreground sm:text-4xl tracking-tight">Loved by medical students preparing for UPSC CMS</h2>
            </div>
            <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
              {[
                { quote: "The Spaced Repetition flashcards and AI explanations are elite. I memorized complex drug interactions in days rather than weeks.", title: "Verified PG Resident", inst: "AIIMS Delhi" },
                { quote: "Unlimited AI tutor support is a game-changer. The explanations break down the 'why' behind each option. Significantly improved my diagnostics.", title: "Verified MBBS Intern", inst: "MAMC" },
                { quote: "The QBank is extremely clean — exactly 240 questions per year. No duplicates, no missing options, beautifully formatted.", title: "Verified Medical Officer Track", inst: "KGMU Lucknow" },
                { quote: "The ₹199 price is a steal. Unlimited AI tutoring, textbook page mapping, and revision sheets. Easily replaces multiple subscriptions.", title: "Verified Aspirant", inst: "CMC Vellore" },
                { quote: "Mock simulations feel incredibly close to actual exam software. My score estimates went from 55% to 74% in two weeks.", title: "Verified Resident Doctor", inst: "JIPMER Puducherry" },
                { quote: "Requested textbook mapping for pediatric guidelines — added within hours. The curated notes are super high yield.", title: "Verified MO Aspirant", inst: "Seth GS Medical College" },
              ].map((item, idx) => (
                <div key={idx} className="glass-card p-5 border border-border/60 hover:border-primary/20 transition-all duration-300 relative bg-slate-900/40" style={{ backdropFilter: 'blur(12px)' }}>
                  <div className="flex gap-1 text-amber-500 mb-3">
                    {Array.from({ length: 5 }).map((_, i) => (
                      <svg key={i} className="w-3.5 h-3.5 fill-current text-amber-400" viewBox="0 0 20 20"><path d="M9.049 2.927c.3-.921 1.603-.921 1.902 0l1.07 3.292a1 1 0 00.95.69h3.462c.969 0 1.371 1.24.588 1.81l-2.8 2.034a1 1 0 00-.364 1.118l1.07 3.292c.3.921-.755 1.688-1.54 1.118l-2.8-2.034a1 1 0 00-1.175 0l-2.8 2.034c-.784.57-1.838-.197-1.539-1.118l1.07-3.292a1 1 0 00-.364-1.118L2.98 8.72c-.783-.57-.38-1.81.588-1.81h3.461a1 1 0 00.951-.69l1.07-3.292z" /></svg>
                    ))}
                  </div>
                  <p className="text-xs text-slate-300 leading-relaxed italic">"{item.quote}"</p>
                  <div className="border-t border-slate-800/60 mt-3 pt-2.5 flex items-center gap-2.5">
                    <div className="w-7 h-7 rounded-full bg-primary/10 flex items-center justify-center font-bold text-[10px] text-primary">&#x2695;</div>
                    <div>
                      <h4 className="text-xs font-bold text-white">{item.title}</h4>
                      <p className="text-[10px] text-muted-foreground">{item.inst}</p>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Campus + Cockpit in one row */}
          <div className="grid lg:grid-cols-2 gap-5">
            {/* Campus Momentum */}
            <div className="rounded-2xl border border-border/60 bg-card/60 p-5 space-y-4">
              <div className="flex items-center justify-between">
                <div>
                  <h3 className="font-display text-lg font-extrabold text-foreground">Campus Momentum</h3>
                  <p className="text-[11px] text-muted-foreground">Doctors from top institutions prep here daily.</p>
                </div>
                <Badge className="bg-emerald-600 text-white hover:bg-emerald-600 text-[10px]">2,900+ active</Badge>
              </div>
              <div className="flex flex-wrap gap-2">
                {['AIIMS Delhi','CMC Vellore','JIPMER Puducherry','KGMU Lucknow','MAMC','Seth GS'].map((c) => (
                  <span key={c} className="rounded-lg border border-border/50 bg-muted/20 px-2.5 py-1 text-[10px] font-semibold text-foreground">{c}</span>
                ))}
              </div>
              <div className="space-y-2">
                {communityProfiles.map((p) => (
                  <div key={p.name} className="flex items-center justify-between rounded-xl border border-border/40 bg-muted/10 px-3 py-2">
                    <div>
                      <span className="text-xs font-extrabold text-foreground">{p.name}</span>
                      <span className="text-[10px] text-muted-foreground ml-2">{p.college}</span>
                    </div>
                    <div className="flex items-center gap-1.5">
                      <span className="h-1.5 w-1.5 rounded-full bg-emerald-500 animate-pulse" />
                      <span className="text-[10px] font-semibold text-emerald-600">{p.badge}</span>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* Study Cockpit */}
            <Card className="relative overflow-hidden rounded-2xl border border-border/60 bg-card/90 shadow-lg">
              <div className="flex items-center justify-between border-b border-border/50 bg-muted/30 px-4 py-2.5">
                <div className="flex items-center gap-1.5">
                  <div className="h-2.5 w-2.5 rounded-full bg-red-400/80" />
                  <div className="h-2.5 w-2.5 rounded-full bg-amber-400/80" />
                  <div className="h-2.5 w-2.5 rounded-full bg-emerald-400/80" />
                </div>
                <div className="flex items-center gap-1.5 text-[10px] font-bold text-muted-foreground tracking-wider uppercase">
                  <span className="inline-block h-1.5 w-1.5 rounded-full bg-emerald-500 animate-pulse" />
                  System Cockpit Live
                </div>
              </div>
              <CardContent className="p-4 space-y-3">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2.5">
                    <div className="h-9 w-9 rounded-lg bg-blue-500/10 flex items-center justify-center">
                      <Stethoscope className="h-4.5 w-4.5 text-blue-500" />
                    </div>
                    <div>
                      <h3 className="text-sm font-bold text-foreground">
                        {isAuthenticated && user ? (user.first_name ? `${user.first_name} ${user.last_name || ''}` : user.username) : "Dr. Sarah Jenkins"}
                      </h3>
                      <p className="text-[11px] text-muted-foreground">
                        {isAuthenticated && user ? (user.college || "Medical Specialist") : "General Medicine Track"}
                      </p>
                    </div>
                    <Badge className="bg-blue-500/10 text-blue-600 dark:text-blue-400 border-0 text-[10px]">
                      {isAuthenticated && user ? (user.is_subscribed ? 'Premium' : 'Aspirant') : 'Aspirant'}
                    </Badge>
                  </div>
                  <div className="flex gap-3">
                    <div className="rounded-lg border border-border/40 bg-muted/15 px-3 py-1.5">
                      <p className="text-[9px] uppercase font-bold text-muted-foreground">Streak</p>
                      <p className="text-xs font-extrabold">{isAuthenticated && user ? "1 Day" : "12 Days"}</p>
                    </div>
                    <div className="rounded-lg border border-border/40 bg-muted/15 px-3 py-1.5">
                      <p className="text-[9px] uppercase font-bold text-muted-foreground">Est. Score</p>
                      <p className="text-xs font-extrabold">{isAuthenticated && user ? "74.5%" : "68.5%"}</p>
                    </div>
                  </div>
                </div>
                <div className="space-y-1 bg-muted/20 p-3 rounded-xl border border-border/40">
                  <div className="flex justify-between text-xs font-bold text-foreground">
                    <span>Clinical Prep Progress</span>
                    <span className="text-blue-600">74% Target</span>
                  </div>
                  <div className="h-2 w-full bg-border/50 rounded-full overflow-hidden">
                    <div className="h-full bg-linear-to-r from-blue-500 to-indigo-600 rounded-full" style={{ width: '74%' }} />
                  </div>
                </div>
              </CardContent>
            </Card>
          </div>
        </div>
      </section>

      {/* ═══════════════════════════════════════════════════════════════════════
          SECTION 4 — PREMIUM PRICING
      ═══════════════════════════════════════════════════════════════════════ */}
      <section className="px-4 py-16 sm:px-6">
        <div className="mx-auto max-w-5xl rounded-[2rem] border border-amber-500/20 bg-slate-950 text-white relative overflow-hidden shadow-2xl">
          <div className="absolute right-0 top-0 h-[350px] w-[350px] rounded-full bg-linear-to-br from-amber-500/10 to-yellow-500/15 blur-3xl opacity-60 pointer-events-none" />
          <div className="absolute left-0 bottom-0 h-[350px] w-[350px] rounded-full bg-linear-to-tr from-cyan-500/10 to-blue-500/15 blur-3xl opacity-60 pointer-events-none" />

          <div className="mx-auto max-w-5xl relative z-10 p-8 sm:p-12 md:p-16">
            <div className="grid gap-10 lg:grid-cols-2 items-center">
              <div className="space-y-5">
                <Badge className="bg-amber-500/15 text-amber-400 hover:bg-amber-500/20 border border-amber-500/30 font-bold uppercase tracking-wider text-[10px]">
                  <Crown className="w-3.5 h-3.5 mr-1 inline" /> Early Bird Special Pass
                </Badge>
                <h2 className="font-display text-3xl font-black md:text-4xl text-white tracking-tight leading-tight">
                  One Place for Complete UPSC CMS &amp; NEET PG
                </h2>
                <p className="text-slate-400 text-sm leading-relaxed">Unlock unlimited AI tutor usage, hand-notes, faculty doubt support, and the full QBank + simulations.</p>
                <div className="grid gap-3 sm:grid-cols-2 pt-1">
                  {[
                    { t: 'Unlimited AI Tutor', d: 'No token limits. Full clinical analyses and mnemonics.' },
                    { t: 'Hand-notes', d: 'High-yield revision summaries, flowcharts, and cheat sheets.' },
                    { t: 'Faculty Doubts', d: 'Direct channel with state and national experts.' },
                    { t: 'Full QBank + Sims', d: '1,440+ verified PYQs (2018-2025) and custom mocks.' },
                  ].map((item, i) => (
                    <div key={i} className="flex gap-2.5">
                      <CheckCircle2 className="h-4.5 w-4.5 text-amber-500 shrink-0 mt-0.5" />
                      <div>
                        <h4 className="font-bold text-xs text-slate-200">{item.t}</h4>
                        <p className="text-[11px] text-slate-400 mt-0.5 leading-relaxed">{item.d}</p>
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              <div className="flex justify-center">
                <div className="w-full max-w-sm rounded-3xl border border-amber-500/30 bg-slate-900/60 p-7 text-center backdrop-blur-md relative overflow-hidden">
                  <div className="absolute top-0 right-0 w-24 h-24 bg-amber-500/10 rounded-full blur-2xl pointer-events-none" />
                  <span className="text-xs font-bold text-amber-400 uppercase tracking-widest">Premium Pass</span>
                  <div className="mt-4 flex items-baseline justify-center gap-2">
                    <span className="text-5xl font-black text-white">₹199</span>
                    <span className="text-lg line-through text-slate-500">₹10,000</span>
                  </div>
                  <p className="text-[10px] text-amber-400/90 font-bold mt-1 tracking-wide">98% Launch Offer — Rising Soon</p>
                  <ul className="mt-5 space-y-2.5 text-left text-xs text-slate-300 border-t border-slate-800 pt-5">
                    {['Unlimited AI tutor (no tokens)','Handwritten study materials','Faculty doubt support','All reference books & guides'].map((li, i) => (
                      <li key={i} className="flex items-center gap-2"><Zap className="w-3.5 h-3.5 text-amber-500" /> {li}</li>
                    ))}
                  </ul>
                  <Button size="xl" asChild className="w-full mt-6 rounded-2xl bg-linear-to-r from-amber-500 to-yellow-500 hover:from-amber-600 hover:to-yellow-600 text-black font-extrabold shadow-lg shadow-amber-500/20 py-3.5 transition-transform active:scale-95">
                    <Link href="/subscription">Claim Offer Now <ArrowRight className="w-4 h-4 ml-1" /></Link>
                  </Button>
                  <span className="block text-[9px] text-slate-500 mt-2.5">Secure via Razorpay. Cancel anytime.</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* ═══════════════════════════════════════════════════════════════════════
          SECTION 5 — COMPARISON PAGES + FINAL CTA
          High-impression pages: cms/vs-neet-pg (15k+), neet-pg/vs-usmle, etc.
          Drive SEO value + internal linking.
      ═══════════════════════════════════════════════════════════════════════ */}
      <section className="px-4 py-16 sm:px-6 border-t border-border/60 bg-muted/20">
        <div className="mx-auto max-w-6xl space-y-12">
          {/* Comparison grid */}
          <div className="text-center mb-8 space-y-2">
            <Badge variant="outline" className="border-primary/30 text-primary text-[10px]">Compare Exams</Badge>
            <h2 className="font-display text-2xl font-extrabold text-foreground sm:text-3xl tracking-tight">Which exam fits your career path?</h2>
            <p className="text-sm text-muted-foreground max-w-xl mx-auto">Informed comparisons across UPSC CMS, NEET PG, INI-CET, FMGE, and USMLE — with syllabus overlap, difficulty, salary, and scope.</p>
          </div>
          <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {[
              { href: '/cms/vs-neet-pg', q1: 'UPSC CMS vs NEET PG', q2: 'Which is tougher?', q3: 'Salary & scope comparison', badge: '15k+ searches/mo' },
              { href: '/cms/vs-ini-cet', q1: 'UPSC CMS vs INI-CET', q2: 'AIIMS vs UPSC pathway', q3: 'Posting & stipend details', badge: 'Top comparison' },
              { href: '/neet-pg/vs-usmle', q1: 'NEET PG vs USMLE', q2: 'Indian PG vs US residency', q3: 'Cost, time, and ROI', badge: 'Growing interest' },
              { href: '/cms/salary', q1: 'UPSC CMS Salary', q2: 'Pay scale & grade pay', q3: 'Posting-wise breakdown', badge: '10+ imp queries' },
              { href: '/cms/exam-pattern', q1: 'UPSC CMS Exam Pattern', q2: 'Paper 1 & 2 breakdown', q3: 'Negative marking + duration', badge: 'High intent' },
              { href: '/guides/medical-officer-jobs', q1: 'Medical Officer Jobs', q2: 'After MBBS govt roles', q3: 'Salary, eligibility, vacancies', badge: '1.5k+ imp/mo' },
            ].map((c) => (
              <Link key={c.href} href={c.href} className="group rounded-2xl border border-border/50 bg-card/70 p-5 hover:border-primary/30 hover:-translate-y-0.5 transition-all">
                <div className="flex items-center justify-between mb-2">
                  <Badge variant="outline" className="text-[9px] border-border/60 text-muted-foreground">{c.badge}</Badge>
                  <ArrowUpRight className="w-3.5 h-3.5 text-muted-foreground group-hover:text-primary transition-colors" />
                </div>
                <h3 className="text-sm font-extrabold text-foreground group-hover:text-primary transition-colors">{c.q1}</h3>
                <p className="text-[11px] text-muted-foreground mt-1">{c.q2}</p>
                <p className="text-[11px] text-muted-foreground/70 mt-0.5">{c.q3}</p>
              </Link>
            ))}
          </div>

          {/* Final CTA */}
          <div className="text-center space-y-5 pt-8 border-t border-border/40">
            <h2 className="font-display text-2xl sm:text-3xl font-extrabold text-foreground tracking-tight">Ready to build an exam-ready routine?</h2>
            <p className="text-muted-foreground max-w-lg mx-auto text-sm">Join thousands of medical graduates leveraging an AI + doctor prep workflow to study faster, cleaner, and with optimized memory retention.</p>
            <Button size="xl" asChild className="rounded-2xl bg-white text-slate-950 hover:bg-slate-100 font-bold shadow-xl transition-all px-8 active:scale-[0.98]">
              <Link href={isAuthenticated ? '/dashboard' : '/register'}>
                Get Started Free <ArrowRight className="ml-1.5 w-5 h-5 text-slate-950" />
              </Link>
            </Button>
          </div>
        </div>
      </section>
    </div>
  );
}
