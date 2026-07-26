import { LegalLayout, buildLegalMetadata } from '@/components/LegalLayout';
import type { Metadata } from 'next';
import Link from 'next/link';
import Script from 'next/script';
import { Award, Brain, Heart, Lightbulb, ShieldCheck, Sparkles, Target, Users } from 'lucide-react';
import { siteName, siteUrl } from '@/lib/seo';

const title = 'About CrackCMS — Built by Doctors, Powered by AI';
const description = 'CrackCMS (by CrackLabs AI) is the highest-rated AI medical exam preparation platform for UPSC CMS, NEET PG, INI-CET, FMGE, USMLE and medical officer exams. Meet our team, mission, and story.';
const canonical = '/about';

export const metadata: Metadata = buildLegalMetadata({ title, description, canonical });

const team = [
    { role: 'Founder & CEO', name: 'Divyanshu Dubey', bio: 'Engineer & AI researcher focused on healthcare education. Built CrackCMS after seeing first-hand how scattered medical-prep resources are.' },
    { role: 'Chief Medical Officer', name: 'MBBS, MD (Internal Medicine)', bio: 'Practising clinician with 10+ years of teaching experience; oversees medical-review board.' },
    { role: 'Head of Content', name: 'MBBS, MD (Pediatrics)', bio: 'Curates question banks and ensures every explanation meets editorial standards.' },
    { role: 'Lead AI Engineer', name: 'MS (Computer Science)', bio: 'Designs the multi-provider AI pipeline that powers the AI tutor.' },
];

const stats = [
    { number: '1.92 lakh+', label: 'PYQs & curated MCQs' },
    { number: '47,000+', label: 'Active medical aspirants' },
    { number: '11+', label: 'AI providers in rotation' },
    { number: '4.8 / 5', label: 'Average user rating' },
];

const values = [
    { icon: Heart, title: 'Patient-first thinking', body: 'Every feature is designed with the ultimate bedside reality in mind. We teach concepts that will actually save lives.' },
    { icon: Brain, title: 'AI + human review', body: 'Large language models draft explanations at scale; clinicians verify them. The result: depth of a textbook, speed of AI.' },
    { icon: ShieldCheck, title: 'Evidence over opinion', body: 'Every claim cites a Tier-1 source. Outdated teaching is rejected, even if it appears in popular MCQ books.' },
    { icon: Sparkles, title: 'Modern learner-first design', body: 'Mobile-first, dark-mode-friendly, keyboard-shortcut-powered. Studying should feel like a flow state, not a chore.' },
];

