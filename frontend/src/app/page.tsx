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

  // 1. PYQ Atlas Widget
  const [pyqAnswer, setPyqAnswer] = useState<string | null>(null);
  const [showPyqExplanation, setShowPyqExplanation] = useState(false);
  const [pyqAiLoading, setPyqAiLoading] = useState(false);
  const [pyqAiDone, setPyqAiDone] = useState(false);

  // 2. AI Tutor Widget
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

  // 3. Exam Engine Widget
  const [examTimer, setExamTimer] = useState(6291); // 1h 44m 51s
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

  // 4. Rapid Recall Mnemonic Flip Widget
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

  // 5. Question Generator Widget states and handlers
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
    
    // Simulate AI Generation delay
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
        // Medicine
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
    <div className="min-h-screen bg-transparent font-sans">
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
      {/* Exam Countdown Banner */}
      <ExamCountdown />

      {/* Navbar */}
      <nav className="sticky top-0 z-50 border-b border-border/60 bg-background/80 backdrop-blur-xl transition-all">
        <div className="mx-auto flex h-16 max-w-6xl items-center justify-between px-4 sm:px-6">
          <BrandMark href="/" compact showTagline={false} />
          <div className="flex items-center gap-3">
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
                <Button asChild className="rounded-xl font-semibold shadow-md shadow-primary/15 transition-transform active:scale-95">
                  <Link href="/register">
                    Start Free <ChevronRight className="ml-1 w-4 h-4" />
                  </Link>
                </Button>
              </>
            )}
          </div>
        </div>
      </nav>

      {/* Hero Section */}
      <section className="relative mx-auto max-w-7xl px-4 pb-20 pt-16 sm:px-6 overflow-hidden">
        {/* Glow decorative effects */}
        <div className="absolute left-1/4 top-10 -z-10 h-72 w-72 rounded-full bg-blue-500/10 blur-3xl dark:bg-blue-500/5" />
        <div className="absolute right-1/4 bottom-10 -z-10 h-96 w-96 rounded-full bg-teal-500/10 blur-3xl dark:bg-teal-500/5" />

        <div className="flex flex-col gap-10">
          {/* Header block with Logo and Title */}
          <div className="space-y-6 max-w-5xl mx-auto w-full">
            <Badge 
              variant="secondary" 
              className="inline-flex items-center rounded-full border border-primary/10 bg-primary/5 px-4 py-1.5 text-xs font-bold uppercase tracking-[0.12em] text-primary"
            >
              <Sparkles className="w-3.5 h-3.5 mr-2 text-primary" />
              Doctor-first prep. Smart study platform.
            </Badge>

            <div className="flex flex-col md:flex-row gap-6 items-center md:items-start">
              {/* CMS Circle Logo */}
              <div className="relative h-32 w-32 md:h-48 md:w-48 lg:h-56 lg:w-56 shrink-0 overflow-hidden rounded-full border-2 border-amber-500/30 bg-slate-950 shadow-xl shadow-amber-500/10">
                <Image 
                  src="/cms-circle-logo.png" 
                  alt="CMS Circle Logo" 
                  fill
                  sizes="(max-width: 768px) 128px, (max-width: 1024px) 192px, 224px"
                  className="object-cover rounded-full"
                  priority
                />
              </div>

              {/* Title, Description & CTAs */}
              <div className="space-y-4 flex-1">
                <h1 className="font-display text-4xl font-extrabold leading-[1.08] tracking-tight text-foreground sm:text-5xl lg:text-6xl text-left">
                  <span className="bg-linear-to-r from-blue-600 via-indigo-600 to-teal-500 bg-clip-text text-transparent dark:from-blue-400 dark:via-indigo-300 dark:to-teal-400">AI Powered</span> UPSC CMS Platform
                </h1>
                
                <p className="max-w-3xl text-lg leading-relaxed text-muted-foreground text-left">
                  Build daily clinical consistency with an integrated medical prep operating system. 
                  Equipped with a smart question bank, AI tutoring, hyper-realistic simulated mock tests, and smart weak-area analytics.
                </p>

                <div className="flex flex-col items-start gap-4 sm:flex-row sm:items-center pt-2">
                  <Button size="xl" asChild className="w-full rounded-2xl sm:w-auto font-semibold shadow-lg shadow-primary/15 transition-all hover:shadow-xl hover:shadow-primary/20">
                    <Link href={isAuthenticated ? '/dashboard' : '/register'}>
                      Start Preparing
                      <ChevronRight className="ml-1.5 w-5 h-5" />
                    </Link>
                  </Button>
                  <Button size="xl" variant="outline" asChild className="w-full rounded-2xl sm:w-auto font-semibold bg-background hover:bg-muted/50">
                    <Link href="#features">Explore Platform</Link>
                  </Button>
                </div>
              </div>
            </div>

            <div className="flex flex-wrap justify-center gap-2.5 pt-4 w-full">
              <div className="inline-flex items-center gap-2 rounded-full border border-border/80 bg-card/65 px-4 py-2 text-xs font-semibold text-muted-foreground shadow-sm">
                <Clock3 className="h-4 w-4 text-blue-500" />
                Daily workflow optimized
              </div>
              <div className="inline-flex items-center gap-2 rounded-full border border-border/80 bg-card/65 px-4 py-2 text-xs font-semibold text-muted-foreground shadow-sm">
                <Target className="h-4 w-4 text-teal-500" />
                Exam-style reasoning
              </div>
              <div className="inline-flex items-center gap-2 rounded-full border border-border/80 bg-card/65 px-4 py-2 text-xs font-semibold text-muted-foreground shadow-sm">
                <TrendingUp className="h-4 w-4 text-indigo-500" />
                Outcome-focused analytics
              </div>
            </div>
          </div>

      {/* Downward Page Motion Feature Showcase (Decluttering + Side-by-side Storytelling) */}
      <section id="features" className="border-t border-border/60 bg-muted/20 py-24 px-4 sm:px-6">
        <div className="mx-auto max-w-6xl space-y-32">
          
          {/* Header block */}
          <div className="text-center max-w-2xl mx-auto space-y-4">
            <h2 className="font-display text-3xl font-extrabold text-foreground sm:text-4xl tracking-tight">
              Everything Needed for High-Performance CMS Prep
            </h2>
            <p className="text-lg text-muted-foreground">
              We broken down exam preparation into modular, specialized engines that work together seamlessly. Explore them live below.
            </p>
            <div className="h-1.5 w-16 bg-blue-500 rounded-full mx-auto" />
          </div>

          {/* Feature 1: Clinical PYQ Atlas (Interactive MCQ) */}
          <div className="relative group/feat rounded-[2.5rem] border border-emerald-500/20 dark:border-emerald-500/10 bg-emerald-500/2 dark:bg-emerald-950/4 p-6 sm:p-8 md:p-12 shadow-sm hover:border-emerald-500/35 transition-all duration-300 overflow-hidden">
            <div className="absolute right-0 bottom-0 -z-10 h-72 w-72 rounded-full bg-emerald-500/10 blur-3xl opacity-60" />
            <div className="grid gap-12 lg:grid-cols-12 items-center relative z-10">
              <div className="lg:col-span-6 space-y-6">
                <Badge className="bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 hover:bg-emerald-500/15 border-0 font-bold uppercase tracking-wider text-[10px]">
                  FEATURE DEEP DIVE
                </Badge>
                <h3 className="font-display text-2xl font-extrabold text-foreground sm:text-3xl leading-tight">
                  Clinical PYQ Atlas
                </h3>
                <p className="text-base text-muted-foreground leading-relaxed">
                  Unlock 2000+ active past questions from UPSC CMS (2018-2025). Every question is systematically indexed by subject, topic cluster, and difficulty grade, and enriched with voter-consensus answers and high-yield references.
                </p>
                
                <ul className="space-y-3 font-semibold text-foreground text-sm">
                  <li className="flex items-center gap-2.5">
                    <CheckCircle2 className="h-4.5 w-4.5 text-emerald-500 shrink-0" />
                    Double-verified medical consensus answer keys
                  </li>
                  <li className="flex items-center gap-2.5">
                    <CheckCircle2 className="h-4.5 w-4.5 text-emerald-500 shrink-0" />
                    Direct cross-referencing to core medical textbooks
                  </li>
                  <li className="flex items-center gap-2.5">
                    <CheckCircle2 className="h-4.5 w-4.5 text-emerald-500 shrink-0" />
                    Keyboard shortcuts for lightning-fast answer flow
                  </li>
                </ul>
              </div>

              {/* Interactive MCQ Mock Widget */}
              <div className="lg:col-span-6">
                <div className="rounded-3xl border border-border/80 bg-card p-6 shadow-xl relative">
                  <span className="absolute -top-3 left-6 rounded-full bg-emerald-500 text-white text-[10px] font-bold px-3 py-1 uppercase tracking-wider">
                    Interactive Demo
                  </span>
                  
                  <div className="space-y-4 pt-2">
                    <div className="flex justify-between items-center text-xs font-bold text-muted-foreground">
                      <span>UPSC CMS 2024 Paper 1</span>
                      <span className="text-emerald-600">Question #182</span>
                    </div>

                    <p className="text-sm font-bold text-foreground leading-relaxed">
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
                        let btnStyle = "border-border/60 hover:border-emerald-500/50 hover:bg-muted/10";
                        
                        if (pyqAnswer !== null) {
                          if (isCorrect) {
                            btnStyle = "border-emerald-500 bg-emerald-500/5 text-emerald-900 dark:text-emerald-300";
                          } else if (isSelected) {
                            btnStyle = "border-red-500 bg-red-50/5 text-red-900 dark:text-red-400";
                          } else {
                            btnStyle = "border-border/40 opacity-60";
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
                            className={`w-full text-left rounded-xl border p-3.5 text-xs font-semibold flex items-center gap-3 transition-all ${btnStyle}`}
                          >
                            <span className={`h-6 w-6 rounded-full flex items-center justify-center shrink-0 border text-xs font-extrabold
                              ${isSelected && isCorrect ? 'bg-emerald-500 text-white border-emerald-500' : ''}
                              ${isSelected && !isCorrect ? 'bg-red-500 text-white border-red-500' : ''}
                              ${!isSelected && isCorrect && pyqAnswer !== null ? 'bg-emerald-500 text-white border-emerald-500' : 'bg-muted/30 border-border'}
                            `}>
                              {opt.key}
                            </span>
                            <span>{opt.text}</span>
                          </button>
                        );
                      })}
                    </div>

                    {showPyqExplanation && (
                      <div className="space-y-2 animate-fadeIn">
                        <div className="rounded-xl bg-muted/40 p-3 border border-emerald-500/10 space-y-1.5">
                          <div className="flex items-center gap-1.5 text-xs font-bold text-emerald-600">
                            <Sparkles className="h-3.5 w-3.5" />
                            AI Explanation Consensus:
                          </div>
                          <p className="text-[11px] leading-relaxed text-muted-foreground">
                            In an acute anterior wall STEMI (V1-V4 elevation) presenting to a non-PCI center, immediate thrombolytic therapy is indicated if primary PCI delay exceeds 120 minutes. Tenecteplase is preferred due to high fibrin specificity.
                          </p>
                        </div>

                        {/* Generate AI Analysis button */}
                        {!pyqAiDone && !pyqAiLoading && (
                          <button
                            onClick={() => { setPyqAiLoading(true); setTimeout(() => { setPyqAiLoading(false); setPyqAiDone(true); }, 1800); }}
                            className="w-full rounded-xl border border-blue-200 bg-blue-50/50 dark:bg-blue-900/10 dark:border-blue-800/50 p-3 flex items-center justify-center gap-2 cursor-pointer transition-all hover:bg-blue-50 dark:hover:bg-blue-900/20 text-xs font-bold text-blue-700 dark:text-blue-300"
                          >
                            <Brain className="w-4 h-4" /> Generate AI Analysis
                          </button>
                        )}
                        {pyqAiLoading && (
                          <div className="flex items-center justify-center gap-2 p-3 rounded-xl border border-blue-200 bg-blue-50/30 dark:bg-blue-900/10 animate-pulse">
                            <Loader2 className="w-4 h-4 animate-spin text-blue-500" />
                            <span className="text-[11px] font-bold text-blue-600">Analyzing with AI...</span>
                          </div>
                        )}
                        {pyqAiDone && (
                          <div className="space-y-2 animate-fadeIn">
                            <div className="rounded-xl bg-emerald-50/50 dark:bg-emerald-950/10 border border-emerald-200 dark:border-emerald-900/30 p-3">
                              <div className="text-[10px] font-bold text-emerald-600 mb-1 flex items-center gap-1"><CheckCircle2 className="w-3 h-3" /> Why Correct</div>
                              <p className="text-[11px] leading-relaxed text-muted-foreground">Thrombolytic therapy (specifically Tenecteplase) is the gold standard for STEMI reperfusion when primary PCI cannot be performed within the 120-minute door-to-balloon window. It works by dissolving the coronary thrombus via plasminogen activation.</p>
                            </div>
                            <div className="rounded-xl bg-amber-50/50 dark:bg-amber-950/10 border border-amber-200 dark:border-amber-900/30 p-3">
                              <div className="text-[10px] font-bold text-amber-600 mb-1">🧠 Mnemonic</div>
                              <p className="text-[11px] leading-relaxed text-muted-foreground"><strong>STEMI-T</strong>: ST elevation → Emergency → Must reperfuse → Intervention (PCI or Thrombolysis) → Tenecteplase if no PCI</p>
                            </div>
                            <div className="rounded-xl bg-blue-50/50 dark:bg-blue-950/10 border border-blue-200 dark:border-blue-900/30 p-3">
                              <div className="text-[10px] font-bold text-blue-600 mb-1">📖 Textbook</div>
                              <p className="text-[11px] text-muted-foreground">Harrison&apos;s Principles of Internal Medicine, Ch. 273, Page 1453–1460</p>
                            </div>
                          </div>
                        )}

                        <div className="flex justify-between items-center pt-1 text-[10px] text-muted-foreground border-t border-border/50">
                          <span>Textbook: <strong>Harrison&apos;s Cardiology, Ch. 273</strong></span>
                          <button 
                            onClick={() => {
                              setPyqAnswer(null);
                              setShowPyqExplanation(false);
                              setPyqAiDone(false);
                              setPyqAiLoading(false);
                            }}
                            className="text-primary font-bold hover:underline"
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

          {/* Feature 2: Doctor-Grade AI Tutor (Interactive Chat RAG) */}
          <div className="relative group/feat rounded-[2.5rem] border border-blue-500/20 dark:border-blue-500/10 bg-blue-500/2 dark:bg-blue-950/4 p-6 sm:p-8 md:p-12 shadow-sm hover:border-blue-500/35 transition-all duration-300 overflow-hidden">
            <div className="absolute left-0 bottom-0 -z-10 h-72 w-72 rounded-full bg-blue-500/10 blur-3xl opacity-60" />
            <div className="grid gap-12 lg:grid-cols-12 items-center relative z-10">
              {/* Interactive Chat Mock Widget on the Left */}
              <div className="lg:col-span-6 lg:order-last">
                <div className="lg:pl-6 space-y-6">
                  <Badge className="bg-blue-500/10 text-blue-600 dark:text-blue-400 hover:bg-blue-500/15 border-0 font-bold uppercase tracking-wider text-[10px]">
                    RAG KNOWLEDGE RETRIEVAL
                  </Badge>
                  <h3 className="font-display text-2xl font-extrabold text-foreground sm:text-3xl leading-tight">
                    Doctor-Grade AI Tutor
                  </h3>
                  <p className="text-base text-muted-foreground leading-relaxed">
                    Stuck on a tricky pathophysiology concept? Our AI Tutor retrieves context from 79 textbook chapters and medical resources to provide grounded explanations aligned with standard clinical practice.
                  </p>

                  <ul className="space-y-3 font-semibold text-foreground text-sm">
                    <li className="flex items-center gap-2.5">
                      <CheckCircle2 className="h-4.5 w-4.5 text-blue-500 shrink-0" />
                      Interactive chat modes (Socratic, Viva, High-Yield)
                    </li>
                    <li className="flex items-center gap-2.5">
                      <CheckCircle2 className="h-4.5 w-4.5 text-blue-500 shrink-0" />
                      Multi-model round-robin routing (failsafe reliability)
                    </li>
                    <li className="flex items-center gap-2.5">
                      <CheckCircle2 className="h-4.5 w-4.5 text-blue-500 shrink-0" />
                      Instant mnemonic generation to simplify retention
                    </li>
                  </ul>
                </div>
              </div>

              {/* Interactive AI Chat Mockup */}
              <div className="lg:col-span-6">
                <div className="rounded-3xl border border-border/80 bg-card p-5 shadow-xl relative">
                  <span className="absolute -top-3 left-6 rounded-full bg-blue-500 text-white text-[10px] font-bold px-3 py-1 uppercase tracking-wider">
                    Interactive Demo
                  </span>

                  <div className="space-y-4 pt-2">
                    <div className="flex gap-1.5 border-b border-border/50 pb-3">
                      {[
                        { id: 'ra', label: 'Rheumatoid Arthritis' },
                        { id: 'se', label: 'Status Epilepticus' },
                        { id: 'as', label: 'Aortic Stenosis' }
                      ].map((btn) => (
                        <button
                          key={btn.id}
                          onClick={() => setActiveTutorTopic(btn.id as 'ra' | 'se' | 'as')}
                          className={`px-3 py-1.5 rounded-lg text-[10px] font-bold border transition-all ${
                            activeTutorTopic === btn.id
                              ? 'bg-blue-500 border-blue-500 text-white shadow-sm'
                              : 'border-border/60 bg-muted/20 text-muted-foreground hover:bg-muted/40'
                          }`}
                        >
                          {btn.label}
                        </button>
                      ))}
                    </div>

                    <div className="space-y-3 max-h-[280px] overflow-y-auto pr-1">
                      {/* User Prompt */}
                      <div className="flex items-start gap-2.5 justify-end">
                        <div className="rounded-2xl rounded-tr-sm bg-blue-500 text-white px-4 py-2.5 max-w-[85%] text-xs font-semibold shadow-sm">
                          {tutorConversations[activeTutorTopic].question}
                        </div>
                        <div className="h-7 w-7 rounded-full bg-blue-100 flex items-center justify-center shrink-0 text-xs font-extrabold text-blue-600">
                          Dr
                        </div>
                      </div>

                      {/* AI Answer */}
                      <div className="flex items-start gap-2.5">
                        <div className="h-7 w-7 rounded-full bg-indigo-500 flex items-center justify-center shrink-0 text-[10px] font-extrabold text-white">
                          AI
                        </div>
                        <div className="rounded-2xl rounded-tl-sm bg-muted/45 px-4 py-2.5 max-w-[85%] text-xs text-foreground leading-relaxed border border-border/30">
                          <div className="flex items-center gap-1.5 text-[10px] font-bold text-indigo-500 mb-1.5">
                            <Brain className="h-3.5 w-3.5" />
                            RAG Grounded Response
                          </div>
                          <div 
                            className="space-y-2 whitespace-pre-line"
                            dangerouslySetInnerHTML={{
                              __html: tutorConversations[activeTutorTopic].reply.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
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

          {/* Feature 3: Smart Exam Engine (Interactive Exam HUD) */}
          <div className="relative group/feat rounded-[2.5rem] border border-teal-500/20 dark:border-teal-500/10 bg-teal-500/2 dark:bg-teal-950/4 p-6 sm:p-8 md:p-12 shadow-sm hover:border-teal-500/35 transition-all duration-300 overflow-hidden">
            <div className="absolute right-0 top-0 -z-10 h-72 w-72 rounded-full bg-teal-500/10 blur-3xl opacity-60" />
            <div className="grid gap-12 lg:grid-cols-12 items-center relative z-10">
              <div className="lg:col-span-6 space-y-6">
                <Badge className="bg-teal-500/10 text-teal-600 dark:text-teal-400 hover:bg-teal-500/15 border-0 font-bold uppercase tracking-wider text-[10px]">
                  ADAPTIVE SYSTEM
                </Badge>
                <h3 className="font-display text-2xl font-extrabold text-foreground sm:text-3xl leading-tight">
                  Smart Exam Engine
                </h3>
                <p className="text-base text-muted-foreground leading-relaxed">
                  Take control of your preparation with adaptive testing modes that mimic UPSC CMS exam conditions. Features automated timers, negative marking scoring, and immediate breakdown reviews.
                </p>

                <ul className="space-y-3 font-semibold text-foreground text-sm">
                  <li className="flex items-center gap-2.5">
                    <CheckCircle2 className="h-4.5 w-4.5 text-teal-500 shrink-0" />
                    Realistic exam interface mimicking actual test software
                  </li>
                  <li className="flex items-center gap-2.5">
                    <CheckCircle2 className="h-4.5 w-4.5 text-teal-500 shrink-0" />
                    Dynamic negative scoring (+1.0 / -0.33 marking)
                  </li>
                  <li className="flex items-center gap-2.5">
                    <CheckCircle2 className="h-4.5 w-4.5 text-teal-500 shrink-0" />
                    Customized topic weight drills based on prior weak performance
                  </li>
                </ul>
              </div>

              {/* Exam HUD widget mockup */}
              <div className="lg:col-span-6">
                <div className="rounded-3xl border border-border/80 bg-slate-950 text-slate-100 p-6 shadow-2xl relative font-sans">
                  <span className="absolute -top-3 left-6 rounded-full bg-teal-500 text-white text-[10px] font-bold px-3 py-1 uppercase tracking-wider">
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

                    {/* Question box */}
                    <div className="space-y-1.5">
                      <p className="text-[10px] uppercase font-bold text-slate-500 tracking-wider">Question 24 of 120</p>
                      <p className="text-xs font-bold leading-relaxed text-slate-200">
                        Which of the following is the definitive management of severe pre-eclampsia at 38 weeks of gestation?
                      </p>
                    </div>

                    {/* MCQ choices */}
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
                            className={`w-full text-left rounded-xl border p-3 text-[11px] font-semibold flex items-center gap-3 transition-all ${
                              isSel
                                ? 'border-teal-500 bg-teal-500/10 text-teal-300'
                                : 'border-slate-800 bg-slate-900/50 hover:bg-slate-900 text-slate-400 hover:text-slate-200'
                            }`}
                          >
                            <span className={`h-5 w-5 rounded-full flex items-center justify-center shrink-0 border text-[10px] font-extrabold ${
                              isSel ? 'bg-teal-500 border-teal-500 text-slate-950' : 'border-slate-700 bg-slate-950'
                            }`}>
                              {ch.key}
                            </span>
                            <span>{ch.text}</span>
                          </button>
                        );
                      })}
                    </div>

                    {/* Live scoring stats mockup */}
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

          {/* Feature 4: Rapid Recall AI (Flipping Flashcard) */}
          <div className="relative group/feat rounded-[2.5rem] border border-amber-500/20 dark:border-amber-500/10 bg-amber-500/2 dark:bg-amber-950/4 p-6 sm:p-8 md:p-12 shadow-sm hover:border-amber-500/35 transition-all duration-300 overflow-hidden">
            <div className="absolute left-0 top-0 -z-10 h-72 w-72 rounded-full bg-amber-500/10 blur-3xl opacity-60" />
            <div className="grid gap-12 lg:grid-cols-12 items-center relative z-10">
              {/* Interactive Flashcard Widget on the Left */}
              <div className="lg:col-span-6 lg:order-last">
                <div className="lg:pl-6 space-y-6">
                  <Badge className="bg-amber-500/10 text-amber-600 dark:text-amber-400 hover:bg-amber-500/15 border-0 font-bold uppercase tracking-wider text-[10px]">
                    SPACED REPETITION
                  </Badge>
                  <h3 className="font-display text-2xl font-extrabold text-foreground sm:text-3xl leading-tight">
                    Rapid Recall AI (SM-2)
                  </h3>
                  <p className="text-base text-muted-foreground leading-relaxed">
                    Consolidate critical high-yield facts using our SM-2 algorithm-backed flashcard system. Generates personalized clinical mnemonics to boost memory recall on exam day.
                  </p>

                  <ul className="space-y-3 font-semibold text-foreground text-sm">
                    <li className="flex items-center gap-2.5">
                      <CheckCircle2 className="h-4.5 w-4.5 text-amber-500 shrink-0" />
                      Adaptive spaced repetition schedules custom to your recall speed
                    </li>
                    <li className="flex items-center gap-2.5">
                      <CheckCircle2 className="h-4.5 w-4.5 text-amber-500 shrink-0" />
                      Quick mnemonics cards with colored highlight structures
                    </li>
                    <li className="flex items-center gap-2.5">
                      <CheckCircle2 className="h-4.5 w-4.5 text-amber-500 shrink-0" />
                      Custom card builder and public deck library
                    </li>
                  </ul>
                </div>
              </div>

              {/* Interactive Flipping Card Deck */}
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
                        className={`py-2 px-3 text-center rounded-xl text-[10px] font-bold border transition-all ${
                          flippedCard === c.id
                            ? 'bg-amber-500 border-amber-500 text-white'
                            : 'border-border/60 bg-card hover:bg-muted/30 text-muted-foreground'
                        }`}
                      >
                        {c.title}
                      </button>
                    ))}
                  </div>

                  <div className="perspective-1000 h-[260px] w-full relative">
                    {mnemonicCards.map((c) => {
                      const isFlipped = flippedCard === c.id;
                      const isSelected = flippedCard === null ? c.id === 1 : flippedCard === c.id;

                      if (!isSelected) return null;
                      // Default fallback if nothing is clicked
                      const activeFlippedState = flippedCard === null ? false : isFlipped;

                      return (
                        <div
                          key={c.id}
                          onClick={() => setFlippedCard(flippedCard === c.id ? null : c.id)}
                          className={`w-full h-full duration-500 transform-style-3d relative cursor-pointer select-none rounded-3xl border border-border/80 bg-card shadow-lg ${
                            activeFlippedState ? 'rotate-y-180' : ''
                          }`}
                        >
                          {/* Front side */}
                          <div className="absolute inset-0 backface-hidden w-full h-full flex flex-col justify-between p-6">
                            <div>
                              <div className="flex justify-between items-center text-[10px] font-bold text-amber-600 dark:text-amber-400">
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
                          <div className="absolute inset-0 backface-hidden rotate-y-180 w-full h-full bg-amber-500/3 flex flex-col justify-between p-6 overflow-y-auto">
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

          {/* Feature 5: Question Generator (Interactive demo) */}
          <div className="relative group/feat rounded-[2.5rem] border border-cyan-500/20 dark:border-cyan-500/10 bg-cyan-500/2 dark:bg-cyan-950/4 p-6 sm:p-8 md:p-12 shadow-sm hover:border-cyan-500/35 transition-all duration-300 overflow-hidden">
            <div className="absolute right-0 bottom-0 -z-10 h-72 w-72 rounded-full bg-cyan-500/10 blur-3xl opacity-60" />
            <div className="grid gap-12 lg:grid-cols-12 items-center relative z-10">
              <div className="lg:col-span-6 space-y-6">
                <Badge className="bg-cyan-500/10 text-cyan-600 dark:text-cyan-400 hover:bg-cyan-500/15 border-0 font-bold uppercase tracking-wider text-[10px]">
                  UNLIMITED CLINICAL DRILLS
                </Badge>
                <h3 className="font-display text-2xl font-extrabold text-foreground sm:text-3xl leading-tight">
                  Question Generator
                </h3>
                <p className="text-base text-muted-foreground leading-relaxed">
                  Generate bespoke mock questions tailored to any subject, sub-topic, and difficulty level. Strengthen active recall by generating targeted clinical drills on topics where you need the most reinforcement.
                </p>

                <ul className="space-y-3 font-semibold text-foreground text-sm">
                  <li className="flex items-center gap-2.5">
                    <CheckCircle2 className="h-4.5 w-4.5 text-cyan-500 shrink-0" />
                    Bespoke question generation matching UPSC CMS patterns
                  </li>
                  <li className="flex items-center gap-2.5">
                    <CheckCircle2 className="h-4.5 w-4.5 text-cyan-500 shrink-0" />
                    Detailed explanation breakdowns automatically created
                  </li>
                  <li className="flex items-center gap-2.5">
                    <CheckCircle2 className="h-4.5 w-4.5 text-cyan-500 shrink-0" />
                    Focus on custom sub-topics like Pediatrics, Vaccines, Cardiology
                  </li>
                </ul>
              </div>

              {/* Interactive Question Generator Demo */}
              <div className="lg:col-span-6">
                <div className="rounded-3xl border border-border/80 bg-card p-6 shadow-xl relative">
                  <span className="absolute -top-3 left-6 rounded-full bg-cyan-500 text-white text-[10px] font-bold px-3 py-1 uppercase tracking-wider">
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
                          className="w-full px-2 py-1.5 rounded-lg border border-border/60 bg-muted/20 text-xs font-semibold text-foreground"
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
                          className="w-full px-2 py-1.5 rounded-lg border border-border/60 bg-muted/20 text-xs font-semibold text-foreground placeholder:text-muted-foreground/60"
                        />
                      </div>
                    </div>

                    {!demoGenerated && !demoLoading && (
                      <button
                        onClick={handleDemoGenerate}
                        className="w-full py-2.5 rounded-xl bg-cyan-500 hover:bg-cyan-600 text-white font-bold text-xs flex items-center justify-center gap-1.5 shadow-md shadow-cyan-500/10 active:scale-95 transition-all cursor-pointer"
                      >
                        <Sparkles className="w-3.5 h-3.5" />
                        Generate Custom Drill
                      </button>
                    )}

                    {demoLoading && (
                      <div className="p-6 text-center space-y-3 bg-muted/20 rounded-xl border border-border/40 animate-pulse">
                        <Loader2 className="w-6 h-6 animate-spin mx-auto text-cyan-500" />
                        <p className="text-[11px] font-bold text-cyan-600">Generating bespoke {demoSubject} question on &quot;{demoTopic || 'General Info'}&quot;...</p>
                      </div>
                    )}

                    {demoGenerated && demoQuestion && (
                      <div className="space-y-4 pt-1 animate-fadeIn">
                        <div className="p-3 bg-cyan-500/5 rounded-xl border border-cyan-500/10 text-xs font-bold leading-relaxed text-foreground">
                          {demoQuestion.text}
                        </div>

                        <div className="space-y-2">
                          {demoQuestion.options.map((opt: { key: string; text: string }) => {
                            const isSelected = demoAnswer === opt.key;
                            const isCorrect = opt.key === demoQuestion.correct;
                            let btnStyle = "border-border/60 hover:border-cyan-500/50 hover:bg-muted/10";
                            
                            if (demoAnswer !== null) {
                              if (isCorrect) {
                                btnStyle = "border-emerald-500 bg-emerald-500/5 text-emerald-900 dark:text-emerald-300";
                              } else if (isSelected) {
                                btnStyle = "border-red-500 bg-red-50/5 text-red-900 dark:text-red-400";
                              } else {
                                btnStyle = "border-border/40 opacity-60";
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
                                className={`w-full text-left rounded-xl border p-3 text-[11px] font-semibold flex items-center gap-3 transition-all ${btnStyle}`}
                              >
                                <span className={`h-5 w-5 rounded-full flex items-center justify-center shrink-0 border text-[10px] font-extrabold
                                  ${isSelected && isCorrect ? 'bg-emerald-500 text-white border-emerald-500' : ''}
                                  ${isSelected && !isCorrect ? 'bg-red-500 text-white border-red-500' : ''}
                                  ${!isSelected && isCorrect && demoAnswer !== null ? 'bg-emerald-500 text-white border-emerald-500' : 'bg-muted/30 border-border'}
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
                            <div className="rounded-xl bg-muted/40 p-3 border border-cyan-500/10 space-y-1">
                              <div className="flex items-center gap-1.5 text-xs font-bold text-cyan-600">
                                <Sparkles className="h-3.5 w-3.5" />
                                Explanation:
                              </div>
                              <p className="text-[11px] leading-relaxed text-muted-foreground">
                                {demoQuestion.explanation}
                              </p>
                            </div>

                            {/* Generate AI Analysis in demo */}
                            {!demoAiDone && !demoAiLoading && (
                              <button
                                onClick={() => { setDemoAiLoading(true); setTimeout(() => { setDemoAiLoading(false); setDemoAiDone(true); }, 1800); }}
                                className="w-full rounded-xl border border-blue-200 bg-blue-50/50 dark:bg-blue-900/10 dark:border-blue-800/50 p-3 flex items-center justify-center gap-2 cursor-pointer transition-all hover:bg-blue-50 dark:hover:bg-blue-900/20 text-xs font-bold text-blue-700 dark:text-blue-300"
                              >
                                <Brain className="w-4 h-4" /> Generate AI Analysis
                              </button>
                            )}
                            {demoAiLoading && (
                              <div className="flex items-center justify-center gap-2 p-3 rounded-xl border border-blue-200 bg-blue-50/30 dark:bg-blue-900/10 animate-pulse">
                                <Loader2 className="w-4 h-4 animate-spin text-blue-500" />
                                <span className="text-[11px] font-bold text-blue-600">Generating deep analysis...</span>
                              </div>
                            )}
                            {demoAiDone && (
                              <div className="space-y-2 animate-fadeIn">
                                <div className="rounded-xl bg-emerald-50/50 dark:bg-emerald-950/10 border border-emerald-200 dark:border-emerald-900/30 p-3">
                                  <div className="text-[10px] font-bold text-emerald-600 mb-1 flex items-center gap-1"><CheckCircle2 className="w-3 h-3" /> Why Correct</div>
                                  <p className="text-[11px] leading-relaxed text-muted-foreground">{demoQuestion.explanation}</p>
                                </div>
                                <div className="rounded-xl bg-amber-50/50 dark:bg-amber-950/10 border border-amber-200 dark:border-amber-900/30 p-3">
                                  <div className="text-[10px] font-bold text-amber-600 mb-1">🧠 Exam Tip</div>
                                  <p className="text-[11px] leading-relaxed text-muted-foreground">This is a high-yield UPSC CMS pattern. Questions on emergency protocols and first-line management appear every year. Focus on distinguishing first-line vs second-line treatments.</p>
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

      {/* Testimonials Section */}
      <section className="mx-auto max-w-7xl px-6 py-16 text-center border-t border-border/40">
        <div className="space-y-4 max-w-3xl mx-auto mb-12">
          <Badge className="bg-primary/10 text-primary hover:bg-primary/15 border-0 font-bold uppercase tracking-wider text-[10px] py-1 px-3">
            Aspirant Reviews
          </Badge>
          <h2 className="font-display text-2xl font-extrabold text-foreground sm:text-4xl tracking-tight">
            Loved by medical students preparing for UPSC CMS
          </h2>
          <p className="text-sm md:text-base text-muted-foreground">
            See how doctors and residents across top-tier institutions are using our platform to boost their clinical scores and daily prep streaks.
          </p>
        </div>

        <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-3 max-w-6xl mx-auto text-left">
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
            <div key={idx} className="glass-card p-6 border border-border/60 hover:border-primary/20 transition-all group duration-300 relative bg-slate-900/40" style={{ backdropFilter: 'blur(12px)' }}>
              <div className="flex gap-1 text-amber-500 mb-4">
                {Array.from({ length: item.rating }).map((_, i) => (
                  <svg key={i} className="w-4 h-4 fill-current text-amber-400" viewBox="0 0 20 20">
                    <path d="M9.049 2.927c.3-.921 1.603-.921 1.902 0l1.07 3.292a1 1 0 00.95.69h3.462c.969 0 1.371 1.24.588 1.81l-2.8 2.034a1 1 0 00-.364 1.118l1.07 3.292c.3.921-.755 1.688-1.54 1.118l-2.8-2.034a1 1 0 00-1.175 0l-2.8 2.034c-.784.57-1.838-.197-1.539-1.118l1.07-3.292a1 1 0 00-.364-1.118L2.98 8.72c-.783-.57-.38-1.81.588-1.81h3.461a1 1 0 00.951-.69l1.07-3.292z" />
                  </svg>
                ))}
              </div>
              <p className="text-xs md:text-sm text-slate-300 leading-relaxed italic">
                &quot;{item.quote}&quot;
              </p>
              <div className="border-t border-slate-800/60 mt-4 pt-3 flex items-center gap-3">
                <div className="w-8 h-8 rounded-full bg-primary/10 flex items-center justify-center font-bold text-xs text-primary">
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
      </section>

      {/* Premium early bird pricing section */}
      <section className="relative px-6 py-20 md:py-24 overflow-hidden border-t border-border/45 bg-slate-950 text-white rounded-[2.5rem] mx-4 sm:mx-6 md:mx-12 my-16 shadow-2xl">
        <div className="absolute right-0 top-0 h-[400px] w-[400px] rounded-full bg-linear-to-br from-amber-500/10 to-yellow-500/15 blur-3xl opacity-60 pointer-events-none" />
        <div className="absolute left-0 bottom-0 h-[400px] w-[400px] rounded-full bg-linear-to-tr from-cyan-500/10 to-blue-500/15 blur-3xl opacity-60 pointer-events-none" />

        <div className="mx-auto max-w-5xl relative z-10">
          <div className="grid gap-12 lg:grid-cols-12 items-center">
            <div className="lg:col-span-7 space-y-6 text-left">
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

            <div className="lg:col-span-5 flex justify-center">
              <div className="w-full max-w-sm rounded-3xl border border-amber-500/30 bg-slate-900/60 p-8 text-center backdrop-blur-md relative overflow-hidden">
                <div className="absolute top-0 right-0 w-24 h-24 bg-amber-500/10 rounded-full blur-2xl pointer-events-none" />
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
      </section>

          {/* "Campus Momentum" Dashboard */}
          <div className="relative group w-full pt-4">
            <div className="absolute -inset-1 rounded-[2.5rem] bg-linear-to-tr from-emerald-500 via-blue-500 to-indigo-500 opacity-20 blur-xl transition-all group-hover:opacity-30" />
            <div className="rounded-[2.5rem] border border-border/80 bg-card p-6 md:p-10 shadow-xl space-y-6 relative overflow-hidden">
              <div className="absolute right-0 top-0 h-40 w-40 rounded-full bg-emerald-500/5 blur-3xl" />
              
              <div className="flex flex-wrap items-center justify-between gap-4 border-b border-border/50 pb-5">
                <div className="space-y-1 text-left">
                  <h3 className="font-display text-xl font-extrabold text-foreground">Campus Momentum</h3>
                  <p className="text-xs text-muted-foreground">Students and residents from leading medical institutions prep here.</p>
                </div>
                <Badge className="bg-emerald-600 text-white hover:bg-emerald-600 px-4 py-1.5 rounded-full font-bold shadow-sm shadow-emerald-600/10">
                  2,900+ active this week
                </Badge>
              </div>

              {/* Scrolling ticker visual replacement */}
              <div className="grid gap-3 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-6">
                {campuses.map((campus) => (
                  <div 
                    key={campus} 
                    className="rounded-xl border border-border/60 bg-muted/20 px-4 py-3 text-xs font-semibold text-center text-foreground hover:bg-muted/40 transition-colors"
                  >
                    {campus}
                  </div>
                ))}
              </div>

              <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4 pt-2">
                {communityProfiles.map((profile) => (
                  <div key={profile.name} className="rounded-2xl border border-border/50 bg-muted/15 p-4 space-y-1.5 relative hover:border-primary/35 transition-all text-left">
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

          {/* "System Cockpit Live" Dashboard */}
          <div className="space-y-6 pt-10">
            <div className="text-center space-y-2">
              <h2 className="font-display text-2xl font-extrabold text-foreground tracking-tight">
                Personalized Study Cockpit
              </h2>
              <p className="text-sm text-muted-foreground max-w-xl mx-auto">
                Track high-yield progress, streak targets, and score estimations.
              </p>
            </div>

            <div className="relative group max-w-3xl mx-auto w-full">
              <div className="absolute -inset-1 rounded-[2.5rem] bg-linear-to-tr from-emerald-500 via-blue-500 to-indigo-500 opacity-20 blur-xl transition-all group-hover:opacity-30" />
              <Card className="relative overflow-hidden rounded-4xl border border-border/80 bg-card/90 text-foreground shadow-2xl backdrop-blur-md">
              {/* Header bar of the widget */}
              <div className="flex items-center justify-between border-b border-border/60 bg-muted/40 px-5 py-4">
                <div className="flex items-center gap-2">
                  <div className="h-3 w-3 rounded-full bg-red-400/80" />
                  <div className="h-3 w-3 rounded-full bg-amber-400/80" />
                  <div className="h-3 w-3 rounded-full bg-emerald-400/80" />
                </div>
                <div className="flex items-center gap-2 text-xs font-bold text-muted-foreground tracking-wider uppercase">
                  <span className="inline-block h-1.5 w-1.5 rounded-full bg-emerald-500 animate-pulse" />
                  SYSTEM COCKPIT LIVE
                </div>
              </div>

              <CardContent className="p-6 space-y-5">
                <div className="flex flex-col sm:flex-row sm:items-center gap-4 justify-between">
                  <div className="flex items-center gap-3">
                    <div className="h-10 w-10 rounded-xl bg-blue-500/10 border border-blue-500/20 flex items-center justify-center">
                      <Stethoscope className="h-5 w-5 text-blue-500" />
                    </div>
                    <div>
                      <h3 className="text-sm font-bold text-foreground">
                        {isAuthenticated && user ? (user.first_name ? `${user.first_name} ${user.last_name || ''}` : user.username) : "Dr. Sarah Jenkins"}
                      </h3>
                      <p className="text-[11px] text-muted-foreground">
                        {isAuthenticated && user ? (user.college || "Medical Specialist Track") : "General Medicine Specialist Track"}
                      </p>
                    </div>
                    <Badge className="bg-blue-500/10 text-blue-600 dark:text-blue-400 hover:bg-blue-500/15 border-0">
                      {isAuthenticated && user ? (user.is_subscribed ? "Premium Member" : "Aspirant") : "Aspirant"}
                    </Badge>
                  </div>

                  <div className="flex gap-4">
                    <div className="rounded-xl border border-border/50 bg-muted/20 px-4 py-2 flex items-center gap-2.5">
                      <Flame className="h-4 w-4 text-orange-500" />
                      <div>
                        <p className="text-[9px] uppercase font-bold text-muted-foreground tracking-wide">Daily Streak</p>
                        <p className="text-xs font-extrabold">
                          {isAuthenticated && user ? "1 Day" : "12 Days"}
                        </p>
                      </div>
                    </div>
                    <div className="rounded-xl border border-border/50 bg-muted/20 px-4 py-2 flex items-center gap-2.5">
                      <Award className="h-4 w-4 text-amber-500" />
                      <div>
                        <p className="text-[9px] uppercase font-bold text-muted-foreground tracking-wide">Est. Score</p>
                        <p className="text-xs font-extrabold">
                          {isAuthenticated && user ? "74.5%" : "68.5%"}
                        </p>
                      </div>
                    </div>
                  </div>
                </div>

                {/* Progress bar */}
                <div className="space-y-1.5 bg-muted/30 p-4 rounded-2xl border border-border/50">
                  <div className="flex justify-between text-xs font-bold text-foreground">
                    <span>Clinical Prep Progress</span>
                    <span className="text-blue-600 dark:text-blue-400">74% Target</span>
                  </div>
                  <div className="h-2.5 w-full bg-border/50 rounded-full overflow-hidden">
                    <div className="h-full bg-linear-to-r from-blue-500 to-indigo-600 rounded-full" style={{ width: '74%' }} />
                  </div>
                </div>
              </CardContent>
            </Card>
          </div>
        </div>
      </div>

        {/* Stats Strip */}
        <div className="mt-16 grid grid-cols-2 gap-4 md:grid-cols-4 pt-8 border-t border-border/50 max-w-5xl mx-auto w-full">
          {stats.map((stat, i) => (
            <div key={i} className="flex flex-col items-center text-center p-3 hover:translate-y-[-2px] transition-transform">
              <div className="h-10 w-10 rounded-xl bg-primary/5 flex items-center justify-center mb-3">
                <stat.icon className="h-5 w-5 text-primary" />
              </div>
              <span className="text-3xl font-extrabold text-foreground tracking-tight">{stat.value}</span>
              <span className="text-sm font-bold text-foreground mt-1">{stat.label}</span>
              <span className="text-xs text-muted-foreground mt-0.5">{stat.desc}</span>
            </div>
          ))}
        </div>

        {/* Target Market Pills */}
        <div className="mt-8 flex flex-wrap justify-center items-center gap-2 p-3 bg-muted/20 border border-border/40 rounded-2xl max-w-4xl mx-auto">
          <span className="text-[10px] uppercase font-extrabold text-muted-foreground tracking-wider mr-2">Core System Alignment:</span>
          <span className="rounded-full border border-border/60 bg-card px-3.5 py-1 text-xs font-semibold text-foreground shadow-sm">UPSC CMS Pattern Aligned</span>
          <span className="rounded-full border border-border/60 bg-card px-3.5 py-1 text-xs font-semibold text-foreground shadow-sm">NEET PG Revision Friendly</span>
          <span className="rounded-full border border-border/60 bg-card px-3.5 py-1 text-xs font-semibold text-foreground shadow-sm">No Credit Card Required</span>
          <span className="rounded-full border border-border/60 bg-card px-3.5 py-1 text-xs font-semibold text-foreground shadow-sm">Free Daily Tokens</span>
        </div>
      </section>

      {/* Subjects Section */}
      <section className="px-4 py-24 sm:px-6 relative overflow-hidden">
        <div className="absolute left-1/2 top-1/2 -z-10 h-72 w-72 rounded-full bg-indigo-500/5 blur-3xl" />
        <div className="mx-auto max-w-4xl space-y-12">
          
          <div className="text-center space-y-3">
            <h2 className="font-display text-3xl font-extrabold text-foreground tracking-tight">
              All 5 UPSC CMS Subjects Covered
            </h2>
            <p className="text-muted-foreground max-w-lg mx-auto">
              Paper 1 + Paper 2 complete exam coverage with high-yield clinical question depth.
            </p>
          </div>

          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {subjects.map((s, i) => (
              <Card key={i} className="group border-border/80 transition-all duration-300 hover:border-primary/40 hover:-translate-y-0.5 hover:shadow-md bg-card/60 backdrop-blur-sm">
                <CardContent className="p-5 flex items-center gap-3">
                  <div className="h-8 w-8 rounded-lg bg-emerald-500/10 flex items-center justify-center transition-colors group-hover:bg-emerald-500/20">
                    <CheckCircle2 className="w-4.5 h-4.5 text-emerald-500" />
                  </div>
                  <span className="font-bold text-sm text-foreground">{s}</span>
                </CardContent>
              </Card>
            ))}
            <Card className="group border-border/80 transition-all duration-300 hover:border-primary/40 hover:-translate-y-0.5 hover:shadow-md bg-card/60 backdrop-blur-sm">
              <CardContent className="p-5 flex items-center gap-3">
                <div className="h-8 w-8 rounded-lg bg-blue-500/10 flex items-center justify-center transition-colors group-hover:bg-blue-500/20">
                  <Sparkles className="w-4.5 h-4.5 text-blue-500" />
                </div>
                <span className="font-bold text-sm text-foreground">AI-Powered Analytics</span>
              </CardContent>
            </Card>
          </div>
        </div>
      </section>

      {/* Why CrackCMS Section */}
      <section className="border-t border-border/60 bg-muted/20 px-4 py-24 sm:px-6">
        <div className="mx-auto max-w-4xl space-y-12">
          
          <div className="text-center">
            <h2 className="font-display text-3xl font-extrabold text-foreground tracking-tight">
              Why Doctors Prefer This System
            </h2>
          </div>

          <div className="grid md:grid-cols-3 gap-8">
            {[
              { 
                icon: Clock3, 
                title: 'Workflow-First', 
                desc: 'Organized systematically around what you need to do now, next, and what demands review focus.' 
              },
              { 
                icon: Users, 
                title: 'Doctor-Centric', 
                desc: 'Features, labels, and explanations align with clinical practice, rather than generic exam templates.' 
              },
              { 
                icon: TrendingUp, 
                title: 'Continuous Optimization', 
                desc: 'Data-driven insights isolate and narrow down your weakest diagnostic areas over time.' 
              },
            ].map((item, i) => (
              <div key={i} className="text-center space-y-4 group">
                <div className="w-14 h-14 rounded-2xl flex items-center justify-center mx-auto bg-primary/10 border border-primary/10 transition-transform group-hover:scale-105 shadow-sm">
                  <item.icon className="w-6 h-6 text-primary" />
                </div>
                <h3 className="font-bold text-foreground text-base">{item.title}</h3>
                <p className="text-sm text-muted-foreground leading-relaxed">{item.desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>



      {/* CTA Section */}
      <section className="px-4 pb-24 sm:px-6 relative overflow-hidden">
        {/* Glow backdrop */}
        <div className="absolute left-1/2 top-1/2 -z-10 h-[500px] w-[500px] -translate-x-1/2 -translate-y-1/2 rounded-full bg-blue-600/10 blur-3xl" />
        
        <Card className="mx-auto max-w-4xl border-0 bg-slate-950 text-white rounded-[2.5rem] relative overflow-hidden shadow-2xl">
          {/* Neon gradient background mesh */}
          <div className="absolute right-0 top-0 h-96 w-96 rounded-full bg-linear-to-br from-indigo-500/20 to-teal-500/20 blur-3xl opacity-60" />
          <div className="absolute left-0 bottom-0 h-96 w-96 rounded-full bg-linear-to-tr from-blue-500/20 to-rose-500/20 blur-3xl opacity-60" />
          
          <CardContent className="p-10 md:p-16 text-center space-y-6 relative z-10">
            <div className="h-12 w-12 rounded-2xl bg-white/10 flex items-center justify-center mx-auto border border-white/10 shadow-lg">
              <GraduationCap className="w-6 h-6 text-blue-400" />
            </div>
            
            <h2 className="font-display text-3xl md:text-4xl font-extrabold tracking-tight text-white leading-tight">
              Ready to Build an Exam-Ready Routine?
            </h2>
            
            <p className="text-slate-400 max-w-lg mx-auto text-base">
              Join thousands of medical graduates leveraging an AI + doctor prep workflow to study faster, cleaner, and with optimized memory retention.
            </p>
            
            <div className="pt-4">
              <Button size="xl" asChild className="rounded-2xl bg-white text-slate-950 hover:bg-slate-100 font-bold transition-all px-8 py-4 shadow-xl active:scale-98">
                <Link href={isAuthenticated ? '/dashboard' : '/register'}>
                  Get Started Free <ArrowRight className="ml-1.5 w-5 h-5 text-slate-950" />
                </Link>
              </Button>
            </div>
          </CardContent>
        </Card>
      </section>

      {/* Footer */}
      <footer className="border-t border-border/60 bg-muted/10 px-4 py-12 sm:px-6">
        <div className="mx-auto flex max-w-6xl flex-col items-center justify-between gap-6 sm:flex-row">
          <BrandMark href="/" compact showTagline={false} />
          <div className="flex flex-wrap items-center justify-center gap-2 text-xs text-muted-foreground sm:justify-end">
            <span className="rounded-full border border-border/80 bg-card px-3 py-1 font-semibold">UPSC CMS</span>
            <span className="rounded-full border border-border/80 bg-card px-3 py-1 font-semibold">NEET PG</span>
            <span className="rounded-full border border-border/80 bg-card px-3 py-1 font-semibold">CMS Mock Tests</span>
          </div>
        </div>
        
        <div className="mx-auto mt-6 max-w-6xl border-t border-border/40 pt-4 flex flex-col sm:flex-row justify-between items-center gap-3 text-xs text-muted-foreground">
          <p>© 2026 CrackCMS | AI-powered UPSC CMS preparation platform</p>
          <div className="flex gap-4">
            <Link href="/privacy" className="hover:text-foreground hover:underline">Privacy Policy</Link>
            <Link href="/terms" className="hover:text-foreground hover:underline">Terms of Service</Link>
          </div>
        </div>
      </footer>
    </div>
  );
}
