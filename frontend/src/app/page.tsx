'use client';
import Link from 'next/link';
import { useAuth } from '@/lib/auth';
import { BookOpen, Brain, BarChart3, GraduationCap, Sparkles, Target, ChevronRight, Zap, Shield, TrendingUp } from 'lucide-react';

export default function LandingPage() {
  const { isAuthenticated } = useAuth();

  const features = [
    { icon: <BookOpen className="w-8 h-8" />, title: 'PYQ Engine', desc: '25+ years of UPSC CMS questions with detailed explanations & textbook references', color: '#06b6d4' },
    { icon: <Brain className="w-8 h-8" />, title: 'AI Tutor', desc: 'Ask any medical concept — get instant, exam-focused explanations with mnemonics', color: '#8b5cf6' },
    { icon: <Target className="w-8 h-8" />, title: 'Smart Tests', desc: '9 test types: subject-wise, topic-wise, PYQ simulator, adaptive AI tests', color: '#f59e0b' },
    { icon: <Sparkles className="w-8 h-8" />, title: 'Mnemonic Generator', desc: 'AI generates memory tricks, acronyms & clinical correlation hooks', color: '#ec4899' },
    { icon: <BarChart3 className="w-8 h-8" />, title: 'Analytics Dashboard', desc: 'Track accuracy, weak topics, revision heatmap & AI-powered suggestions', color: '#10b981' },
    { icon: <GraduationCap className="w-8 h-8" />, title: 'CMS Simulator', desc: 'Full Paper 1 & Paper 2 mock exams matching the real exam experience', color: '#ef4444' },
  ];

  const stats = [
    { value: '1500+', label: 'PYQ Questions' },
    { value: '47', label: 'Topic Areas' },
    { value: '5', label: 'Core Subjects' },
    { value: '9', label: 'Test Types' },
  ];

  return (
    <div style={{ background: 'var(--bg-primary)' }} className="min-h-screen">
      {/* Navbar */}
      <nav className="flex items-center justify-between px-8 py-4" style={{ background: 'rgba(10, 15, 28, 0.9)', backdropFilter: 'blur(12px)', borderBottom: '1px solid var(--glass-border)', position: 'sticky', top: 0, zIndex: 50 }}>
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl flex items-center justify-center" style={{ background: 'var(--gradient-primary)' }}>
            <Zap className="w-6 h-6 text-white" />
          </div>
          <span className="text-xl font-bold gradient-text">CrackCMS</span>
        </div>
        <div className="flex items-center gap-4">
          {isAuthenticated ? (
            <Link href="/dashboard" className="btn-primary">Go to Dashboard <ChevronRight className="w-4 h-4" /></Link>
          ) : (
            <>
              <Link href="/login" className="btn-secondary">Login</Link>
              <Link href="/register" className="btn-primary">Start Free <ChevronRight className="w-4 h-4" /></Link>
            </>
          )}
        </div>
      </nav>

      {/* Hero Section */}
      <section className="px-8 py-24 text-center max-w-5xl mx-auto animate-fadeInUp">
        <div className="inline-flex items-center gap-2 px-4 py-2 rounded-full mb-6" style={{ background: 'rgba(6, 182, 212, 0.1)', border: '1px solid rgba(6, 182, 212, 0.2)' }}>
          <Sparkles className="w-4 h-4" style={{ color: 'var(--accent-primary)' }} />
          <span className="text-sm font-medium" style={{ color: 'var(--accent-primary)' }}>AI-Powered • Exam-Focused • Next Generation</span>
        </div>
        <h1 className="text-5xl md:text-7xl font-bold mb-6 leading-tight">
          Crack <span className="gradient-text">UPSC CMS</span><br />
          Like Never Before
        </h1>
        <p className="text-xl mb-10 max-w-2xl mx-auto" style={{ color: 'var(--text-secondary)' }}>
          The most advanced AI-powered preparation platform. PYQ engine, AI tutor,
          mnemonic generator, and personalized analytics — all in one place.
        </p>
        <div className="flex items-center justify-center gap-4 mb-16">
          <Link href={isAuthenticated ? '/dashboard' : '/register'} className="btn-primary text-lg py-3 px-8">
            Start Preparing Now <ChevronRight className="w-5 h-5" />
          </Link>
          <Link href="#features" className="btn-secondary text-lg py-3 px-8">
            Explore Features
          </Link>
        </div>

        {/* Stats */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-6 max-w-3xl mx-auto">
          {stats.map((stat, i) => (
            <div key={i} className="stat-card text-center animate-pulse-glow" style={{ animationDelay: `${i * 0.5}s` }}>
              <div className="text-3xl font-bold gradient-text">{stat.value}</div>
              <div className="text-sm mt-1" style={{ color: 'var(--text-secondary)' }}>{stat.label}</div>
            </div>
          ))}
        </div>
      </section>

      {/* Features Section */}
      <section id="features" className="px-8 py-20 max-w-6xl mx-auto">
        <h2 className="text-3xl font-bold text-center mb-4">Everything You Need to <span className="gradient-text">Crack CMS</span></h2>
        <p className="text-center mb-12" style={{ color: 'var(--text-secondary)' }}>Not just a question bank — it&apos;s your AI-powered CMS knowledge engine</p>
        <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-6">
          {features.map((feat, i) => (
            <div key={i} className="glass-card p-6 animate-fadeInUp" style={{ animationDelay: `${i * 0.1}s` }}>
              <div className="w-14 h-14 rounded-xl flex items-center justify-center mb-4" style={{ background: `${feat.color}15`, color: feat.color }}>
                {feat.icon}
              </div>
              <h3 className="text-lg font-bold mb-2">{feat.title}</h3>
              <p className="text-sm" style={{ color: 'var(--text-secondary)' }}>{feat.desc}</p>
            </div>
          ))}
        </div>
      </section>

      {/* CTA Section */}
      <section className="px-8 py-20 text-center">
        <div className="glass-card max-w-3xl mx-auto p-12">
          <Shield className="w-12 h-12 mx-auto mb-4" style={{ color: 'var(--accent-primary)' }} />
          <h2 className="text-3xl font-bold mb-4">Ready to Start Your <span className="gradient-text">CMS Journey</span>?</h2>
          <p className="mb-8" style={{ color: 'var(--text-secondary)' }}>Join thousands of aspirants using AI to prepare smarter, not harder.</p>
          <Link href={isAuthenticated ? '/dashboard' : '/register'} className="btn-primary text-lg py-3 px-10">
            Get Started Free <TrendingUp className="w-5 h-5" />
          </Link>
        </div>
      </section>

      {/* Footer */}
      <footer className="px-8 py-8 text-center" style={{ borderTop: '1px solid var(--glass-border)', color: 'var(--text-secondary)' }}>
        <p className="text-sm">© 2026 CrackCMS — AI-Powered UPSC CMS Preparation Platform</p>
      </footer>
    </div>
  );
}
