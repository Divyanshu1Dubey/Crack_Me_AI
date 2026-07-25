import { Brain, BookOpen, Stethoscope, Sparkles, Trophy, Activity } from "lucide-react";
import { brandName, siteDescription, siteTitle } from "@/lib/seo";

// The NEET PG landing page is a marketing surface only — the live app
// (questions, tests, flashcards, AI tutor, analytics, bookmarks) lives
// on the main CrackCMS site. CTAs redirect there via external links.
// Override with NEXT_PUBLIC_MAIN_APP_URL.
const MAIN_APP_URL = process.env.NEXT_PUBLIC_MAIN_APP_URL || "https://cracklabs.app";

export default function HomePage() {
    return (
        <main className="min-h-screen flex flex-col">
            <header className="px-6 py-5 flex items-center justify-between border-b" style={{ borderColor: "var(--color-border)" }}>
                <div className="flex items-center gap-2">
                    <div className="w-9 h-9 rounded-full flex items-center justify-center" style={{ background: "var(--color-primary)" }}>
                        <Stethoscope className="w-5 h-5 text-white" />
                    </div>
                    <span className="text-lg font-bold">{brandName}</span>
                </div>
                <nav className="flex items-center gap-2">
                    <a href={`${MAIN_APP_URL}/login`} target="_blank" rel="noopener noreferrer" className="btn-primary text-sm">
                        Sign in
                    </a>
                </nav>
            </header>

            <section className="flex-1 px-6 py-16 md:py-24 max-w-6xl mx-auto w-full">
                <div className="text-center space-y-6">
                    <span className="inline-flex items-center gap-2 px-3 py-1 rounded-full text-xs font-semibold" style={{ background: "rgba(5,150,105,0.1)", color: "var(--accent-primary)" }}>
                        <Sparkles className="w-3.5 h-3.5" />
                        {`India's #1 AI-powered NEET PG prep`}
                    </span>
                    <h1 className="text-4xl md:text-6xl font-extrabold tracking-tight">
                        Conquer <span style={{ color: "var(--accent-primary)" }}>NEET PG</span>
                    </h1>
                    <p className="text-base md:text-lg max-w-2xl mx-auto" style={{ color: "var(--color-muted-foreground)" }}>
                        {siteDescription}
                    </p>
                    <div className="flex flex-wrap justify-center gap-3 pt-4">
                        <a href={`${MAIN_APP_URL}/practice?exam=neet_pg`} target="_blank" rel="noopener noreferrer" className="btn-primary">
                            <BookOpen className="w-4 h-4" />
                            Start Practising
                        </a>
                        <a href={`${MAIN_APP_URL}/simulator?exam=neet_pg`} target="_blank" rel="noopener noreferrer" className="btn-primary" style={{ background: "transparent", color: "var(--accent-primary)", border: "1px solid var(--color-border)" }}>
                            <Trophy className="w-4 h-4" />
                            Take a Grand Test
                        </a>
                    </div>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mt-16">
                    {[
                        { icon: BookOpen, title: "5000+ PYQs", desc: "Previous year questions from 2010–2025, subject-wise and topic-tagged." },
                        { icon: Brain, title: "AI Explanations", desc: "Mnemonics, why-wrong analysis, textbook references, clinical pearls — for every question." },
                        { icon: Activity, title: "AIR Predictor", desc: "After every grand test, predict your All India Rank using past year distributions." },
                    ].map((f) => (
                        <article key={f.title} className="glass-card p-6">
                            <f.icon className="w-6 h-6 mb-3" style={{ color: "var(--accent-primary)" }} />
                            <h2 className="font-bold text-lg">{f.title}</h2>
                            <p className="text-sm mt-1" style={{ color: "var(--color-muted-foreground)" }}>{f.desc}</p>
                        </article>
                    ))}
                </div>
            </section>

            <footer className="text-center text-xs py-6" style={{ color: "var(--color-muted-foreground)" }}>
                © {new Date().getFullYear()} {brandName} — {siteTitle}
            </footer>
        </main>
    );
}