export default function AboutPage() {
    const orgSchema = {
        '@context': 'https://schema.org',
        '@type': 'AboutPage',
        url: canonical,
        name: title,
        description,
        mainEntity: {
            '@type': 'Organization',
            name: siteName,
            url: siteUrl,
            foundingDate: '2024',
            founders: [{ '@type': 'Person', name: 'Divyanshu Dubey' }],
            numberOfEmployees: '10-50',
            areaServed: 'Worldwide',
            knowsAbout: [
                'UPSC CMS', 'NEET PG', 'INI-CET', 'FMGE', 'USMLE', 'Medical Officer Exams',
                'Clinical MCQs', 'AI in medical education',
            ],
        },
    };

    return (
        <>
            <Script id="about-schema" type="application/ld+json" strategy="beforeInteractive"
                dangerouslySetInnerHTML={{ __html: JSON.stringify(orgSchema) }} />

            <LegalLayout title={title} description={description} lastUpdated="July 21, 2026" canonical={canonical} schemaType="AboutPage">
                <h2>Our mission</h2>
                <p>
                    CrackCMS exists to give every medical aspirant in India and around the world a fair
                    shot at cracking competitive exams — regardless of which medical college they attend
                    or how much they can afford to spend on coaching. We combine clinical-grade content
                    with the latest advances in generative AI to deliver a study experience that&apos;s
                    faster, deeper, and more personal than any printed book or offline class.
                </p>

                <h2>What we&apos;ve built</h2>
                <p>
                    <strong>1,920+ previous-year questions</strong> across UPSC CMS, NEET PG, INI-CET and
                    FMGE, paired with AI-generated explanations, mnemonics, clinical pearls, textbook
                    references, and similar-PYQ links. Eleven large-language-model providers rotate behind
                    the scenes so the AI tutor is always available, never rate-limited, and always cites
                    its sources.
                </p>

                <h2>By the numbers</h2>
                <div className="not-prose grid grid-cols-2 gap-4 sm:grid-cols-4 my-6">
                    {stats.map(s => (
                        <div key={s.label} className="rounded-2xl border border-border bg-card p-4 text-center">
                            <p className="text-2xl font-black text-foreground">{s.number}</p>
                            <p className="mt-1 text-xs font-medium text-muted-foreground">{s.label}</p>
                        </div>
                    ))}
                </div>

                <h2>What we believe</h2>
                <div className="not-prose grid gap-4 sm:grid-cols-2 my-6">
                    {values.map(v => (
                        <div key={v.title} className="rounded-2xl border border-border bg-card p-5">
                            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-primary/10 text-primary">
                                <v.icon className="h-5 w-5" />
                            </div>
                            <h3 className="mt-3 text-base font-bold text-foreground">{v.title}</h3>
                            <p className="mt-1 text-sm leading-relaxed text-muted-foreground">{v.body}</p>
                        </div>
                    ))}
                </div>

                <h2>Meet the team</h2>
                <p>
                    CrackCMS is built by a small team of doctors, AI engineers, and medical educators.
                    We&apos;re proudly independent, bootstrapped, and focused on long-term learner
                    outcomes — not short-term engagement metrics.
                </p>
                <div className="not-prose grid gap-4 sm:grid-cols-2 my-6">
                    {team.map(member => (
                        <div key={member.role} className="rounded-2xl border border-border bg-card p-5">
                            <div className="flex h-12 w-12 items-center justify-center rounded-full bg-linear-to-br from-primary to-teal-500 text-base font-black text-white">
                                {member.name.split(' ').map(s => s[0]).slice(0, 2).join('')}
                            </div>
                            <p className="mt-3 text-sm font-bold text-foreground">{member.name}</p>
                            <p className="text-xs font-semibold uppercase tracking-wider text-primary">{member.role}</p>
                            <p className="mt-2 text-sm leading-relaxed text-muted-foreground">{member.bio}</p>
                        </div>
                    ))}
                </div>

                <h2>Where we&apos;re going</h2>
                <p>
                    Over the next 12 months we&apos;re launching:
                </p>
                <ul>
                    <li><strong>Adaptive mock tests</strong> that adjust difficulty based on your last 50 questions.</li>
                    <li><strong>Voice-first AI tutor</strong> for ward-round revision.</li>
                    <li><strong>Native Android &amp; iOS apps</strong> built with React Native.</li>
                    <li><strong>Vernacular support</strong> — Hindi, Tamil, Telugu, Bengali, Marathi — for AI tutor responses.</li>
                </ul>

                <h2>Get in touch</h2>
                <p>
                    Questions, partnerships, or press inquiries: <a href="mailto:hello@cracklabs.app">hello@cracklabs.app</a>.
                    For learner support, see our <Link href="/contact" className="text-primary underline">Contact page</Link>.
                </p>

                <div className="not-prose mt-10 rounded-2xl border border-primary/30 bg-primary/5 p-6 sm:p-8">
                    <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
                        <div>
                            <p className="text-lg font-bold text-foreground">Ready to start studying?</p>
                            <p className="text-sm text-muted-foreground">Create a free account in 30 seconds.</p>
                        </div>
                        <div className="flex flex-wrap gap-2">
                            <Link href="/register" className="rounded-xl bg-primary px-5 py-2.5 text-sm font-bold text-primary-foreground hover:opacity-95">Create account</Link>
                            <Link href="/subscription" className="rounded-xl border border-border bg-card px-5 py-2.5 text-sm font-bold text-foreground hover:bg-muted">See premium</Link>
                        </div>
                    </div>
                </div>
            </LegalLayout>
        </>
    );
}
