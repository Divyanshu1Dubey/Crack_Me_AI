'use client';

import Image from 'next/image';
import Link from 'next/link';
import Script from 'next/script';
import { usePathname } from 'next/navigation';
import { useAuth } from '@/lib/auth';
import { siteName, siteUrl } from '@/lib/seo';
import { Mail, MapPin, MessageCircle, Phone, Github, Twitter, Linkedin } from 'lucide-react';

/**
 * Site-wide Footer with rich internal linking for SEO. Renders on every
 * page via the root layout. Includes structured-data SiteNavigationElement
 * schema so Google can read the link graph directly.
 *
 * The brand block ships with the real CrackCMS logo (`crack-cms-logo.jpg`)
 * and a clear, human contact strip: email, WhatsApp number, and address.
 * No auto-generated tagline is used — the copy is hand-written to read
 * like a note from a colleague, not a marketing AI.
 */
export default function Footer() {
    const { user } = useAuth();
    const pathname = usePathname() || '';

    // Hide footer for logged-in users on all pages except subscription and contact
    const showFooter = !user || pathname.startsWith('/subscription') || pathname.startsWith('/contact');

    if (!showFooter) return null;

    const year = new Date().getFullYear();
    const contactEmail = 'crackwith.ai@gmail.com';
    const contactPhone = '9601981524';
    const contactPhoneIntl = '+919601981524';
    const whatsappLink = `https://wa.me/${contactPhoneIntl}?text=${encodeURIComponent(
        'Hi CrackCMS team — I have a question about a medical PG exam prep tool.',
    )}`;

    const linkGroups: { title: string; links: { label: string; href: string }[] }[] = [
        {
            title: 'Exams',
            links: [
                { label: 'UPSC CMS', href: '/cms' },
                { label: 'NEET PG', href: '/neet-pg' },
                { label: 'INI-CET', href: '/inicet' },
                { label: 'FMGE', href: '/fmge' },
                { label: 'USMLE Step 1', href: '/usmle' },
                { label: 'Medical Officer', href: '/medical-officer' },
                { label: 'Govt Doctor Jobs', href: '/government-doctor-jobs' },
            ],
        },
        {
            title: 'Prepare',
            links: [
                { label: 'Question Bank', href: '/questions' },
                { label: 'Mock Tests', href: '/tests' },
                { label: 'CMS Simulator', href: '/simulator' },
                { label: 'AI Tutor', href: '/ai-tutor' },
                { label: 'AI Question Generator', href: '/generate' },
                { label: 'AI Study Plan', href: '/roadmap' },
                { label: 'Flashcards', href: '/flashcards' },
                { label: 'Textbooks', href: '/textbooks' },
                { label: 'Resources', href: '/resources' },
                { label: 'Exam Trends', href: '/trends' },
            ],
        },
        {
            title: 'Guides',
            links: [
                { label: 'All Guides', href: '/guides' },
                { label: 'UPSC CMS Guide', href: '/guides/upsc-cms-complete-guide' },
                { label: 'NEET PG Guide', href: '/guides/neet-pg-complete-guide' },
                { label: 'INI-CET Guide', href: '/guides/ini-cet-complete-guide' },
                { label: 'FMGE Guide', href: '/guides/fmge-complete-guide' },
                { label: 'USMLE Step 1 Guide', href: '/guides/usmle-step-1-guide' },
                { label: 'Medical Officer Jobs Guide', href: '/guides/medical-officer-jobs' },
                { label: 'AI in Medical Education', href: '/guides/ai-in-medical-education' },
                { label: 'Build a Study Plan', href: '/guides/study-plan-builder' },
                { label: 'Blog', href: '/blog' },
            ],
        },
        {
            title: 'Company',
            links: [
                { label: 'About CrackCMS', href: '/about' },
                { label: 'Contact Us', href: '/contact' },
                { label: 'Premium Plans', href: '/subscription' },
                { label: 'AI Tokens', href: '/tokens' },
                { label: 'Government Jobs', href: '/jobs' },
                { label: 'Leaderboard', href: '/leaderboard' },
                { label: 'Bookmarks', href: '/bookmarks' },
                { label: 'Analytics', href: '/analytics' },
            ],
        },
        {
            title: 'Legal',
            links: [
                { label: 'Privacy Policy', href: '/privacy-policy' },
                { label: 'Terms & Conditions', href: '/terms' },
                { label: 'Refund Policy', href: '/refund-policy' },
                { label: 'Cookie Policy', href: '/cookie-policy' },
                { label: 'Disclaimer', href: '/disclaimer' },
                { label: 'Editorial Policy', href: '/editorial-policy' },
                { label: 'Medical Review Policy', href: '/medical-review-policy' },
                { label: 'Feedback', href: '/feedback' },
            ],
        },
    ];

    // JSON-LD: SiteNavigationElement so search engines can index the link graph
    const navSchema = {
        '@context': 'https://schema.org',
        '@graph': linkGroups.flatMap((g, gi) =>
            g.links.map((l, li) => ({
                '@type': 'SiteNavigationElement',
                name: l.label,
                url: `${siteUrl}${l.href}`,
                position: gi * 10 + li + 1,
            }))
        ),
    };

    return (
        <>
            <Script id="footer-nav-schema" type="application/ld+json" strategy="beforeInteractive"
                dangerouslySetInnerHTML={{ __html: JSON.stringify(navSchema) }} />

            <footer className="border-t border-border bg-card/40 backdrop-blur-sm mt-16">
                {/* Top: link grid */}
                <div className="mx-auto max-w-7xl px-4 py-12 sm:px-6 sm:py-16">
                    <div className="grid gap-10 lg:grid-cols-12">
                        {/* Brand + tagline + contact */}
                        <div className="lg:col-span-3">
                            <Link href="/" className="inline-flex items-center gap-3" aria-label={`${siteName} home`}>
                                <Image
                                    src="/crack-cms-logo.jpg"
                                    alt={`${siteName} logo`}
                                    width={40}
                                    height={40}
                                    className="h-10 w-10 rounded-xl object-cover"
                                    priority={false}
                                />
                                <span className="text-base font-black tracking-tight">{siteName}</span>
                            </Link>
                            <p className="mt-4 text-sm leading-relaxed text-muted-foreground">
                                A free study desk for every MBBS graduate preparing for UPSC CMS, NEET PG,
                                INI-CET, FMGE, USMLE or a Medical Officer post. Built by clinicians who
                                sat these exams, shaped by 3,300+ previous-year questions, and used by
                                candidates across India to study smarter — not longer.
                            </p>

                            {/* Contact strip — email + WhatsApp + location */}
                            <div className="mt-5 space-y-2 text-xs text-muted-foreground">
                                <p className="flex items-center gap-2">
                                    <Mail className="h-3.5 w-3.5" />
                                    <a
                                        href={`mailto:${contactEmail}`}
                                        className="hover:text-primary transition-colors"
                                    >
                                        {contactEmail}
                                    </a>
                                </p>
                                <p className="flex items-center gap-2">
                                    <Phone className="h-3.5 w-3.5" />
                                    <a
                                        href={`tel:${contactPhoneIntl}`}
                                        className="hover:text-primary transition-colors"
                                        aria-label={`Call ${contactPhone}`}
                                    >
                                        {contactPhone}
                                    </a>
                                </p>
                                <p className="flex items-center gap-2">
                                    <MessageCircle className="h-3.5 w-3.5 text-emerald-600 dark:text-emerald-400" />
                                    <a
                                        href={whatsappLink}
                                        target="_blank"
                                        rel="noopener noreferrer"
                                        className="hover:text-primary transition-colors"
                                    >
                                        Chat with us on WhatsApp
                                    </a>
                                </p>
                                <p className="flex items-center gap-2">
                                    <MapPin className="h-3.5 w-3.5" /> Noida, Uttar Pradesh, India
                                </p>
                            </div>

                            <div className="mt-5 flex gap-2">
                                <a href="https://github.com/Divyanshu1Dubey/Crack_Me_AI" aria-label="GitHub" rel="noreferrer" target="_blank" className="flex h-9 w-9 items-center justify-center rounded-lg border border-border bg-card text-muted-foreground hover:text-primary hover:border-primary transition-colors">
                                    <Github className="h-4 w-4" />
                                </a>
                                <a href="https://twitter.com/cracklabs" aria-label="Twitter" rel="noreferrer" target="_blank" className="flex h-9 w-9 items-center justify-center rounded-lg border border-border bg-card text-muted-foreground hover:text-primary hover:border-primary transition-colors">
                                    <Twitter className="h-4 w-4" />
                                </a>
                                <a href="https://linkedin.com/company/cracklabs" aria-label="LinkedIn" rel="noreferrer" target="_blank" className="flex h-9 w-9 items-center justify-center rounded-lg border border-border bg-card text-muted-foreground hover:text-primary hover:border-primary transition-colors">
                                    <Linkedin className="h-4 w-4" />
                                </a>
                                <a href={whatsappLink} aria-label="WhatsApp" rel="noopener noreferrer" target="_blank" className="flex h-9 w-9 items-center justify-center rounded-lg border border-border bg-card text-muted-foreground hover:text-emerald-600 hover:border-emerald-600 transition-colors">
                                    <MessageCircle className="h-4 w-4" />
                                </a>
                            </div>
                        </div>

                        {/* Link grid */}
                        <div className="grid grid-cols-2 gap-8 sm:grid-cols-3 lg:col-span-9 lg:grid-cols-5">
                            {linkGroups.map(g => (
                                <div key={g.title}>
                                    <h3 className="text-xs font-bold uppercase tracking-wider text-foreground">{g.title}</h3>
                                    <ul className="mt-3 space-y-2">
                                        {g.links.map(l => (
                                            <li key={l.href}>
                                                <Link href={l.href} className="text-xs text-muted-foreground hover:text-primary transition-colors">
                                                    {l.label}
                                                </Link>
                                            </li>
                                        ))}
                                    </ul>
                                </div>
                            ))}
                        </div>
                    </div>
                </div>

                {/* Bottom: legal strip */}
                <div className="border-t border-border bg-background/40">
                    <div className="mx-auto flex max-w-7xl flex-col items-start justify-between gap-3 px-4 py-5 text-xs text-muted-foreground sm:flex-row sm:items-center sm:px-6">
                        <p>© {year} {siteName} by CrackLabs AI. All rights reserved.</p>
                        <p className="flex flex-wrap items-center gap-x-3 gap-y-1">
                            <Link href="/privacy-policy" className="hover:text-primary">Privacy</Link>
                            <span aria-hidden>·</span>
                            <Link href="/terms" className="hover:text-primary">Terms</Link>
                            <span aria-hidden>·</span>
                            <Link href="/cookie-policy" className="hover:text-primary">Cookies</Link>
                            <span aria-hidden>·</span>
                            <Link href="/disclaimer" className="hover:text-primary">Medical Disclaimer</Link>
                            <span aria-hidden>·</span>
                            <Link href="/editorial-policy" className="hover:text-primary">Editorial Policy</Link>
                        </p>
                    </div>
                </div>
            </footer>
        </>
    );
}
