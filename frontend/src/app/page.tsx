'use client';
import Link from 'next/link';
import { useAuth } from '@/lib/auth';
import { BookOpen, Brain, BarChart3, GraduationCap, Sparkles, Target, ChevronRight, Zap, TrendingUp, CheckCircle2, Users, Award, Clock } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';

export default function LandingPage() {
  const { isAuthenticated } = useAuth();

  const features = [
    { icon: BookOpen, title: 'PYQ Question Bank', desc: '3000+ previous year questions from 2018-2025 with verified answers, detailed explanations & textbook references.', color: 'text-indigo-600 dark:text-indigo-400', bg: 'bg-indigo-50 dark:bg-indigo-500/10' },
    { icon: Brain, title: 'AI Medical Tutor', desc: 'Ask any medical concept — get instant CMS-focused explanations, mnemonics & clinical correlations.', color: 'text-violet-600 dark:text-violet-400', bg: 'bg-violet-50 dark:bg-violet-500/10' },
    { icon: Target, title: 'Smart Test Engine', desc: '9 test types including subject-wise, topic-wise, PYQ simulator, adaptive AI tests with negative marking.', color: 'text-amber-600 dark:text-amber-400', bg: 'bg-amber-50 dark:bg-amber-500/10' },
    { icon: Sparkles, title: 'Mnemonic Generator', desc: 'AI generates memory tricks, quick revision hooks & clinical shortcuts for rapid recall.', color: 'text-pink-600 dark:text-pink-400', bg: 'bg-pink-50 dark:bg-pink-500/10' },
    { icon: BarChart3, title: 'Performance Analytics', desc: 'Track accuracy, identify weak topics, view study heatmap & get AI-powered score predictions.', color: 'text-emerald-600 dark:text-emerald-400', bg: 'bg-emerald-50 dark:bg-emerald-500/10' },
    { icon: GraduationCap, title: 'CMS Exam Simulator', desc: 'Full Paper 1 & Paper 2 mock exams with 120 questions each — matching the real UPSC CMS pattern.', color: 'text-rose-600 dark:text-rose-400', bg: 'bg-rose-50 dark:bg-rose-500/10' },
  ];

  const stats = [
    { value: '3000+', label: 'PYQ Questions', icon: BookOpen },
    { value: '5', label: 'Core Subjects', icon: Award },
    { value: '47+', label: 'Topic Areas', icon: Target },
    { value: '9', label: 'Test Types', icon: FileText },
  ];

  const subjects = [
    'General Medicine', 'Surgery', 'Pediatrics', 'Obstetrics & Gynecology', 'Preventive & Social Medicine'
  ];

  return (
    <div className="min-h-screen bg-background">
      {/* Navbar */}
      <nav className="sticky top-0 z-50 border-b border-border bg-background/95 backdrop-blur-sm">
        <div className="max-w-6xl mx-auto flex items-center justify-between px-6 h-16">
          <div className="flex items-center gap-2.5">
            <div className="w-9 h-9 rounded-lg flex items-center justify-center bg-primary">
              <Zap className="w-5 h-5 text-primary-foreground" />
            </div>
            <span className="text-xl font-bold text-foreground">CrackCMS</span>
          </div>
          <div className="flex items-center gap-3">
            {isAuthenticated ? (
              <Button asChild>
                <Link href="/dashboard">Go to Dashboard <ChevronRight className="w-4 h-4" /></Link>
              </Button>
            ) : (
              <>
                <Button variant="ghost" asChild className="hidden sm:inline-flex">
                  <Link href="/login">Log in</Link>
                </Button>
                <Button asChild>
                  <Link href="/register">Start Free <ChevronRight className="w-4 h-4" /></Link>
                </Button>
              </>
            )}
          </div>
        </div>
      </nav>

      {/* Hero Section */}
      <section className="px-6 pt-20 pb-16 text-center max-w-4xl mx-auto">
        <Badge variant="secondary" className="mb-6 px-4 py-1.5 text-sm font-medium">
          <Sparkles className="w-3.5 h-3.5 mr-1.5" />
          India&apos;s #1 UPSC CMS Preparation Platform
        </Badge>

        <h1 className="text-4xl sm:text-5xl md:text-6xl font-bold mb-6 leading-[1.1] tracking-tight text-foreground">
          Crack UPSC CMS with{' '}
          <span className="gradient-text">AI-Powered</span>{' '}
          Preparation
        </h1>

        <p className="text-lg text-muted-foreground mb-10 max-w-2xl mx-auto leading-relaxed">
          3000+ PYQs with verified answers, AI tutor, smart test engine, mnemonic generator 
          & personalized analytics — everything you need in one platform.
        </p>

        <div className="flex flex-col sm:flex-row items-center justify-center gap-3 mb-20">
          <Button size="xl" asChild>
            <Link href={isAuthenticated ? '/dashboard' : '/register'}>
              Start Preparing Free <ChevronRight className="w-5 h-5" />
            </Link>
          </Button>
          <Button size="xl" variant="outline" asChild>
            <Link href="#features">Explore Features</Link>
          </Button>
        </div>

        {/* Stats */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 max-w-3xl mx-auto">
          {stats.map((stat, i) => (
            <Card key={i} className="text-center">
              <CardContent className="p-5">
                <stat.icon className="w-5 h-5 mx-auto mb-2 text-primary" />
                <div className="text-2xl font-bold text-foreground">{stat.value}</div>
                <div className="text-xs text-muted-foreground mt-1">{stat.label}</div>
              </CardContent>
            </Card>
          ))}
        </div>
      </section>

      {/* Features Section */}
      <section id="features" className="px-6 py-20 bg-muted/50">
        <div className="max-w-6xl mx-auto">
          <div className="text-center mb-12">
            <h2 className="text-3xl font-bold text-foreground mb-3">
              Everything You Need to Crack CMS
            </h2>
            <p className="text-muted-foreground max-w-xl mx-auto">
              Not just a question bank — a complete AI-powered medical exam preparation ecosystem.
            </p>
          </div>
          <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-5">
            {features.map((feat, i) => (
              <Card key={i} className="hover:shadow-md transition-shadow border-border">
                <CardContent className="p-6">
                  <div className={`w-11 h-11 rounded-lg flex items-center justify-center mb-4 ${feat.bg}`}>
                    <feat.icon className={`w-5 h-5 ${feat.color}`} />
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
      <section className="px-6 py-20">
        <div className="max-w-4xl mx-auto">
          <div className="text-center mb-10">
            <h2 className="text-3xl font-bold text-foreground mb-3">All 5 UPSC CMS Subjects</h2>
            <p className="text-muted-foreground">Complete coverage of Paper 1 & Paper 2</p>
          </div>
          <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {subjects.map((s, i) => (
              <Card key={i} className="hover:border-primary/30 transition-colors">
                <CardContent className="p-5 flex items-center gap-3">
                  <CheckCircle2 className="w-5 h-5 text-emerald-500 shrink-0" />
                  <span className="font-medium text-foreground">{s}</span>
                </CardContent>
              </Card>
            ))}
            <Card className="hover:border-primary/30 transition-colors">
              <CardContent className="p-5 flex items-center gap-3">
                <CheckCircle2 className="w-5 h-5 text-emerald-500 shrink-0" />
                <span className="font-medium text-foreground">AI-Powered Analysis</span>
              </CardContent>
            </Card>
          </div>
        </div>
      </section>

      {/* Why CrackCMS Section */}
      <section className="px-6 py-20 bg-muted/50">
        <div className="max-w-4xl mx-auto">
          <div className="text-center mb-10">
            <h2 className="text-3xl font-bold text-foreground mb-3">Why CrackCMS?</h2>
          </div>
          <div className="grid md:grid-cols-3 gap-6">
            {[
              { icon: Clock, title: 'Save 4+ Hours Daily', desc: 'AI finds your weak areas and creates targeted practice. No more guessing what to study.' },
              { icon: Users, title: 'Community Driven', desc: 'Join a growing community of UPSC CMS aspirants. Share doubts, discuss questions, climb the leaderboard.' },
              { icon: TrendingUp, title: 'Track Your Growth', desc: 'Detailed analytics with score predictions. Know exactly where you stand and what to improve.' },
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
      <section className="px-6 py-20">
        <Card className="max-w-3xl mx-auto border-primary/20 bg-primary/[0.03]">
          <CardContent className="p-10 md:p-14 text-center">
            <GraduationCap className="w-10 h-10 mx-auto mb-4 text-primary" />
            <h2 className="text-2xl md:text-3xl font-bold text-foreground mb-3">
              Ready to Start Your CMS Journey?
            </h2>
            <p className="text-muted-foreground mb-8 max-w-lg mx-auto">
              Join aspirants who are using AI to prepare smarter, not harder. 
              Free to start — no credit card required.
            </p>
            <Button size="xl" asChild>
              <Link href={isAuthenticated ? '/dashboard' : '/register'}>
                Get Started Free <ChevronRight className="w-5 h-5" />
              </Link>
            </Button>
          </CardContent>
        </Card>
      </section>

      {/* Footer */}
      <footer className="px-6 py-8 border-t border-border">
        <div className="max-w-6xl mx-auto flex flex-col sm:flex-row items-center justify-between gap-4">
          <div className="flex items-center gap-2">
            <Zap className="w-4 h-4 text-primary" />
            <span className="text-sm font-semibold">CrackCMS</span>
          </div>
          <p className="text-sm text-muted-foreground">© 2026 CrackCMS — AI-Powered UPSC CMS Preparation Platform</p>
        </div>
      </footer>
    </div>
  );
}

function FileText(props: React.SVGProps<SVGSVGElement>) {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" {...props}>
      <path d="M15 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7Z" /><path d="M14 2v4a2 2 0 0 0 2 2h4" /><path d="M10 9H8" /><path d="M16 13H8" /><path d="M16 17H8" />
    </svg>
  );
}
