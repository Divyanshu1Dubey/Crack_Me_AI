import Link from "next/link";
import { Brain, BookOpen, Activity, Stethoscope, Sparkles, Trophy } from "lucide-react";
import { brandName, siteDescription, siteTitle } from "@/lib/seo";
import { STEP_INFO } from "@/lib/step";

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
                    <Link href="/login" className="btn-primary text-sm">Sign in</Link>
                </nav>
            </header>

            <section className="flex-1 px-6 py-16 md:py-24 max-w-6xl mx-auto w-full">
                <div className="text-center space-y-6">
                    <span className="inline-flex items-center gap-2 px-3 py-1 rounded-full text-xs font-semibold" style={{ background: "rgba(124,58,237,0.1)", color: "var(--accent-primary)" }}>
                        <Sparkles className="w-3.5 h-3.5" />
                        Step 1 • Step 2 CK • Step 3
                    </span>
                    <h1 className="text-4xl md:text-6xl font-extrabold tracking-tight">
                        Match into your <span style={{ color: "var(--accent-primary)" }}>dream residency</span>
                    </h1>
                    <p className="text-base md:text-lg max-w-2xl mx-auto" style={{ color: "var(--color-muted-foreground)" }}>
                        {siteDescription}
                    </p>
                    <div className="flex flex-wrap justify-center gap-3 pt-4">
                        <Link href="/questions?step=step1" className="btn-primary">
                            <BookOpen className="w-4 h-4" />
                            Start with Step 1
                        </Link>
                        <Link href="/score-estimator" className="btn-primary" style={{ background: "transparent", color: "var(--accent-primary)", border: "1px solid var(--color-border)" }}>
                            <Activity className="w-4 h-4" />
                            Estimate My Score
                        </Link>
                    </div>
                </div>

                {/* Step switcher cards */}
                <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mt-16">
                    {Object.entries(STEP_INFO).map(([key, info]) => (
                        <Link key={key} href={`/questions?step=${key}`} className="glass-card p-6 block hover:translate-y-[-2px] transition-transform">
                            <h2 className="font-bold text-lg">{info.label}</h2>
                            <p className="text-sm mt-1" style={{ color: "var(--color-muted-foreground)" }}>{info.tagline}</p>
                        </Link>
                    ))}
                </div>

                <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mt-8">
                    {[
                        { icon: BookOpen, title: "Step-specific banks", desc: "Pre-clinical, clinical, and independent practice question pools aligned to current USMLE content outlines." },
                        { icon: Brain, title: "First Aid cross-ref", desc: "Every AI explanation links to the corresponding First Aid chapter + page." },
                        { icon: Trophy, title: "Score estimator", desc: "Convert your %-correct into an estimated 3-digit Step score using a calibration table." },
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
