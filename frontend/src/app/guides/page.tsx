import type { Metadata } from 'next';
import Link from 'next/link';
import Script from 'next/script';
import { ArrowRight, BookOpen } from 'lucide-react';
import { Card, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { siteName, siteUrl } from '@/lib/seo';

export const metadata: Metadata = {
    title: 'Medical Exam Preparation Guides — UPSC CMS, NEET PG, INI-CET | CrackCMS',
    description: 'In-depth guides on UPSC CMS, NEET PG, INI-CET, FMGE, USMLE, Medical Officer recruitment, government doctor jobs, and AI in medical education. Written by practising clinicians.',
    alternates: { canonical: '/guides', languages: { 'en-IN': '/guides' } },
    openGraph: {
        type: 'website',
        url: '/guides',
        title: 'Medical Exam Preparation Guides — UPSC CMS, NEET PG, INI-CET | CrackCMS',
        description: 'Comprehensive guides on UPSC CMS, NEET PG, INI-CET, FMGE, USMLE, Medical Officer exams, and government doctor jobs.',
        siteName,
    },
    robots: { index: true, follow: true },
};

const guides = [
    { slug: 'upsc-cms-complete-guide', title: 'UPSC CMS Complete Guide 2026', desc: 'Everything you need to know about the Combined Medical Services exam — eligibility, syllabus, pattern, books, salary, and 6-month study plan.', tag: 'UPSC CMS', emoji: '🏛️', readTime: '12 min' },
    { slug: 'neet-pg-complete-guide', title: 'NEET PG Complete Guide 2026', desc: 'How to prepare for NEET PG in 6 months — exam pattern, subject-wise strategy, topper tips, AIR prediction, and image-based questions.', tag: 'NEET PG', emoji: '🩺', readTime: '11 min' },
    { slug: 'ini-cet-complete-guide', title: 'INI-CET Complete Guide', desc: 'Crack INI-CET for AIIMS, PGIMER, JIPMER, NIMHANS, SCTIMST — eligibility, pattern, syllabus, and the image-based question drill.', tag: 'INI-CET', emoji: '🏥', readTime: '10 min' },
    { slug: 'fmge-complete-guide', title: 'FMGE Complete Guide', desc: 'Pass the MCI Screening Test on your first attempt — syllabus, books, strategy, and Indian-context clinical reasoning.', tag: 'FMGE', emoji: '🌍', readTime: '9 min' },
    { slug: 'usmle-step-1-guide', title: 'USMLE Step 1 Guide for Indian MBBS Students', desc: 'A comprehensive Step 1 roadmap — First Aid, Pathoma, UWorld, study schedule, and IMG-specific advice.', tag: 'USMLE', emoji: '🇺🇸', readTime: '10 min' },
    { slug: 'medical-officer-jobs', title: 'Government Medical Officer Jobs After MBBS', desc: 'Every central and state MBBS doctor post — UPSC CMS, AIIMS MO, state PSCs, NHM, ESIC, Railways, Defence.', tag: 'Careers', emoji: '🏛️', readTime: '8 min' },
    { slug: 'ai-in-medical-education', title: 'How AI Is Transforming Medical Education', desc: 'A practising clinician&apos;s perspective on large-language-model tutors, adaptive MCQs, and the future of exam prep.', tag: 'EdTech', emoji: '🤖', readTime: '7 min' },
    { slug: 'study-plan-builder', title: 'Build a Personalised Study Plan', desc: 'A step-by-step framework to build a 6-month UPSC CMS or NEET PG study plan using PYQs, AI tutor, and spaced repetition.', tag: 'Strategy', emoji: '📅', readTime: '6 min' },
];

export default function GuidesIndexPage() {
    const jsonLd = {
        '@context': 'https://schema.org',
        '@type': 'CollectionPage',
        name: 'Medical Exam Preparation Guides',
        description: 'In-depth guides covering UPSC CMS, NEET PG, INI-CET, FMGE, USMLE, and government doctor jobs.',
        url: '/guides',
        isPartOf: { '@type': 'WebSite', name: siteName, url: siteUrl },
        mainEntity: {
            '@type': 'ItemList',
            itemListElement: guides.map((g, i) => ({
                '@type': 'ListItem',
                position: i + 1,
                url: `${siteUrl}/guides/${g.slug}`,
                name: g.title,
            })),
        },
    };

    return (
        <>
            <Script id="guides-hub-schema" type="application/ld+json" strategy="beforeInteractive"
                dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }} />

            <div className="min-h-screen bg-background">
                <section className="border-b border-border bg-gradient-to-br from-primary/8 via-background to-accent/10">
                    <div className="mx-auto max-w-7xl px-4 py-12 sm:px-6 sm:py-16">
                        <Badge className="bg-primary/10 text-primary border-primary/30 text-xs font-bold uppercase tracking-wider">
                            <BookOpen className="h-3 w-3 mr-1" /> Guides
                        </Badge>
                        <h1 className="mt-4 text-3xl font-black tracking-tight sm:text-4xl md:text-5xl">
                            Medical exam preparation guides
                        </h1>
                        <p className="mt-4 max-w-3xl text-lg text-muted-foreground">
                            In-depth, clinician-reviewed guides covering every major medical entrance exam, government
                            doctor jobs, and AI in medical education. Updated for 2026.
                        </p>
                    </div>
                </section>

                <section className="mx-auto max-w-7xl px-4 py-10 sm:px-6 sm:py-14">
                    <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
                        {guides.map(g => (
                            <Link key={g.slug} href={`/guides/${g.slug}`}>
                                <Card className="h-full border-border/60 bg-card transition-all hover:border-primary/40 hover:shadow-md">
                                    <CardContent className="p-6">
                                        <div className="flex items-center gap-3 mb-3">
                                            <div className="text-3xl">{g.emoji}</div>
                                            <Badge variant="outline" className="text-[10px] font-bold uppercase tracking-wider">{g.tag}</Badge>
                                        </div>
                                        <h2 className="text-base font-bold text-foreground">{g.title}</h2>
                                        <p className="mt-2 text-sm leading-relaxed text-muted-foreground line-clamp-3">{g.desc}</p>
                                        <div className="mt-4 flex items-center justify-between text-xs text-muted-foreground">
                                            <span>{g.readTime} read</span>
                                            <span className="inline-flex items-center gap-1 font-semibold text-primary">
                                                Read <ArrowRight className="h-3 w-3" />
                                            </span>
                                        </div>
                                    </CardContent>
                                </Card>
                            </Link>
                        ))}
                    </div>
                </section>
            </div>
        </>
    );
}
