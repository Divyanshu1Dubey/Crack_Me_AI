'use client';

import { useState, useEffect } from 'react';
import Image from 'next/image';
import Link from 'next/link';
import dynamic from 'next/dynamic';
import { useAuth } from '@/lib/auth';
import {
  Activity,
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
  Zap,
  RotateCw,
  Flame,
  Award,
  ArrowRight,
  Crown,
  Loader2
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

const siteUrl = process.env.NEXT_PUBLIC_SITE_URL || 'https://www.cracklabs.app';

export default function LandingPage() {
  const { isAuthenticated, user } = useAuth();

  // === INTERACTIVE WIDGET STATES ===
  const [pyqAnswer, setPyqAnswer] = useState<string | null>(null);
  const [showPyqExplanation, setShowPyqExplanation] = useState(false);
  const [pyqAiLoading, setPyqAiLoading] = useState(false);
  const [pyqAiDone, setPyqAiDone] = useState(false);

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

  const [flippedCard, setFlippedCard] = useState<number | null>(null);
  const mnemonicCards = [
    {
      id: 1,
      title: "CREST Syndrome",
      subtitle: "Limited Scleroderma Features",
      front: "Click card to reveal clinical mnemonic details",
      back: [
        { letter: "C", text: "Calcinosis cutis (calcium deposits under skin)" },
        { letter: "R", text: "Raynaud's phenomenon (spasm of blood vessels)" },
        { letter: "E", text: "Esophageal dysmotility (swallowing difficulty)" },
        { letter: "S", text: "Sclerodactyly (tightening of skin on fingers)" },
        { letter: "T", text: "Telangiectasia (dilated capillaries on skin surface)" }
      ]
    },
    {
      id: 2,
      title: "Charcot's Triad",
      subtitle: "Acute Ascending Cholangitis",
      front: "Click card to reveal diagnostic triad mnemonic",
      back: [
        { letter: "J", text: "Jaundice (biliary obstruction)" },
        { letter: "F", text: "Fever with chills (active infection)" },
        { letter: "P", text: "Pain in Right Upper Quadrant (RUQ)" }
      ]
    },
    {
      id: 3,
      title: "Beck's Triad",
      subtitle: "Cardiac Tamponade Emergency",
      front: "Click card to reveal classic signs mnemonic",
      back: [
        { letter: "H", text: "Hypotension (due to restricted stroke volume)" },
        { letter: "J", text: "Jugular Venous Distension (elevated systemic pressure)" },
        { letter: "M", text: "Muffled / Distant Heart Sounds (fluid barrier)" }
      ]
    }
  ];

  const [demoSubject, setDemoSubject] = useState('Medicine');
  const [demoTopic, setDemoTopic] = useState('Cardiology');
  const [demoLoading, setDemoLoading] = useState(false);
  const [demoGenerated, setDemoGenerated] = useState(false);
  const [demoAnswer, setDemoAnswer] = useState<string | null>(null);
  interface DemoQuestion {
    text: string;
    options: { key: string; text: string }[];
    correct: string;
    explanation: string;
  }
  const [demoQuestion, setDemoQuestion] = useState<DemoQuestion | null>(null);
  const [demoAiLoading, setDemoAiLoading] = useState(false);
  const [demoAiDone, setDemoAiDone] = useState(false);

  const handleDemoGenerate = () => {
    setDemoLoading(true);
    setDemoGenerated(false);
    setDemoAnswer(null);

    setTimeout(() => {
      setDemoLoading(false);
      setDemoGenerated(true);

      if (demoSubject === 'Surgery') {
        setDemoQuestion({
          text: "A 22-year-old female presents with migration of pain from the periumbilical region to the right iliac fossa. What is the most specific clinical sign for acute appendicitis?",
          options: [
            { key: 'A', text: "Murphy's sign" },
            { key: 'B', text: "McBurney's point tenderness" },
            { key: 'C', text: "Rovsing's sign" },
            { key: 'D', text: "Psoas sign" }
          ],
          correct: 'B',
          explanation: "McBurney's point tenderness (located one-third the distance from the anterior superior iliac spine to the umbilicus) is the most classic and specific clinical sign for acute appendicitis."
        });
      } else if (demoSubject === 'Pediatrics') {
        setDemoQuestion({
          text: "A healthy 9-month-old infant is brought to the clinic for routine immunization. According to the National Immunization Schedule, which vaccine must be administered at this age?",
          options: [
            { key: 'A', text: "BCG and OPV zero dose" },
            { key: 'B', text: "DPT booster dose" },
            { key: 'C', text: "First dose of Measles (MR) vaccine and Vitamin A" },
            { key: 'D', text: "Pentavalent vaccine third dose" }
          ],
          correct: 'C',
          explanation: "Under the National Immunization Schedule, the first dose of Measles/Rubella (MR) vaccine along with the first dose of Vitamin A is administered at 9 completed months of age."
        });
      } else {
        setDemoQuestion({
          text: "A 55-year-old male presenting with chest pain is diagnosed with acute pericarditis. Which ECG finding is most characteristic of this condition?",
          options: [
            { key: 'A', text: "PR segment elevation in all leads" },
            { key: 'B', text: "Diffuse ST-elevation with PR-depression (except in aVR)" },
            { key: 'C', text: "Pathological Q waves in inferior leads" },
            { key: 'D', text: "Prolonged QT interval with T-wave inversion" }
          ],
          correct: 'B',
          explanation: "Acute pericarditis characteristically presents with diffuse ST-elevation and PR segment depression in almost all leads, with the exception of lead aVR where PR elevation and ST depression are seen."
        });
      }
    }, 1500);
  };

  const campuses = [
    'AIIMS Delhi',
    'CMC Vellore',
    'JIPMER Puducherry',
    'KGMU Lucknow',
    'Maulana Azad Medical College',
    'Seth GS Medical College',
  ];

  const communityProfiles = [
    { name: 'Dr. Riya Sharma', college: 'AIIMS Delhi', progress: '412 Clinical Qs this month', badge: 'Active Streak' },
    { name: 'Dr. Aarav Mehta', college: 'CMC Vellore', progress: 'Daily streak active for 14 days', badge: 'Top Reviewer' },
    { name: 'Dr. Nisha Krishnan', college: 'JIPMER Puducherry', progress: 'Top 9% in mock simulation', badge: 'Mock Champion' },
    { name: 'Dr. Harsh Vardhan', college: 'KGMU Lucknow', progress: '58 weak tags successfully resolved', badge: 'High Yield Master' },
  ];

  const stats = [
    { value: '2000+', label: 'Verified PYQs', icon: FileText, desc: 'UPSC CMS 2018-2025' },
    { value: '5', label: 'Core Subjects', icon: Stethoscope, desc: 'Paper 1 & Paper 2' },
    { value: '47+', label: 'Topic Clusters', icon: Activity, desc: 'High-yield medical focus' },
    { value: '9', label: 'Exam Modes', icon: ShieldCheck, desc: 'From custom drills to full simulation' },
  ];

  const subjects = [
    'General Medicine', 'Surgery', 'Pediatrics', 'Obstetrics & Gynecology', 'Preventive & Social Medicine'
  ];

  const faqSchema = {
    '@type': 'FAQPage',
    mainEntity: [
      {
        '@type': 'Question',
        name: 'Is CrackCMS useful for UPSC CMS preparation?',
        acceptedAnswer: {
          '@type': 'Answer',
          text: 'Yes. CrackCMS focuses on UPSC CMS pattern practice with PYQs, timed mocks, and clinical reasoning workflows for medical graduates.',
        },
      },
      {
        '@type': 'Question',
        name: 'Can NEET PG aspirants use CrackCMS for revision?',
        acceptedAnswer: {
          '@type': 'Answer',
          text: 'Yes. The platform includes subject-wise high-yield question practice, AI explanations, and analytics that are valuable for NEET PG revision too.',
        },
      },
      {
        '@type': 'Question',
        name: 'Does CrackCMS include mock tests for CMS exam?',
        acceptedAnswer: {
          '@type': 'Answer',
          text: 'Yes. Full exam-style simulators with timing and analysis are included for CMS exam readiness.',
        },
      },
    ],
  };

  const courseSchema = {
    '@type': 'Course',
    name: 'UPSC CMS and NEET PG Integrated Preparation Workflow',
    description:
      'A structured online preparation workflow with PYQs, mocks, AI tutoring, and weak-area analytics for UPSC CMS and NEET PG aspirants.',
    provider: {
      '@type': 'Organization',
      name: siteName,
      sameAs: siteUrl,
    },
  };

  return (
    <div className="min-h-screen bg-background font-sans antialiased">
      {/* JSON-LD Schemas */}
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{
          __html: JSON.stringify({
            '@context': 'https://schema.org',
            '@graph': [
              {
                '@type': 'Organization',
                name: siteName,
                url: siteUrl,
                logo: `${siteUrl}/cms-circle-logo.png`,
                description: 'Doctor-first UPSC CMS and NEET PG preparation platform for medical aspirants.',
              },
              {
                '@type': 'WebSite',
                name: siteName,
                url: siteUrl,
                potentialAction: {
                  '@type': 'SearchAction',
                  target: `${siteUrl}/questions?search={search_term_string}`,
                  'query-input': 'required name=search_term_string',
                },
              },
              faqSchema,
              courseSchema,
            ],
          }),
        }}
      />

      {/* Animated Background Canvas */}
      <div className="fixed inset-0 -z-10 overflow-hidden pointer-events-none">
        {/* Gradient mesh */}
        <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_top,_var(--tw-gradient-stops))] from-blue-900/20 via-background to-background" />
        {/* Floating orbs */}
        <div className="absolute top-20 left-10 w-96 h-96 bg-blue-500/10 rounded-full blur-3xl animate-pulse" />
        <div className="absolute top-40 right-20 w-80 h-80 bg-purple-500/10 rounded-full blur-3xl animate-pulse delay-1000" />
        <div className="absolute bottom-20 left-1/3 w-72 h-72 bg-cyan-500/10 rounded-full blur-3xl animate-pulse delay-2000" />
        {/* Grid pattern */}
        <div className="absolute inset-0 bg-[linear-gradient(to_right,#8882_1px,transparent_1px),linear-gradient(to_bottom,#8882_1px,transparent_1px)] bg-[size:4rem_4rem] [mask-image:radial-gradient(ellipse_80%_50%_at_50%_0%,#000_70%,transparent_100%)]" />
      </div>

      {/* Exam Countdown Banner */}
      <ExamCountdown />

      {/* Navbar */}
      <nav className="sticky top-0 z-50 border-b border-border/40 bg-background/70 backdrop-blur-2xl supports-[backdrop-filter]:bg-background/60">
        <div className="mx-auto flex h-16 max-w-7xl items-center justify-between px-4 sm:px-6 lg:px-8">
          <BrandMark href="/" compact showTagline={false} />
          <div className="flex items-center gap-2 sm:gap-3">
            <ThemeToggle />
            {isAuthenticated ? (
              <Button asChild className="rounded-xl font-semibold shadow-sm shadow-primary/10">
                <Link href="/dashboard">
                  Open Dashboard <ChevronRight className="ml-1 w-4 h-4" />
                </Link>
              </Button>
            ) : (
              <>
                <Button variant="ghost" asChild className="hidden sm:inline-flex font-medium text-muted-foreground hover:text-foreground">
                  <Link href="/login">Log in</Link>
                </Button>
                <Button asChild className="rounded-xl font-semibold shadow-lg shadow-primary/20 transition-all hover:shadow-xl hover:shadow-primary/30 hover:scale-[1.02] active:scale-[0.98]">
                  <Link href="/register">
                    Start Free <ChevronRight className="ml-1 w-4 h-4" />
                  </Link>
                </Button>
              </>
            )}
          </div>
        </div>
      </nav>

      {/* ============================================
          HERO SECTION
      ============================================ */}
      <section className="relative mx-auto max-w-7xl px-4 pb-20 pt-16 sm:px-6 lg:px-8 overflow-hidden">
        <div className="flex flex-col gap-10">
          {/* Header block */}
          <div className="space-y-8 max-w-5xl mx-auto w-full">
            {/* Badge */}
            <div className="flex justify-center">
              <div className="inline-flex items-center gap-2 rounded-full border border-primary/30 bg-primary/5 px-4 py-1.5 text-xs font-bold uppercase tracking-[0.15em] text-primary shadow-lg shadow-primary/5 backdrop-blur-sm">
                <span className="relative flex h-2 w-2">
                  <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-primary opacity-75"></span>
                  <span className="relative inline-flex rounded-full h-2 w-2 bg-primary"></span>
                </span>
                Doctor-first prep. Smart study platform.
              </div>
            </div>

            {/* Title + Logo + CTAs in a glass card */}
            <div className="relative group">
              {/* Glow behind card */}
              <div className="absolute -inset-1 bg-linear-to-r from-blue-500/20 via-purple-500/20 to-cyan-500/20 rounded-3xl blur-2xl opacity-60 group-hover:opacity-80 transition-opacity duration-500" />

              <div className="relative flex flex-col gap-8 items-center text-center md:flex-row md:items-start md:text-left rounded-3xl border border-border/50 bg-card/60 p-6 sm:p-8 md:p-10 shadow-2xl backdrop-blur-xl">
                {/* Logo */}
                <div className="relative h-32 w-32 sm:h-40 sm:w-40 md:h-48 md:w-48 shrink-0">
                  <div className="absolute inset-0 bg-linear-to-br from-amber-500/20 to-purple-500/20 rounded-full blur-2xl animate-pulse" />
                  <div className="relative h-full w-full overflow-hidden rounded-full border-2 border-amber-500/40 bg-slate-950 shadow-2xl shadow-amber-500/20">
                    <Image
                      src="/cms-circle-logo.png"
                      alt="CMS Circle Logo"
                      fill
                      sizes="(max-width: 640px) 128px, (max-width: 768px) 160px, (max-width: 1024px) 192px, 224px"
                      className="object-cover rounded-full"
                      priority
                    />
                  </div>
                </div>

                {/* Text content */}
                <div className="space-y-6 flex-1">
                  <h1 className="font-display text-4xl font-extrabold leading-[1.1] tracking-tight text-foreground sm:text-5xl lg:text-6xl">
                    <span className="relative inline-block">
                      <span className="bg-linear-to-r from-amber-500 via-pink-500 to-violet-600 bg-clip-text text-transparent animate-gradient-x bg-[length:200%_auto]">
                        AI Powered
                      </span>
                      <span className="absolute -inset-1 bg-linear-to-r from-amber-500/20 via-pink-500/20 to-violet-600/20 blur-xl opacity-0 group-hover:opacity-100 transition-opacity duration-500" />
                    </span>
                    <br />
                    <span className="text-foreground">UPSC CMS Platform</span>
                  </h1>

                  <p className="max-w-3xl text-base leading-relaxed text-foreground/80 sm:text-lg md:text-left">
                    Build daily clinical consistency with an integrated medical prep operating system.
                    Equipped with a smart question bank, AI tutoring, hyper-realistic simulated mock tests, and smart weak-area analytics.
                  </p>

                  <div className="flex flex-col items-center gap-4 sm:flex-row sm:items-center pt-2 md:items-start">
                    <Button
                      asChild
                      size="xl"
                      className="w-full rounded-2xl sm:w-auto font-semibold text-white shadow-xl shadow-fuchsia-500/30 transition-all hover:shadow-2xl hover:shadow-fuchsia-500/40 hover:scale-[1.02] active:scale-[0.98] relative overflow-hidden group/btn"
                      style={{ backgroundImage: 'linear-gradient(90deg, #f59e0b 0%, #ec4899 50%, #7c3aed 100%)' }}
                    >
                      <Link href={isAuthenticated ? '/dashboard' : '/register'}>
                        <span className="relative z-10 flex items-center">
                          Start Preparing
                          <ChevronRight className="ml-1.5 w-5 h-5 group-hover/btn:translate-x-1 transition-transform" />
                        </span>
                      </Link>
                    </Button>
                    <Button
                      variant="outline"
                      size="xl"
                      asChild
                      className="w-full rounded-2xl sm:w-auto font-semibold border-2 hover:border-primary/50 hover:bg-primary/5 transition-all"
                    >
                      <Link href="#features">
                        Explore Platform
                      </Link>
                    </Button>
                  </div>
                </div>
              </div>
            </div>

            {/* Feature pills */}
            <div className="flex flex-wrap justify-center gap-3 pt-2">
              {[
                { icon: Clock3, text: 'Daily workflow optimized', color: 'text-blue-500' },
                { icon: Target, text: 'Exam-style reasoning', color: 'text-teal-500' },
                { icon: TrendingUp, text: 'Outcome-focused analytics', color: 'text-indigo-500' },
              ].map((item, i) => (
                <div
                  key={i}
                  className="inline-flex items-center gap-2 rounded-full border border-border/60 bg-card/80 px-4 py-2 text-xs font-bold text-foreground shadow-lg shadow-black/5 backdrop-blur-sm hover:border-primary/30 hover:shadow-xl hover:shadow-primary/5 transition-all duration-300"
                >
                  <item.icon className={`h-4 w-4 ${item.color}`} />
                  {item.text}
                </div>
              ))}
            </div>
          </div>
        </div>
      </section>

      {/* ============================================
          FEATURES SECTION
      ============================================ */}
      <section id="features" className="relative border-t border-border/40 bg-muted/10 py-24 px-4 sm:px-6">
        {/* Section background decoration */}
        <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_center,_var(--tw-gradient-stops))] from-primary/5 via-background to-background" />

        <div className="mx-auto max-w-7xl space-y-20 relative">
          {/* Section header */}
          <div className="text-center max-w-3xl mx-auto space-y-4">
            <div className="inline-flex items-center gap-2 rounded-full border border-primary/20 bg-primary/5 px-4 py-1.5 text-xs font-bold uppercase tracking-[0.15em] text-primary">
              <Sparkles className="w-3.5 h-3.5" />
              Everything Needed for High-Performance CMS Prep
            </div>
            <h2 className="font-display text-3xl font-extrabold text-foreground sm:text-4xl lg:text-5xl tracking-tight">
              We broken down exam preparation into modular, specialized engines that work together seamlessly. Explore them live below.
            </h2>
            <div className="h-1 w-20 bg-linear-to-r from-blue-500 via-purple-500 to-cyan-500 rounded-full mx-auto" />
          </div>

          {/* Bento Grid */}
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
            {[
              {
                title: 'UPSC CMS Question Bank',
                description: '3,300+ authentic previous year questions with AI-grounded medical explanations.',
                label: 'UPSC CMS',
                icon: FileText,
                color: 'from-emerald-500/10 to-teal-500/10',
                borderColor: 'border-emerald-500/30',
                iconColor: 'text-emerald-500',
              },
              {
                title: 'NEET PG Clinical Bank',
                description: 'Subject-wise high-yield practice with image-based questions and mnemonics.',
                label: 'NEET PG',
                icon: GraduationCap,
                color: 'from-blue-500/10 to-indigo-500/10',
                borderColor: 'border-blue-500/30',
                iconColor: 'text-blue-500',
              },
              {
                title: 'AI Tutor Assistant',
                description: 'Harrison & Robbins trained multi-model AI assistant for immediate doubts.',
                label: 'AI Tutor',
                icon: Brain,
                color: 'from-purple-500/10 to-pink-500/10',
                borderColor: 'border-purple-500/30',
                iconColor: 'text-purple-500',
              },
              {
                title: 'Adaptive Mock Tests',
                description: 'Timed exam engine simulating exact NBE and UPSC test environments.',
                label: 'Mock Tests',
                icon: Clock3,
                color: 'from-cyan-500/10 to-blue-500/10',
                borderColor: 'border-cyan-500/30',
                iconColor: 'text-cyan-500',
              },
              {
                title: 'Rapid Recall Flashcards',
                description: 'SM-2 algorithm flashcards for rapid high-yield clinical memory retention.',
                label: 'Recall',
                icon: RotateCw,
                color: 'from-amber-500/10 to-orange-500/10',
                borderColor: 'border-amber-500/30',
                iconColor: 'text-amber-500',
              },
              {
                title: 'Performance Analytics',
                description: 'Granular weak-area identification and real-time rank predictions.',
                label: 'Analytics',
                icon: TrendingUp,
                color: 'from-rose-500/10 to-pink-500/10',
                borderColor: 'border-rose-500/30',
                iconColor: 'text-rose-500',
              },
            ].map((item, i) => (
              <div
                key={i}
                className="group relative rounded-3xl border-2 border-border/60 bg-card/40 p-6 backdrop-blur-xl transition-all duration-500 hover:scale-[1.02] hover:border-primary/30 hover:shadow-2xl hover:shadow-primary/10 overflow-hidden"
              >
                {/* Animated gradient background on hover */}
                <div className={`absolute inset-0 bg-linear-to-br ${item.color} opacity-0 group-hover:opacity-100 transition-opacity duration-500`} />

                {/* Glow effect */}
                <div className="absolute -inset-1 bg-linear-to-r from-primary/10 via-transparent to-primary/10 rounded-3xl blur-xl opacity-0 group-hover:opacity-100 transition-opacity duration-500 -z-10" />

                <div className="relative space-y-4">
                  <div className="flex items-start justify-between">
                    <div className={`h-12 w-12 rounded-2xl bg-linear-to-br ${item.color} border ${item.borderColor} flex items-center justify-center shadow-lg`}>
                      <item.icon className={`h-6 w-6 ${item.iconColor}`} />
                    </div>
                    <span className="text-[10px] font-bold uppercase tracking-wider text-muted-foreground bg-muted/50 px-3 py-1 rounded-full">
                      {item.label}
                    </span>
                  </div>

                  <h3 className="text-lg font-bold text-foreground group-hover:text-primary transition-colors">
                    {item.title}
                  </h3>
                  <p className="text-sm text-muted-foreground leading-relaxed">
                    {item.description}
                  </p>

                  <div className="flex items-center gap-2 text-xs font-semibold text-primary opacity-0 group-hover:opacity-100 transition-opacity duration-300">
                    Learn more <ChevronRight className="h-3.5 w-3.5 group-hover:translate-x-1 transition-transform" />
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ============================================
          INTERACTIVE FEATURES
      ============================================ */}
      <section className="px-4 sm:px-6 py-24 space-y-32">
        <div className="mx-auto max-w-7xl space-y-32">

          {/* Feature 1: Clinical PYQ Atlas */}
          <div className="relative group rounded-[2.5rem] border-2 border-emerald-500/20 bg-gradient-to-br from-emerald-500/5 to-teal-500/5 p-6 sm:p-8 md:p-12 shadow-2xl backdrop-blur-sm overflow-hidden">
            {/* Animated background glow */}
            <div className="absolute right-0 bottom-0 -z-10 h-96 w-96 bg-emerald-500/10 rounded-full blur-3xl opacity-60 group-hover:opacity-80 group-hover:scale-110 transition-all duration-700" />

            <div className="grid gap-12 lg:grid-cols-12 items-center relative z-10">
              <div className="lg:col-span-6 space-y-6">
                <Badge className="bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 hover:bg-emerald-500/15 border-0 font-bold uppercase tracking-wider text-[10px]">
                  FEATURE DEEP DIVE
                </Badge>
                <h3 className="font-display text-2xl font-extrabold text-foreground sm:text-3xl lg:text-4xl leading-tight">
                  Clinical PYQ Atlas
                </h3>
                <p className="text-base text-muted-foreground leading-relaxed">
                  Unlock 2000+ active past questions from UPSC CMS (2018-2025). Every question is systematically indexed by subject, topic cluster, and difficulty grade, and enriched with voter-consensus answers and high-yield references.
                </p>

                <ul className="space-y-3 font-semibold text-foreground text-sm">
                  <li className="flex items-center gap-2.5">
                    <CheckCircle2 className="h-5 w-5 text-emerald-500 shrink-0" />
                    Double-verified medical consensus answer keys
                  </li>
                  <li className="flex items-center gap-2.5">
                    <CheckCircle2 className="h-5 w-5 text-emerald-500 shrink-0" />
                    Direct cross-referencing to core medical textbooks
                  </li>
                  <li className="flex items-center gap-2.5">
                    <CheckCircle2 className="h-5 w-5 text-emerald-500 shrink-0" />
                    Keyboard shortcuts for lightning-fast answer flow
                  </li>
                </ul>
              </div>

              {/* Interactive MCQ Mock Widget */}
              <div className="lg:col-span-6">
                <div className="rounded-3xl border-2 border-emerald-500/30 bg-slate-950 p-6 shadow-2xl relative overflow-hidden">
                  {/* Scan line effect */}
                  <div className="absolute inset-0 bg-linear-to-b from-transparent via-emerald-500/5 to-transparent bg-[length:100%_4px] animate-pulse" />

                  <span className="relative -top-3 left-6 rounded-full bg-emerald-500 text-white text-[10px] font-bold px-3 py-1 uppercase tracking-wider shadow-lg shadow-emerald-500/50">
                    Interactive Demo
                  </span>

                  <div className="space-y-4 pt-2 relative">
                    <div className="flex justify-between items-center text-xs font-bold text-slate-400">
                      <span>UPSC CMS 2024 Paper 1</span>
                      <span className="text-emerald-400">Question #182</span>
                    </div>

                    <p className="text-sm font-bold text-slate-200 leading-relaxed">
                      A 45-year-old male presents with acute severe chest pain radiating to the left arm. EKG shows ST-elevation in leads V1-V4. What is the immediate drug of choice for coronary reperfusion in a non-PCI capable center?
                    </p>

                    <div className="space-y-2">
                      {[
                        { key: 'A', text: 'Oral Beta Blockers' },
                        { key: 'B', text: 'Thrombolytic Therapy (e.g. Tenecteplase)' },
                        { key: 'C', text: 'Sublingual Nitroglycerin' },
                        { key: 'D', text: 'Maintenance Clopidogrel' }
                      ].map((opt) => {
                        const isSelected = pyqAnswer === opt.key;
                        const isCorrect = opt.key === 'B';
                        let btnStyle = "border-slate-700 hover:border-emerald-500/50 hover:bg-slate-800";

                        if (pyqAnswer !== null) {
                          if (isCorrect) {
                            btnStyle = "border-emerald-500 bg-emerald-500/10 text-emerald-300 shadow-lg shadow-emerald-500/20";
                          } else if (isSelected) {
                            btnStyle = "border-red-500 bg-red-500/10 text-red-300";
                          } else {
                            btnStyle = "border-slate-700/50 opacity-40";
                          }
                        }

                        return (
                          <button
                            key={opt.key}
                            onClick={() => {
                              if (pyqAnswer === null) {
                                setPyqAnswer(opt.key);
                                setShowPyqExplanation(true);
                              }
                            }}
                            className={`w-full text-left rounded-xl border-2 p-3.5 text-xs font-semibold flex items-center gap-3 transition-all ${btnStyle}`}
                          >
                            <span className={`h-6 w-6 rounded-full flex items-center justify-center shrink-0 border-2 text-xs font-extrabold
                              ${isSelected && isCorrect ? 'bg-emerald-500 text-white border-emerald-500' : ''}
                              ${isSelected && !isCorrect ? 'bg-red-500 text-white border-red-500' : ''}
                              ${!isSelected && isCorrect && pyqAnswer !== null ? 'bg-emerald-500 text-white border-emerald-500' : 'border-slate-600'}
                            `}>
                              {opt.key}
                            </span>
                            <span>{opt.text}</span>
                          </button>
                        );
                      })}
                    </div>

                    {showPyqExplanation && (
                      <div className="space-y-3 animate-fadeIn">
                        <div className="rounded-xl bg-slate-900/80 p-4 border border-emerald-500/20 space-y-2">
                          <div className="flex items-center gap-2 text-xs font-bold text-emerald-400">
                            <Sparkles className="h-3.5 w-3.5" />
                            AI Explanation Consensus:
                          </div>
                          <p className="text-[11px] leading-relaxed text-slate-300">
                            In an acute anterior wall STEMI (V1-V4 elevation) presenting to a non-PCI center, immediate thrombolytic therapy is indicated if primary PCI delay exceeds 120 minutes. Tenecteplase is preferred due to high fibrin specificity.
                          </p>
                        </div>

                        {!pyqAiDone && !pyqAiLoading && (
                          <button
                            onClick={() => { setPyqAiLoading(true); setTimeout(() => { setPyqAiLoading(false); setPyqAiDone(true); }, 1800); }}
                            className="w-full rounded-xl border-2 border-blue-500/30 bg-blue-500/10 p-3 flex items-center justify-center gap-2 cursor-pointer transition-all hover:bg-blue-500/20 text-xs font-bold text-blue-400 hover:text-blue-300"
                          >
                            <Brain className="w-4 h-4" /> Generate AI Analysis
                          </button>
                        )}
                        {pyqAiLoading && (
                          <div className="flex items-center justify-center gap-2 p-3 rounded-xl border-2 border-blue-500/30 bg-blue-500/5">
                            <Loader2 className="w-4 h-4 animate-spin text-blue-500" />
                            <span className="text-[11px] font-bold text-blue-400">Analyzing with AI...</span>
                          </div>
                        )}
                        {pyqAiDone && (
                          <div className="space-y-2 animate-fadeIn">
                            <div className="rounded-xl bg-emerald-500/10 border border-emerald-500/20 p-3">
                              <div className="text-[10px] font-bold text-emerald-400 mb-1 flex items-center gap-1"><CheckCircle2 className="w-3 h-3" /> Why Correct</div>
                              <p className="text-[11px] leading-relaxed text-slate-300">Thrombolytic therapy (specifically Tenecteplase) is the gold standard for STEMI reperfusion when primary PCI cannot be performed within the 120-minute door-to-balloon window.</p>
                            </div>
                            <div className="rounded-xl bg-amber-500/10 border border-amber-500/20 p-3">
                              <div className="text-[10px] font-bold text-amber-400 mb-1">🧠 Mnemonic</div>
                              <p className="text-[11px] leading-relaxed text-slate-300"><strong>STEMI-T</strong>: ST elevation → Emergency → Must reperfuse → Intervention (PCI or Thrombolysis) → Tenecteplase if no PCI</p>
                            </div>
                          </div>
                        )}

                        <div className="flex justify-between items-center pt-2 text-[10px] text-slate-500 border-t border-slate-800">
                          <span>Textbook: <strong className="text-slate-400">Harrison&apos;s Cardiology, Ch. 273</strong></span>
                          <button
                            onClick={() => {
                              setPyqAnswer(null);
                              setShowPyqExplanation(false);
                              setPyqAiDone(false);
                              setPyqAiLoading(false);
                            }}
                            className="text-emerald-400 font-bold hover:underline"
                          >
                            Reset Demo
                          </button>
                        </div>
                      </div>
                    )}
                  </div>
                </div>
              </div>
            </div>
          </div>

          {/* Feature 2: Doctor-Grade AI Tutor */}
          <div className="relative group rounded-[2.5rem] border-2 border-blue-500/20 bg-gradient-to-br from-blue-500/5 to-indigo-500/5 p-6 sm:p-8 md:p-12 shadow-2xl backdrop-blur-sm overflow-hidden">
            <div className="absolute left-0 bottom-0 -z-10 h-96 w-96 bg-blue-500/10 rounded-full blur-3xl opacity-60 group-hover:opacity-80 group-hover:scale-110 transition-all duration-700" />

            <div className="grid gap-12 lg:grid-cols-12 items-center relative z-10">
              <div className="lg:col-span-6 lg:order-last space-y-6">
                <Badge className="bg-blue-500/10 text-blue-600 dark:text-blue-400 hover:bg-blue-500/15 border-0 font-bold uppercase tracking-wider text-[10px]">
                  RAG KNOWLEDGE RETRIEVAL
                </Badge>
                <h3 className="font-display text-2xl font-extrabold text-foreground sm:text-3xl lg:text-4xl leading-tight">
                  Doctor-Grade AI Tutor
                </h3>
                <p className="text-base text-muted-foreground leading-relaxed">
                  Stuck on a tricky pathophysiology concept? Our AI Tutor retrieves context from 79 textbook chapters and medical resources to provide grounded explanations aligned with standard clinical practice.
                </p>

                <ul className="space-y-3 font-semibold text-foreground text-sm">
                  <li className="flex items-center gap-2.5">
                    <CheckCircle2 className="h-5 w-5 text-blue-500 shrink-0" />
                    Interactive chat modes (Socratic, Viva, High-Yield)
                  </li>
                  <li className="flex items-center gap-2.5">
                    <CheckCircle2 className="h-5 w-5 text-blue-500 shrink-0" />
                    Multi-model round-robin routing (failsafe reliability)
                  </li>
                  <li className="flex items-center gap-2.5">
                    <CheckCircle2 className="h-5 w-5 text-blue-500 shrink-0" />
                    Instant mnemonic generation to simplify retention
                  </li>
                </ul>
              </div>

              {/* AI Chat Mockup */}
              <div className="lg:col-span-6">
                <div className="rounded-3xl border-2 border-blue-500/30 bg-slate-950 p-5 shadow-2xl relative overflow-hidden">
                  {/* HUD corners */}
                  <div className="absolute top-0 left-0 w-8 h-8 border-t-2 border-l-2 border-blue-500/50" />
                  <div className="absolute top-0 right-0 w-8 h-8 border-t-2 border-r-2 border-blue-500/50" />
                  <div className="absolute bottom-0 left-0 w-8 h-8 border-b-2 border-l-2 border-blue-500/50" />
                  <div className="absolute bottom-0 right-0 w-8 h-8 border-b-2 border-r-2 border-blue-500/50" />

                  <span className="relative -top-3 left-6 rounded-full bg-blue-500 text-white text-[10px] font-bold px-3 py-1 uppercase tracking-wider shadow-lg shadow-blue-500/50">
                    Interactive Demo
                  </span>

                  <div className="space-y-4 pt-2">
                    <div className="flex gap-1.5 border-b border-slate-800 pb-3">
                      {[
                        { id: 'ra', label: 'Rheumatoid Arthritis' },
                        { id: 'se', label: 'Status Epilepticus' },
                        { id: 'as', label: 'Aortic Stenosis' }
                      ].map((btn) => (
                        <button
                          key={btn.id}
                          onClick={() => setActiveTutorTopic(btn.id as 'ra' | 'se' | 'as')}
                          className={`px-3 py-1.5 rounded-lg text-[10px] font-bold border-2 transition-all ${
                            activeTutorTopic === btn.id
                              ? 'bg-blue-500 border-blue-500 text-white shadow-lg shadow-blue-500/30'
                              : 'border-slate-700 bg-slate-900/50 text-slate-400 hover:bg-slate-800'
                          }`}
                        >
                          {btn.label}
                        </button>
                      ))}
                    </div>

                    <div className="space-y-3 max-h-70 overflow-y-auto pr-1">
                      {/* User Prompt */}
                      <div className="flex items-start gap-2.5 justify-end">
                        <div className="rounded-2xl rounded-tr-sm bg-blue-600 text-white px-4 py-2.5 max-w-[85%] text-xs font-semibold shadow-lg shadow-blue-500/20">
                          {tutorConversations[activeTutorTopic].question}
                        </div>
                        <div className="h-7 w-7 rounded-full bg-blue-500/20 border-2 border-blue-500/40 flex items-center justify-center shrink-0 text-xs font-extrabold text-blue-400">
                          Dr
                        </div>
                      </div>

                      {/* AI Answer */}
                      <div className="flex items-start gap-2.5">
                        <div className="h-7 w-7 rounded-full bg-indigo-500 border-2 border-indigo-400 flex items-center justify-center shrink-0 text-[10px] font-extrabold text-white">
                          AI
                        </div>
                        <div className="rounded-2xl rounded-tl-sm bg-slate-900/80 px-4 py-2.5 max-w-[85%] text-xs text-slate-200 leading-relaxed border border-slate-800">
                          <div className="flex items-center gap-1.5 text-[10px] font-bold text-indigo-400 mb-1.5">
                            <Brain className="h-3.5 w-3.5" />
                            RAG Grounded Response
                          </div>
                          <div
                            className="space-y-2 whitespace-pre-line"
                            dangerouslySetInnerHTML={{
                              __html: (() => {
                                const escapeHtml = (v: string) =>
                                  v
                                    .replace(/</g, '&lt;')
                                    .replace(/>/g, '&gt;')
                                    .replace(/"/g, '&quot;')
                                    .replace(/'/g, '&#39;')
                                    .replace(/&/g, '&amp;');
                                const raw = tutorConversations[activeTutorTopic].reply;
                                const parts = raw.split(/\*\*(.*?)\*\*/g);
                                return parts
                                  .map((p, i) => (i % 2 === 1 ? `<strong class="text-indigo-400">${p}</strong>` : escapeHtml(p)))
                                  .join('');
                              })()
                            }}
                          />
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>

          {/* Feature 3: Smart Exam Engine */}
          <div className="relative group rounded-[2.5rem] border-2 border-teal-500/20 bg-gradient-to-br from-teal-500/5 to-cyan-500/5 p-6 sm:p-8 md:p-12 shadow-2xl backdrop-blur-sm overflow-hidden">
            <div className="absolute right-0 top-0 -z-10 h-96 w-96 bg-teal-500/10 rounded-full blur-3xl opacity-60 group-hover:opacity-80 group-hover:scale-110 transition-all duration-700" />

            <div className="grid gap-12 lg:grid-cols-12 items-center relative z-10">
              <div className="lg:col-span-6 space-y-6">
                <Badge className="bg-teal-500/10 text-teal-600 dark:text-teal-400 hover:bg-teal-500/15 border-0 font-bold uppercase tracking-wider text-[10px]">
                  ADAPTIVE SYSTEM
                </Badge>
                <h3 className="font-display text-2xl font-extrabold text-foreground sm:text-3xl lg:text-4xl leading-tight">
                  Smart Exam Engine
                </h3>
                <p className="text-base text-muted-foreground leading-relaxed">
                  Take control of your preparation with adaptive testing modes that mimic UPSC CMS exam conditions. Features automated timers, negative marking scoring, and immediate breakdown reviews.
                </p>

                <ul className="space-y-3 font-semibold text-foreground text-sm">
                  <li className="flex items-center gap-2.5">
                    <CheckCircle2 className="h-5 w-5 text-teal-500 shrink-0" />
                    Realistic exam interface mimicking actual test software
                  </li>
                  <li className="flex items-center gap-2.5">
                    <CheckCircle2 className="h-5 w-5 text-teal-500 shrink-0" />
                    Dynamic negative scoring (+1.0 / -0.33 marking)
                  </li>
                  <li className="flex items-center gap-2.5">
                    <CheckCircle2 className="h-5 w-5 text-teal-500 shrink-0" />
                    Customized topic weight drills based on prior weak performance
                  </li>
                </ul>
              </div>

              {/* Exam HUD widget mockup */}
              <div className="lg:col-span-6">
                <div className="rounded-3xl border-2 border-teal-500/30 bg-slate-950 text-slate-100 p-6 shadow-2xl relative font-mono">
                  <span className="absolute -top-3 left-6 rounded-full bg-teal-500 text-white text-[10px] font-bold px-3 py-1 uppercase tracking-wider shadow-lg shadow-teal-500/50">
                    Interactive Demo
                  </span>

                  <div className="space-y-5 pt-2">
                    <div className="flex items-center justify-between border-b border-slate-800 pb-3">
                      <div className="flex items-center gap-2.5">
                        <Clock3 className="h-4 w-4 text-rose-500 animate-pulse" />
                        <span className="font-mono text-sm font-bold text-rose-400">{formatTimer(examTimer)}</span>
                      </div>
                      <div className="text-xs font-bold text-slate-400">
                        Section: <span className="text-teal-400">Paper 1 (Obstetrics)</span>
                      </div>
                    </div>

                    <div className="space-y-1.5">
                      <p className="text-[10px] uppercase font-bold text-slate-500 tracking-wider">Question 24 of 120</p>
                      <p className="text-xs font-bold leading-relaxed text-slate-200">
                        Which of the following is the definitive management of severe pre-eclampsia at 38 weeks of gestation?
                      </p>
                    </div>

                    <div className="space-y-2">
                      {[
                        { key: 'A', text: 'Intravenous Magnesium Sulfate infusion' },
                        { key: 'B', text: 'Oral Antihypertensives and weekly monitoring' },
                        { key: 'C', text: 'Immediate delivery of the fetus' },
                        { key: 'D', text: 'Strict bed rest and corticosteroid administration' }
                      ].map((ch) => {
                        const isSel = examSelectedOption === ch.key;
                        return (
                          <button
                            key={ch.key}
                            onClick={() => setExamSelectedOption(ch.key)}
                            className={`w-full text-left rounded-xl border-2 p-3 text-[11px] font-semibold flex items-center gap-3 transition-all ${
                              isSel
                                ? 'border-teal-500 bg-teal-500/10 text-teal-300 shadow-lg shadow-teal-500/10'
                                : 'border-slate-800 bg-slate-900/50 hover:bg-slate-800 text-slate-400 hover:text-slate-200'
                            }`}
                          >
                            <span className={`h-5 w-5 rounded-full flex items-center justify-center shrink-0 border-2 text-[10px] font-extrabold ${
                              isSel ? 'bg-teal-500 border-teal-500 text-slate-950' : 'border-slate-700 bg-slate-950'
                            }`}>
                              {ch.key}
                            </span>
                            <span>{ch.text}</span>
                          </button>
                        );
                      })}
                    </div>

                    <div className="border-t border-slate-800 pt-3.5 flex justify-between items-center text-[10px] text-slate-500">
                      <div className="flex gap-3">
                        <span>Correct: <strong className="text-emerald-500 font-bold">18 (+18.0)</strong></span>
                        <span>Incorrect: <strong className="text-rose-500 font-bold">5 (-1.65)</strong></span>
                      </div>
                      <div>
                        <span>Score: <strong className="text-teal-400 font-bold">16.35</strong></span>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>

          {/* Feature 4: Rapid Recall AI */}
          <div className="relative group rounded-[2.5rem] border-2 border-amber-500/20 bg-gradient-to-br from-amber-500/5 to-orange-500/5 p-6 sm:p-8 md:p-12 shadow-2xl backdrop-blur-sm overflow-hidden">
            <div className="absolute left-0 top-0 -z-10 h-96 w-96 bg-amber-500/10 rounded-full blur-3xl opacity-60 group-hover:opacity-80 group-hover:scale-110 transition-all duration-700" />

            <div className="grid gap-12 lg:grid-cols-12 items-center relative z-10">
              <div className="lg:col-span-6 lg:order-last space-y-6">
                <Badge className="bg-amber-500/10 text-amber-600 dark:text-amber-400 hover:bg-amber-500/15 border-0 font-bold uppercase tracking-wider text-[10px]">
                  SPACED REPETITION
                </Badge>
                <h3 className="font-display text-2xl font-extrabold text-foreground sm:text-3xl lg:text-4xl leading-tight">
                  Rapid Recall AI (SM-2)
                </h3>
                <p className="text-base text-muted-foreground leading-relaxed">
                  Consolidate critical high-yield facts using our SM-2 algorithm-backed flashcard system. Generates personalized clinical mnemonics to build active recall memory retention.
                </p>

                <ul className="space-y-3 font-semibold text-foreground text-sm">
                  <li className="flex items-center gap-2.5">
                    <CheckCircle2 className="h-5 w-5 text-amber-500 shrink-0" />
                    Smart spaced repetition algorithm (SM-2)
                  </li>
                  <li className="flex items-center gap-2.5">
                    <CheckCircle2 className="h-5 w-5 text-amber-500 shrink-0" />
                    Quick mnemonics cards with colored highlight structures
                  </li>
                  <li className="flex items-center gap-2.5">
                    <CheckCircle2 className="h-5 w-5 text-amber-500 shrink-0" />
                    Custom card builder and public deck library
                  </li>
                </ul>
              </div>

              {/* Interactive Flashcard Widget */}
              <div className="lg:col-span-6">
                <div className="space-y-4">
                  <div className="flex justify-between items-center text-xs font-bold text-muted-foreground px-2">
                    <span>Interactive Flashcards</span>
                    <span className="text-amber-500">Tap Card to Flip</span>
                  </div>

                  <div className="grid grid-cols-3 gap-2">
                    {mnemonicCards.map((c) => (
                      <button
                        key={c.id}
                        onClick={() => setFlippedCard(flippedCard === c.id ? null : c.id)}
                        className={`py-2 px-3 text-center rounded-xl text-[10px] font-bold border-2 transition-all ${
                          flippedCard === c.id
                            ? 'bg-amber-500 border-amber-500 text-white shadow-lg shadow-amber-500/30'
                            : 'border-border/60 bg-card/80 hover:bg-amber-500/10 text-muted-foreground hover:text-foreground'
                        }`}
                      >
                        {c.title}
                      </button>
                    ))}
                  </div>

                  <div className="perspective-1000 h-65 w-full relative">
                    {mnemonicCards.map((c) => {
                      const isFlipped = flippedCard === c.id;
                      const isSelected = flippedCard === null ? c.id === 1 : flippedCard === c.id;

                      if (!isSelected) return null;
                      const activeFlippedState = flippedCard === null ? false : isFlipped;

                      return (
                        <div
                          key={c.id}
                          onClick={() => setFlippedCard(flippedCard === c.id ? null : c.id)}
                          className={`w-full h-full duration-700 transform-style-3d relative cursor-pointer select-none rounded-3xl border-2 border-amber-500/30 bg-card shadow-2xl ${activeFlippedState ? 'rotate-y-180' : ''}`}
                        >
                          {/* Front side */}
                          <div className="absolute inset-0 backface-hidden w-full h-full flex flex-col justify-between p-6 bg-gradient-to-br from-amber-500/5 to-orange-500/5">
                            <div>
                              <div className="flex justify-between items-center text-[10px] font-bold text-amber-600">
                                <span>HIGH YIELD CARD</span>
                                <Sparkles className="h-4 w-4" />
                              </div>
                              <h4 className="text-lg font-extrabold text-foreground mt-4">{c.title}</h4>
                              <p className="text-xs text-muted-foreground mt-1">{c.subtitle}</p>
                            </div>

                            <div className="text-center text-[11px] text-muted-foreground/80 py-4 border-t border-border/40 flex items-center justify-center gap-1">
                              <RotateCw className="h-3 w-3" />
                              {c.front}
                            </div>
                          </div>

                          {/* Back side */}
                          <div className="absolute inset-0 backface-hidden rotate-y-180 w-full h-full bg-gradient-to-br from-amber-500/10 to-orange-500/10 flex flex-col justify-between p-6 overflow-y-auto">
                            <div>
                              <span className="text-[10px] font-bold text-amber-600 tracking-wider">CLINICAL MNEMONIC</span>
                              <h4 className="text-base font-extrabold text-foreground mt-1 border-b border-border/60 pb-2">{c.title}</h4>

                              <div className="mt-3.5 space-y-2">
                                {c.back.map((b, bi) => (
                                  <div key={bi} className="flex gap-2.5 text-xs text-foreground items-start">
                                    <span className="h-5 w-5 rounded-md bg-amber-500 text-white font-extrabold flex items-center justify-center text-[10px] shrink-0">
                                      {b.letter}
                                    </span>
                                    <span className="font-semibold">{b.text}</span>
                                  </div>
                                ))}
                              </div>
                            </div>

                            <div className="text-center text-[10px] text-amber-600 font-bold border-t border-border/40 pt-3">
                              Spaced Review interval: 3 days (SM-2)
                            </div>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </div>
              </div>
            </div>
          </div>

          {/* Feature 5: Question Generator */}
          <div className="relative group rounded-[2.5rem] border-2 border-cyan-500/20 bg-gradient-to-br from-cyan-500/5 to-blue-500/5 p-6 sm:p-8 md:p-12 shadow-2xl backdrop-blur-sm overflow-hidden">
            <div className="absolute right-0 bottom-0 -z-10 h-96 w-96 bg-cyan-500/10 rounded-full blur-3xl opacity-60 group-hover:opacity-80 group-hover:scale-110 transition-all duration-700" />

            <div className="grid gap-12 lg:grid-cols-12 items-center relative z-10">
              <div className="lg:col-span-6 space-y-6">
                <Badge className="bg-cyan-500/10 text-cyan-600 dark:text-cyan-400 hover:bg-cyan-500/15 border-0 font-bold uppercase tracking-wider text-[10px]">
                  UNLIMITED CLINICAL DRILLS
                </Badge>
                <h3 className="font-display text-2xl font-extrabold text-foreground sm:text-3xl lg:text-4xl leading-tight">
                  Question Generator
                </h3>
                <p className="text-base text-muted-foreground leading-relaxed">
                  Generate bespoke mock questions tailored to any subject, sub-topic, and difficulty level. Strengthen active recall by generating targeted clinical drills on topics where you need the most reinforcement.
                </p>

                <ul className="space-y-3 font-semibold text-foreground text-sm">
                  <li className="flex items-center gap-2.5">
                    <CheckCircle2 className="h-5 w-5 text-cyan-500 shrink-0" />
                    Bespoke question generation matching UPSC CMS patterns
                  </li>
                  <li className="flex items-center gap-2.5">
                    <CheckCircle2 className="h-5 w-5 text-cyan-500 shrink-0" />
                    Detailed explanation breakdowns automatically created
                  </li>
                  <li className="flex items-center gap-2.5">
                    <CheckCircle2 className="h-5 w-5 text-cyan-500 shrink-0" />
                    Focus on custom sub-topics like Pediatrics, Vaccines, Cardiology
                  </li>
                </ul>
              </div>

              {/* Interactive Question Generator Demo */}
              <div className="lg:col-span-6">
                <div className="rounded-3xl border-2 border-cyan-500/30 bg-card p-6 shadow-2xl relative overflow-hidden">
                  <span className="absolute -top-3 left-6 rounded-full bg-cyan-500 text-white text-[10px] font-bold px-3 py-1 uppercase tracking-wider shadow-lg shadow-cyan-500/50">
                    Interactive Demo
                  </span>

                  <div className="space-y-4 pt-2">
                    <div className="flex justify-between items-center text-xs font-bold text-muted-foreground">
                      <span>Generate Custom Questions</span>
                      <span className="text-cyan-600">Question Generator</span>
                    </div>

                    <div className="grid grid-cols-2 gap-2 text-xs">
                      <div>
                        <label className="block font-bold text-muted-foreground mb-1">Subject</label>
                        <select
                          value={demoSubject}
                          onChange={(e) => {
                            setDemoSubject(e.target.value);
                            setDemoGenerated(false);
                            setDemoAnswer(null);
                          }}
                          className="w-full px-2 py-1.5 rounded-lg border-2 border-border/60 bg-muted/20 text-xs font-semibold text-foreground"
                        >
                          <option value="Medicine">General Medicine</option>
                          <option value="Surgery">Surgery</option>
                          <option value="Pediatrics">Pediatrics</option>
                        </select>
                      </div>
                      <div>
                        <label className="block font-bold text-muted-foreground mb-1">Topic (optional)</label>
                        <input
                          type="text"
                          value={demoTopic}
                          onChange={(e) => {
                            setDemoTopic(e.target.value);
                            setDemoGenerated(false);
                            setDemoAnswer(null);
                          }}
                          placeholder="e.g. Cardiology, Vaccines"
                          className="w-full px-2 py-1.5 rounded-lg border-2 border-border/60 bg-muted/20 text-xs font-semibold text-foreground placeholder:text-muted-foreground/60"
                        />
                      </div>
                    </div>

                    {!demoGenerated && !demoLoading && (
                      <button
                        onClick={handleDemoGenerate}
                        className="w-full py-2.5 rounded-xl bg-cyan-500 hover:bg-cyan-600 text-white font-bold text-xs flex items-center justify-center gap-1.5 shadow-lg shadow-cyan-500/20 active:scale-95 transition-all cursor-pointer"
                      >
                        <Sparkles className="w-3.5 h-3.5" />
                        Generate Custom Drill
                      </button>
                    )}

                    {demoLoading && (
                      <div className="p-6 text-center space-y-3 bg-muted/20 rounded-xl border-2 border-border/40">
                        <Loader2 className="w-6 h-6 animate-spin mx-auto text-cyan-500" />
                        <p className="text-[11px] font-bold text-cyan-600">Generating bespoke {demoSubject} question on &quot;{demoTopic || 'General Info'}&quot;...</p>
                      </div>
                    )}

                    {demoGenerated && demoQuestion && (
                      <div className="space-y-4 pt-1 animate-fadeIn">
                        <div className="p-3 bg-cyan-500/5 rounded-xl border-2 border-cyan-500/20 text-xs font-bold leading-relaxed text-foreground">
                          {demoQuestion.text}
                        </div>

                        <div className="space-y-2">
                          {demoQuestion.options.map((opt: { key: string; text: string }) => {
                            const isSelected = demoAnswer === opt.key;
                            const isCorrect = opt.key === demoQuestion.correct;
                            let btnStyle = "border-border/60 hover:border-cyan-500/50 hover:bg-muted/10";

                            if (demoAnswer !== null) {
                              if (isCorrect) {
                                btnStyle = "border-emerald-500 bg-emerald-500/5 text-emerald-300";
                              } else if (isSelected) {
                                btnStyle = "border-red-500 bg-red-500/5 text-red-300";
                              } else {
                                btnStyle = "border-border/40 opacity-40";
                              }
                            }

                            return (
                              <button
                                key={opt.key}
                                onClick={() => {
                                  if (demoAnswer === null) {
                                    setDemoAnswer(opt.key);
                                  }
                                }}
                                className={`w-full text-left rounded-xl border-2 p-3 text-[11px] font-semibold flex items-center gap-3 transition-all ${btnStyle}`}
                              >
                                <span className={`h-5 w-5 rounded-full flex items-center justify-center shrink-0 border-2 text-[10px] font-extrabold
                                  ${isSelected && isCorrect ? 'bg-emerald-500 text-white border-emerald-500' : ''}
                                  ${isSelected && !isCorrect ? 'bg-red-500 text-white border-red-500' : ''}
                                  ${!isSelected && isCorrect && demoAnswer !== null ? 'bg-emerald-500 text-white border-emerald-500' : 'border-border'}
                                `}>
                                  {opt.key}
                                </span>
                                <span>{opt.text}</span>
                              </button>
                            );
                          })}
                        </div>

                        {demoAnswer !== null && (
                          <div className="space-y-2 animate-fadeIn">
                            <div className="rounded-xl bg-muted/40 p-3 border-2 border-cyan-500/20 space-y-1">
                              <div className="flex items-center gap-1.5 text-xs font-bold text-cyan-600">
                                <Sparkles className="h-3.5 w-3.5" />
                                Explanation:
                              </div>
                              <p className="text-[11px] leading-relaxed text-muted-foreground">
                                {demoQuestion.explanation}
                              </p>
                            </div>

                            {!demoAiDone && !demoAiLoading && (
                              <button
                                onClick={() => { setDemoAiLoading(true); setTimeout(() => { setDemoAiLoading(false); setDemoAiDone(true); }, 1800); }}
                                className="w-full rounded-xl border-2 border-blue-500/30 bg-blue-500/10 p-3 flex items-center justify-center gap-2 cursor-pointer transition-all hover:bg-blue-500/20 text-xs font-bold text-blue-400 hover:text-blue-300"
                              >
                                <Brain className="w-4 h-4" /> Generate AI Analysis
                              </button>
                            )}
                            {demoAiLoading && (
                              <div className="flex items-center justify-center gap-2 p-3 rounded-xl border-2 border-blue-500/30 bg-blue-500/5">
                                <Loader2 className="w-4 h-4 animate-spin text-blue-500" />
                                <span className="text-[11px] font-bold text-blue-400">Generating deep analysis...</span>
                              </div>
                            )}
                            {demoAiDone && (
                              <div className="space-y-2 animate-fadeIn">
                                <div className="rounded-xl bg-emerald-500/10 border border-emerald-500/20 p-3">
                                  <div className="text-[10px] font-bold text-emerald-400 mb-1 flex items-center gap-1"><CheckCircle2 className="w-3 h-3" /> Why Correct</div>
                                  <p className="text-[11px] leading-relaxed text-slate-300">{demoQuestion.explanation}</p>
                                </div>
                                <div className="rounded-xl bg-amber-500/10 border border-amber-500/20 p-3">
                                  <div className="text-[10px] font-bold text-amber-400 mb-1">Exam Tip</div>
                                  <p className="text-[11px] leading-relaxed text-slate-300">This is a high-yield UPSC CMS pattern. Questions on emergency protocols and first-line management appear every year.</p>
                                </div>
                              </div>
                            )}

                            <div className="flex justify-end pt-1 border-t border-border/50">
                              <button
                                onClick={() => {
                                  setDemoGenerated(false);
                                  setDemoAnswer(null);
                                  setDemoAiDone(false);
                                  setDemoAiLoading(false);
                                }}
                                className="text-[10px] text-cyan-500 font-bold hover:underline cursor-pointer bg-transparent border-0"
                              >
                                Try Another Subject
                              </button>
                            </div>
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                </div>
              </div>
            </div>
          </div>

        </div>
      </section>

      {/* ============================================
          TESTIMONIALS
      ============================================ */}
      <section className="relative border-t-2 border-border/40 bg-muted/5 py-24 px-4 sm:px-6 overflow-hidden">
        <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_bottom,_var(--tw-gradient-stops))] from-primary/5 via-background to-background" />

        <div className="mx-auto max-w-7xl relative">
          <div className="text-center max-w-3xl mx-auto mb-16 space-y-4">
            <div className="inline-flex items-center gap-2 rounded-full border border-primary/20 bg-primary/5 px-4 py-1.5 text-xs font-bold uppercase tracking-[0.15em] text-primary">
              Aspirant Reviews
            </div>
            <h2 className="font-display text-3xl font-extrabold text-foreground sm:text-4xl lg:text-5xl tracking-tight">
              Loved by medical students preparing for UPSC CMS
            </h2>
            <p className="text-sm md:text-base text-muted-foreground">
              See how doctors and residents across top-tier institutions are using our platform to boost their clinical scores and daily prep streaks.
            </p>
          </div>

          <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
            {[
              {
                quote: "The Spaced Repetition flashcards and AI explanations are elite. I was able to memorize complex drug interactions and clinical classification codes in days rather than weeks. Best resource for UPSC CMS and NEET PG.",
                title: "Verified PG Resident",
                inst: "AIIMS Delhi",
                rating: 5
              },
              {
                quote: "Having unlimited AI tutor support is a game-changer. Whenever I get stuck on a difficult clinical case study, the explanations break down the 'why' behind each option. It has significantly improved my diagnostics.",
                title: "Verified MBBS Intern",
                inst: "Maulana Azad Medical College (MAMC)",
                rating: 5
              },
              {
                quote: "The yearly CMS QBank is extremely clean. I love that there are exactly 240 questions for every year. No duplicates, no missing options, and the Roman numeral options are beautifully formatted.",
                title: "Verified Medical Officer Track",
                inst: "KGMU Lucknow",
                rating: 5
              },
              {
                quote: "Honestly, the ₹199 price is a steal. You get direct textbook page mapping, top teacher revision sheets, and unlimited AI tutoring without any tokens. It easily replaces multiple expensive subscriptions.",
                title: "Verified Aspirant",
                inst: "CMC Vellore",
                rating: 5
              },
              {
                quote: "Mock simulations feel incredibly close to the actual exam software. The timer and negative marking prepare you mentally. My score estimates have gone up from 55% to 74% in just two weeks.",
                title: "Verified Resident Doctor",
                inst: "JIPMER Puducherry",
                rating: 5
              },
              {
                quote: "Extremely helpful customer support. I requested standard medical textbook mapping for pediatric guidelines, and they added it within a few hours. The curated notes are super high yield.",
                title: "Verified MO Aspirant",
                inst: "Seth GS Medical College",
                rating: 5
              }
            ].map((item, idx) => (
              <div
                key={idx}
                className="group relative rounded-3xl border-2 border-border/60 bg-card/40 p-6 backdrop-blur-xl transition-all duration-500 hover:scale-[1.02] hover:border-primary/30 hover:shadow-2xl hover:shadow-primary/10 overflow-hidden"
              >
                {/* Animated border glow */}
                <div className="absolute -inset-1 bg-linear-to-r from-primary/10 via-transparent to-primary/10 rounded-3xl blur-xl opacity-0 group-hover:opacity-100 transition-opacity duration-500 -z-10" />

                <div className="flex gap-1 text-amber-500 mb-4">
                  {Array.from({ length: item.rating }).map((_, i) => (
                    <svg key={i} className="w-4 h-4 fill-current text-amber-400 drop-shadow-sm" viewBox="0 0 20 20">
                      <path d="M9.049 2.927c.3-.921 1.603-.921 1.902 0l1.07 3.292a1 1 0 00.95.69h3.462c.969 0 1.371 1.24.588 1.81l-2.8 2.034a1 1 0 00-.364 1.118l1.07 3.292c.3.921-.755 1.688-1.54 1.118l-2.8-2.034a1 1 0 00-1.175 0l-2.8 2.034c-.784.57-1.838-.197-1.539-1.118l1.07-3.292a1 1 0 00-.364-1.118L2.98 8.72c-.783-.57-.38-1.81.588-1.81h3.461a1 1 0 00.951-.69l1.07-3.292z" />
                    </svg>
                  ))}
                </div>
                <p className="text-sm text-slate-300 leading-relaxed">
                  &quot;{item.quote}&quot;
                </p>
                <div className="border-t border-slate-800/60 mt-4 pt-3 flex items-center gap-3">
                  <div className="h-8 w-8 rounded-full bg-primary/10 border-2 border-primary/20 flex items-center justify-center font-bold text-xs text-primary">
                    ⚕️
                  </div>
                  <div>
                    <h4 className="text-xs font-bold text-white">{item.title}</h4>
                    <p className="text-[10px] text-muted-foreground">{item.inst}</p>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ============================================
          PREMIUM PRICING
      ============================================ */}
      <section className="relative px-4 py-24 sm:px-6 overflow-hidden">
        <div className="mx-auto max-w-5xl">
          <div className="relative group">
            {/* Animated glow */}
            <div className="absolute -inset-1 bg-linear-to-r from-amber-500/30 via-purple-500/30 to-cyan-500/30 rounded-3xl blur-2xl opacity-60 group-hover:opacity-80 transition-opacity duration-500" />

            <div className="relative rounded-3xl border-2 border-amber-500/30 bg-slate-950 text-white p-8 sm:p-12 md:p-16 shadow-2xl overflow-hidden">
              {/* Background mesh */}
              <div className="absolute right-0 top-0 h-100 w-100 bg-linear-to-br from-amber-500/10 to-yellow-500/15 rounded-full blur-3xl opacity-60 pointer-events-none" />
              <div className="absolute left-0 bottom-0 h-100 w-100 bg-linear-to-tr from-cyan-500/10 to-blue-500/15 rounded-full blur-3xl opacity-60 pointer-events-none" />

              <div className="relative z-10 grid gap-12 lg:grid-cols-2 items-center">
                <div className="space-y-6 text-left">
                  <Badge className="bg-amber-500/15 text-amber-400 hover:bg-amber-500/20 border border-amber-500/30 font-bold uppercase tracking-wider text-[10px] py-1 px-3">
                    <Crown className="w-3.5 h-3.5 mr-1 inline" /> Early Bird Special Pass
                  </Badge>
                  <h2 className="font-display text-3xl font-black md:text-5xl text-white tracking-tight leading-tight">
                    One Place for Complete UPSC CMS & NEET PG
                  </h2>
                  <p className="text-slate-400 text-sm md:text-base leading-relaxed">
                    Unlock our elite repository of curated materials, unlimited AI tutor usage, and direct faculty support designed specifically for medical officers.
                  </p>

                  <div className="grid gap-4 sm:grid-cols-2 pt-2">
                    {[
                      { title: "Unlimited AI Tutor", desc: "Ask unlimited medical questions. Access full clinical analyses, mnemonics, and concepts instantly." },
                      { title: "Top Curator Hand-notes", desc: "Access high-yield revision summaries, flowcharts, and cheat sheets." },
                      { title: "Renowned Faculty Doubts", desc: "Direct channel to clear clinical doubts with state and national experts." },
                      { title: "Full QBank & Simulations", desc: "1,440+ verified year-wise PYQs (2018-2025) and custom mock exams." }
                    ].map((item, i) => (
                      <div key={i} className="flex gap-3">
                        <CheckCircle2 className="h-5 w-5 text-amber-500 shrink-0 mt-0.5" />
                        <div>
                          <h4 className="font-bold text-sm text-slate-200">{item.title}</h4>
                          <p className="text-xs text-slate-400 mt-0.5">{item.desc}</p>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>

                <div className="flex justify-center">
                  <div className="w-full max-w-sm rounded-3xl border-2 border-amber-500/30 bg-slate-900/80 p-8 text-center backdrop-blur-xl relative overflow-hidden">
                    <div className="absolute top-0 right-0 w-32 h-32 bg-amber-500/10 rounded-full blur-3xl pointer-events-none" />
                    <span className="text-xs font-bold text-amber-400 uppercase tracking-widest">Premium Pass</span>

                    <div className="mt-4 flex items-baseline justify-center gap-2">
                      <span className="text-6xl font-black text-white">₹199</span>
                      <span className="text-lg line-through text-slate-500">₹10,000</span>
                    </div>
                    <p className="text-[10px] text-amber-400/90 font-bold mt-1 tracking-wide">98% Launch Offer — Price Rising to ₹10K+ Soon</p>

                    <ul className="mt-6 space-y-3.5 text-left text-xs text-slate-300 border-t border-slate-800 pt-6">
                      <li className="flex items-center gap-2">
                        <Zap className="w-3.5 h-3.5 text-amber-500" /> Unlimited AI tutor usage (No tokens)
                      </li>
                      <li className="flex items-center gap-2">
                        <Zap className="w-3.5 h-3.5 text-amber-500" /> Handwritten study materials
                      </li>
                      <li className="flex items-center gap-2">
                        <Zap className="w-3.5 h-3.5 text-amber-500" /> Renowned faculty doubt support
                      </li>
                      <li className="flex items-center gap-2">
                        <Zap className="w-3.5 h-3.5 text-amber-500" /> All reference books & guides
                      </li>
                    </ul>

                    <Button size="xl" asChild className="w-full mt-8 rounded-2xl bg-linear-to-r from-amber-500 to-yellow-500 hover:from-amber-600 hover:to-yellow-600 text-black font-extrabold shadow-lg shadow-amber-500/20 py-4 transition-transform active:scale-95">
                      <Link href="/subscription">
                        Claim Premium Offer Now <ArrowRight className="w-4 h-4 ml-1" />
                      </Link>
                    </Button>
                    <span className="block text-[9px] text-slate-500 mt-3">Secure payment via Razorpay. Cancel anytime.</span>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* ============================================
          CAMPUS MOMENTUM + STATS
      ============================================ */}
      <section className="px-4 sm:px-6 py-24">
        <div className="mx-auto max-w-7xl space-y-16">

          {/* Campus Momentum */}
          <div className="relative group w-full">
            <div className="absolute -inset-1 bg-linear-to-tr from-emerald-500 via-blue-500 to-indigo-500 opacity-20 blur-2xl transition-all group-hover:opacity-30 rounded-[2.5rem]" />
            <div className="relative rounded-[2.5rem] border-2 border-border/80 bg-card/60 p-6 md:p-10 shadow-2xl backdrop-blur-xl space-y-6 overflow-hidden">
              <div className="absolute right-0 top-0 h-40 w-40 bg-emerald-500/5 rounded-full blur-3xl" />

              <div className="flex flex-wrap items-center justify-between gap-4 border-b border-border/50 pb-5">
                <div className="space-y-1 text-left">
                  <h3 className="font-display text-xl font-extrabold text-foreground">Campus Momentum</h3>
                  <p className="text-xs text-muted-foreground">Students and residents from leading medical institutions prep here.</p>
                </div>
                <Badge className="bg-emerald-600 text-white hover:bg-emerald-600 px-4 py-1.5 rounded-full font-bold shadow-lg shadow-emerald-600/20">
                  2,900+ active this week
                </Badge>
              </div>

              <div className="grid gap-3 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-6">
                {campuses.map((campus) => (
                  <div
                    key={campus}
                    className="rounded-xl border-2 border-border/60 bg-muted/20 px-4 py-3 text-xs font-semibold text-center text-foreground hover:bg-emerald-500/10 hover:border-emerald-500/30 transition-all"
                  >
                    {campus}
                  </div>
                ))}
              </div>

              <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4 pt-2">
                {communityProfiles.map((profile) => (
                  <div key={profile.name} className="rounded-2xl border-2 border-border/50 bg-muted/15 p-4 space-y-1.5 relative hover:border-primary/35 hover:bg-primary/5 transition-all text-left">
                    <span className="absolute top-4 right-4 text-[9px] font-bold text-emerald-600 dark:text-emerald-400 bg-emerald-500/10 px-2 py-0.5 rounded-full">
                      {profile.badge}
                    </span>
                    <p className="text-sm font-extrabold text-foreground">{profile.name}</p>
                    <p className="text-xs text-muted-foreground">{profile.college}</p>
                    <p className="pt-1 text-xs font-semibold text-emerald-600 dark:text-emerald-400 flex items-center gap-1">
                      <span className="h-1.5 w-1.5 rounded-full bg-emerald-500 animate-pulse" />
                      {profile.progress}
                    </p>
                  </div>
                ))}
              </div>
            </div>
          </div>

          {/* Stats Strip */}
          <div className="grid grid-cols-2 gap-4 md:grid-cols-4 pt-8 border-t-2 border-border/50">
            {stats.map((stat, i) => (
              <div key={i} className="flex flex-col items-center text-center p-6 rounded-2xl border-2 border-border/60 bg-card/40 backdrop-blur-sm hover:border-primary/30 hover:bg-primary/5 transition-all duration-300 hover:-translate-y-1">
                <div className="h-12 w-12 rounded-xl bg-primary/5 flex items-center justify-center mb-3 border-2 border-primary/10">
                  <stat.icon className="h-6 w-6 text-primary" />
                </div>
                <span className="text-4xl font-extrabold text-foreground tracking-tight">{stat.value}</span>
                <span className="text-sm font-bold text-foreground mt-1">{stat.label}</span>
                <span className="text-xs text-muted-foreground mt-0.5">{stat.desc}</span>
              </div>
            ))}
          </div>

          {/* Target Market Pills */}
          <div className="flex flex-wrap justify-center items-center gap-2 p-4 bg-muted/10 border-2 border-border/40 rounded-2xl">
            <span className="text-[10px] uppercase font-extrabold text-muted-foreground tracking-wider mr-2">Core System Alignment:</span>
            {['UPSC CMS Pattern Aligned', 'NEET PG Revision Friendly', 'No Credit Card Required', 'Free Daily Tokens'].map((pill, i) => (
              <span key={i} className="rounded-full border-2 border-border/60 bg-card px-3.5 py-1 text-xs font-semibold text-foreground shadow-sm hover:border-primary/30 hover:bg-primary/5 transition-all">
                {pill}
              </span>
            ))}
          </div>
        </div>
      </section>

      {/* ============================================
          SUBJECTS SECTION
      ============================================ */}
      <section className="px-4 py-24 sm:px-6 relative overflow-hidden border-t-2 border-border/40">
        <div className="absolute left-1/2 top-1/2 -z-10 h-96 w-96 bg-indigo-500/5 rounded-full blur-3xl" />

        <div className="mx-auto max-w-5xl space-y-12">
          <div className="text-center space-y-3">
            <h2 className="font-display text-3xl font-extrabold text-foreground tracking-tight sm:text-4xl">
              All 5 UPSC CMS Subjects Covered
            </h2>
            <p className="text-muted-foreground max-w-lg mx-auto">
              Paper 1 + Paper 2 complete exam coverage with high-yield clinical question depth.
            </p>
          </div>

          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {subjects.map((s, i) => (
              <div key={i} className="group relative rounded-2xl border-2 border-border/80 bg-card/60 p-5 backdrop-blur-sm transition-all duration-300 hover:border-primary/40 hover:-translate-y-1 hover:shadow-xl hover:shadow-primary/10 overflow-hidden">
                <div className="absolute inset-0 bg-linear-to-br from-emerald-500/5 to-transparent opacity-0 group-hover:opacity-100 transition-opacity duration-300" />
                <div className="relative flex items-center gap-3">
                  <div className="h-8 w-8 rounded-lg bg-emerald-500/10 flex items-center justify-center border-2 border-emerald-500/20 transition-colors group-hover:bg-emerald-500/20">
                    <CheckCircle2 className="w-4 h-4 text-emerald-500" />
                  </div>
                  <span className="font-bold text-sm text-foreground">{s}</span>
                </div>
              </div>
            ))}
            <div className="group relative rounded-2xl border-2 border-border/80 bg-card/60 p-5 backdrop-blur-sm transition-all duration-300 hover:border-primary/40 hover:-translate-y-1 hover:shadow-xl hover:shadow-primary/10 overflow-hidden">
              <div className="absolute inset-0 bg-linear-to-br from-blue-500/5 to-transparent opacity-0 group-hover:opacity-100 transition-opacity duration-300" />
              <div className="relative flex items-center gap-3">
                <div className="h-8 w-8 rounded-lg bg-blue-500/10 flex items-center justify-center border-2 border-blue-500/20 transition-colors group-hover:bg-blue-500/20">
                  <Sparkles className="w-4 h-4 text-blue-500" />
                </div>
                <span className="font-bold text-sm text-foreground">AI-Powered Analytics</span>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* ============================================
          WHY CRACKCMS
      ============================================ */}
      <section className="border-t-2 border-border/60 bg-muted/10 px-4 py-24 sm:px-6">
        <div className="mx-auto max-w-5xl space-y-12">
          <div className="text-center">
            <h2 className="font-display text-3xl font-extrabold text-foreground tracking-tight sm:text-4xl">
              Why Doctors Prefer This System
            </h2>
          </div>

          <div className="grid md:grid-cols-3 gap-8">
            {[
              { icon: Clock3, title: 'Workflow-First', desc: 'Organized systematically around what you need to do now, next, and what demands review focus.' },
              { icon: Users, title: 'Doctor-Centric', desc: 'Features, labels, and explanations align with clinical practice, rather than generic exam templates.' },
              { icon: TrendingUp, title: 'Continuous Optimization', desc: 'Data-driven insights isolate and narrow down your weakest diagnostic areas over time.' },
            ].map((item, i) => (
              <div key={i} className="group relative rounded-3xl border-2 border-border/60 bg-card/40 p-8 text-center backdrop-blur-xl transition-all duration-500 hover:scale-[1.02] hover:border-primary/30 hover:shadow-2xl hover:shadow-primary/10 overflow-hidden">
                <div className="absolute inset-0 bg-linear-to-br from-primary/5 to-transparent opacity-0 group-hover:opacity-100 transition-opacity duration-500" />
                <div className="relative space-y-4">
                  <div className="w-16 h-16 rounded-2xl flex items-center justify-center mx-auto bg-primary/10 border-2 border-primary/20 transition-transform group-hover:scale-110 group-hover:rotate-3 shadow-lg">
                    <item.icon className="w-7 h-7 text-primary" />
                  </div>
                  <h3 className="font-bold text-foreground text-base">{item.title}</h3>
                  <p className="text-sm text-muted-foreground leading-relaxed">{item.desc}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ============================================
          FINAL CTA
      ============================================ */}
      <section className="px-4 pb-24 sm:px-6 relative overflow-hidden">
        <div className="absolute left-1/2 top-1/2 -z-10 h-125 w-125 -translate-x-1/2 -translate-y-1/2 bg-blue-600/10 rounded-full blur-3xl" />

        <Card className="mx-auto max-w-4xl border-2 border-primary/20 bg-slate-950 text-white rounded-[2.5rem] relative overflow-hidden shadow-2xl">
          {/* Neon gradient background mesh */}
          <div className="absolute right-0 top-0 h-96 w-96 bg-linear-to-br from-indigo-500/20 to-teal-500/20 rounded-full blur-3xl opacity-60" />
          <div className="absolute left-0 bottom-0 h-96 w-96 bg-linear-to-tr from-blue-500/20 to-rose-500/20 rounded-full blur-3xl opacity-60" />

          <CardContent className="p-10 md:p-16 text-center space-y-6 relative z-10">
            <div className="h-16 w-16 rounded-2xl bg-white/10 flex items-center justify-center mx-auto border-2 border-white/20 shadow-xl">
              <GraduationCap className="w-8 h-8 text-blue-400" />
            </div>

            <h2 className="font-display text-3xl md:text-4xl font-extrabold tracking-tight text-white leading-tight">
              Ready to Build an Exam-Ready Routine?
            </h2>

            <p className="text-slate-400 max-w-lg mx-auto text-base">
              Join thousands of medical graduates leveraging an AI + doctor prep workflow to study faster, cleaner, and with optimized memory retention.
            </p>

            <div className="pt-4">
              <Button size="xl" asChild className="rounded-2xl bg-white text-slate-950 hover:bg-slate-100 font-bold transition-all px-8 py-4 shadow-xl active:scale-95">
                <Link href={isAuthenticated ? '/dashboard' : '/register'}>
                  Get Started Free <ArrowRight className="ml-1.5 w-5 h-5 text-slate-950" />
                </Link>
              </Button>
            </div>
          </CardContent>
        </Card>
      </section>

      {/* ============================================
          EXAM MICROSITES
      ============================================ */}
      <section id="exam-microsites" className="px-4 sm:px-6 py-16 md:py-20 border-t-2 border-border/60 bg-muted/10">
        <div className="mx-auto max-w-6xl">
          <div className="text-center mb-10">
            <Badge variant="outline" className="mb-4 border-primary/30 text-primary">Three Exams. One Workflow.</Badge>
            <h2 className="font-display text-3xl md:text-4xl font-extrabold tracking-tight text-foreground">
              Pick your exam microsite
            </h2>
            <p className="mt-3 text-sm md:text-base text-muted-foreground max-w-2xl mx-auto">
              Each exam gets its own dedicated experience — different subjects,
              different PYQs, different mocks — but the same AI tutor and analytics you trust.
            </p>
          </div>
          <div className="grid md:grid-cols-3 gap-5">
            {[
              {
                href: '/exams/cms',
                badge: 'UPSC',
                name: 'UPSC CMS',
                desc: 'Combined Medical Services. 2,000+ PYQs from 2018-2025. Paper I (Medicine + Paediatrics) and Paper II (Surgery + OBG + PSM).',
                gradient: 'from-cyan-600 to-blue-700',
                icon: '🩺',
              },
              {
                href: '/exams/neet-pg',
                badge: 'NEET PG',
                name: 'NEET PG',
                desc: 'Postgraduate entrance. 1,200+ PYQs across 19 PG subjects (2020-2025). All-India 50% quota + State quota prep.',
                gradient: 'from-emerald-600 to-teal-700',
                icon: '🎓',
              },
              {
                href: '/exams/usmle',
                badge: 'USMLE',
                name: 'USMLE',
                desc: 'Step 1 + Step 2 CK. High-yield lists, NBME-style vignettes. Beta access — join the waitlist.',
                gradient: 'from-indigo-600 to-violet-700',
                icon: '🌎',
              },
            ].map((c) => (
              <Link key={c.href} href={c.href}
                className="group relative rounded-3xl border-2 border-border/60 bg-card/80 overflow-hidden transition-all hover:scale-[1.02] hover:shadow-2xl hover:shadow-primary/10">
                <div className={`bg-linear-to-br ${c.gradient} text-white p-6 relative overflow-hidden`}>
                  <div className="absolute inset-0 bg-linear-to-t from-black/20 to-transparent" />
                  <div className="relative flex items-center justify-between mb-3">
                    <Badge className="bg-white/15 text-white border-2 border-white/20 backdrop-blur-sm">{c.badge}</Badge>
                    <span className="text-3xl">{c.icon}</span>
                  </div>
                  <h3 className="text-2xl font-extrabold">{c.name}</h3>
                </div>
                <div className="p-5">
                  <p className="text-sm text-muted-foreground leading-relaxed min-h-20">{c.desc}</p>
                  <div className="mt-3 flex items-center text-sm font-semibold text-primary group-hover:gap-2 transition-all">
                    Open microsite <ArrowRight className="ml-1 w-4 h-4 group-hover:translate-x-1 transition-transform" />
                  </div>
                </div>
              </Link>
            ))}
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="border-t-2 border-border/60 bg-muted/10 px-4 py-12 sm:px-6">
        <div className="mx-auto max-w-6xl text-center">
          <BrandMark href="/" compact showTagline={true} />
          <p className="mt-4 text-xs text-muted-foreground">
            © {new Date().getFullYear()} {siteName}. All rights reserved.
          </p>
        </div>
      </footer>
    </div>
  );
}
