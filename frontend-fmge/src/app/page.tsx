import Link from "next/link";
import { Brain, BookOpen, Stethoscope, Sparkles, Trophy, GraduationCap } from "lucide-react";
import { brandName, siteDescription, siteTitle } from "@/lib/seo";
import { FMGE_SUBJECTS, TOTAL_BLUEPRINT_COUNT } from "@/lib/fmge-blueprint";

export default function HomePage() {
    return (
        <main className="min-h-screen flex flex-col">
            <header className="px-6 py-5 flex items-center justify-between border-b" style={{ borderColor: "var(--color-border)" }}>
                <div className="flex items-center gap-2">
                    <div className="w-9 h-9 rounded-full flex items-center justify-center" style={{ background: "var(--color-primary)" }}>
                        <GraduationCap className="w-5 h-5 text-white" />
                    </div>
                    <span className="text-lg font-bold">{brandName}</span>
                </div>
                <nav className="flex items-center gap-2">
                    <Link href="/login" className="btn-primary text-sm">Sign in</Link>
                </nav>
            </header>

            <section className="flex-1 px-6 py-16 md:py-24 max-w-6xl mx-auto w-full">
                <div className="text-center space-y-6">
                    <span className="inline-flex items-center gap-2 px-3 py-1 rounded-full text-xs font-semibold" style={{ background: "rgba(217,119,6,0.1)", color: "var(--accent-primary)" }}>
                        <Sparkles className="w-3.5 h-3.5" />
                        19 subjects · 300 questions · NBE pattern
                    </span>
                    <h1 className="text-4xl md:text-6xl font-extrabold tracking-tight">
                        Pass <span style={{ color: "var(--accent-primary)" }}>FMGE</span> on the first attempt
                    </h1>
                    <p className="text-base md:text-lg max-w-2xl mx-auto" style={{ color: "var(--color-muted-foreground)" }}>
                        {siteDescription}
                    </p>
                    <div className="flex flex-wrap justify-center gap-3 pt-4">
                        <Link href="/simulator" className="btn-primary">
                            <Trophy className="w-4 h-4" />
                            Start NBE-pattern Mock
                        </Link>
                        <Link href="/questions" className="btn-primary" style={{ background: "transparent", color: "var(--accent-primary)", border: "1px solid var(--color-border)" }}>
                            <BookOpen className="w-4 h-4" />
                            Browse Question Bank
                        </Link>
                    </div>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mt-16">
                    {[
                        { icon: BookOpen, title: `${TOTAL_BLUEPRINT_COUNT}-question NBE-pattern simulator`, desc: "Exact subject-wise weighting as per the official NBE blueprint." },
                        { icon: Brain, title: "AI explanations on every question", desc: "Mnemonics, why-wrong analysis and textbook references — even for obscure 19th-subject questions." },
                        { icon: Stethoscope, title: "5-year trend dashboard", desc: "See which subjects are most repeated and which questions reappear across years." },
                    ].map((f) => (
                        <article key={f.title} className="glass-card p-6">
                            <f.icon className="w-6 h-6 mb-3" style={{ color: "var(--accent-primary)" }} />
                            <h2 className="font-bold text-lg">{f.title}</h2>
                            <p className="text-sm mt-1" style={{ color: "var(--color-muted-foreground)" }}>{f.desc}</p>
                        </article>
                    ))}
                </div>

                <div className="mt-12 glass-card p-6">
                    <h2 className="font-bold text-lg mb-4">FMGE blueprint — subject-wise distribution</h2>
                    <ul className="grid grid-cols-2 md:grid-cols-4 gap-3">
                        {FMGE_SUBJECTS.map((s) => (
                            <li key={s.code} className="flex items-center justify-between text-sm p-2 rounded-md" style={{ background: "var(--color-muted)" }}>
                                <span>{s.name}</span>
                                <span className="font-mono font-bold" style={{ color: "var(--accent-primary)" }}>{s.typicalCount}</span>
                            </li>
                        ))}
                    </ul>
                </div>
            </section>

            <footer className="text-center text-xs py-6" style={{ color: "var(--color-muted-foreground)" }}>
                © {new Date().getFullYear()} {brandName} — {siteTitle}
            </footer>
        </main>
    );
}
